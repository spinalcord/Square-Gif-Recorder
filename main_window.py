from typing import List, Optional

from utils.qt_imports import *
from utils.constants import *
from core.recording_timer import RecordingTimer
from utils.gif_saver import save_gif_from_frames
from pynput import keyboard
from core.app_enums import AppMode
from core.data_classes import *
from managers.ui_manager import UIManager
from managers.hotkey_manager import HotkeyManager
from managers.recording_manager import RecordingManager
from widgets.range_slider import RangeSlider
from widgets.preview_widget import PreviewWidget


class GifRecorderMainWindow(QMainWindow):
    """
    Clean, well-structured main window for GIF recording application.
    Responsibilities are properly separated into manager classes.
    """
    
    # Qt signals for thread-safe hotkey handling
    record_signal = pyqtSignal()
    pause_signal = pyqtSignal()
    stop_signal = pyqtSignal()
    record_frame_signal = pyqtSignal()  # NEW: Signal for single frame recording

    def __init__(self):
        super().__init__()
        
        # Core data
        self.frames: List[QImage] = []
        self.drag_pos = QPoint()
        self._last_mode_was_edit = True # wird von ui_manager verwendet
        self._is_closing = False
        
        # NEU: Speicherung der Fenstergröße
        self._saved_window_size: Optional[QSize] = None
        self._saved_window_pos: Optional[QPoint] = None
        
        # Initialize managers
        self.ui_manager = UIManager(self)
        self.recording_manager = RecordingManager(self)
        self.hotkey_manager = HotkeyManager(self, HotkeyConfig())
        
        # Setup
        self._init_ui()
        self._connect_signals()
        self._setup_window()
        self._setup_hotkeys()
        
        # Initial state
        self.ui_manager.update_for_mode(AppMode.READY)
        QTimer.singleShot(0, self._initial_fix)

    def _init_ui(self) -> None:
        """Initialize the user interface."""
        self._create_central_widget()
        self._create_controls()
        self._create_preview_section()
        self._create_quality_settings()
        self._add_size_grip()
    
    def _create_central_widget(self) -> None:
        """Create the main layout structure."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Transparent recording area spacer
        self.recording_area_spacer = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )
        self.main_layout.addSpacerItem(self.recording_area_spacer)
    
    def _create_controls(self) -> None:
        """Create the main control panel."""
        self.controls_frame = QWidget()
        controls_layout = QVBoxLayout(self.controls_frame)
        controls_layout.setContentsMargins(10, 10, 10, 10)
        
        # Toolbar with main buttons
        toolbar = self._create_toolbar()
        controls_layout.addLayout(toolbar)
        
        # Status and info labels
        self.status_label = QLabel("Ready.")
        controls_layout.addWidget(self.status_label)
        
        self.hotkey_info_label = QLabel("")
        self.hotkey_info_label.setStyleSheet("font-size: 10px; color: gray;")
        controls_layout.addWidget(self.hotkey_info_label)
        
        self.main_layout.addWidget(self.controls_frame)
    
    def _create_toolbar(self) -> QHBoxLayout:
        """Create the main toolbar with buttons and FPS control."""
        toolbar_layout = QHBoxLayout()
        
        # Action buttons
        self.record_btn = QPushButton("Record")
        self.pause_btn = QPushButton("Pause")
        self.record_frame_btn = QPushButton("Resume && Pause")  # NEW: Try single frame
        self.save_btn = QPushButton("Save")
        self.quit_btn = QPushButton("Quit")
        
        # FPS control
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(15)
        
        # Add to layout
        toolbar_layout.addWidget(self.record_btn)
        toolbar_layout.addWidget(self.pause_btn)
        toolbar_layout.addWidget(self.record_frame_btn)  # NEW: Add the new button
        toolbar_layout.addWidget(QLabel("Recording FPS:"))
        toolbar_layout.addWidget(self.fps_spin)
        toolbar_layout.addWidget(self.save_btn)
        toolbar_layout.addWidget(self.quit_btn)
        
        return toolbar_layout
    
    def _create_preview_section(self) -> None:
        """Create the preview widget section."""
        self.preview_widget = PreviewWidget()
        controls_layout = self.controls_frame.layout()
        controls_layout.addWidget(self.preview_widget)

    def _create_quality_settings(self) -> None:
        """Create quality settings group."""
        self.quality_groupbox = QGroupBox("Quality Settings")
        quality_layout = QFormLayout()
        
        # Scale setting
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["100%", "75%", "50%", "25%"])
        quality_layout.addRow("Scale:", self.scale_combo)
        
        # Colors setting
        self.colors_combo = QComboBox()
        self.colors_combo.addItems(["256 (Default)", "128", "64", "32"])
        quality_layout.addRow("Colors:", self.colors_combo)
        
        # Frame skipping
        self.skip_frame_spin = QSpinBox()
        self.skip_frame_spin.setRange(1, 20)
        self.skip_frame_spin.setValue(1)
        self.skip_frame_spin.setToolTip("Reduces frame rate (1=all, 2=every second, etc.)")
        quality_layout.addRow("Use every n-th frame:", self.skip_frame_spin)
        
        # NEU: Ähnlichkeits-Erkennung aktivieren/deaktivieren
        self.similarity_check = QCheckBox("Skip similar frames")
        self.similarity_check.setChecked(True)
        self.similarity_check.setToolTip("Automatically skip frames that are very similar to the previous frame")
        quality_layout.addRow(self.similarity_check)
        
        # NEU: Ähnlichkeits-Schwellenwert
        similarity_layout = QHBoxLayout()
        self.similarity_slider = QSlider(Qt.Orientation.Horizontal)
        self.similarity_slider.setRange(85, 99)  # 0.85 bis 0.99
        self.similarity_slider.setValue(95)  # 0.95 default
        self.similarity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.similarity_slider.setTickInterval(5)
        self.similarity_slider.setToolTip("Higher values = more frames skipped (more aggressive)")
        
        self.similarity_label = QLabel("95%")
        self.similarity_slider.valueChanged.connect(
            lambda v: self.similarity_label.setText(f"{v}%")
        )
        
        # Ähnlichkeits-Einstellungen nur aktiv wenn Checkbox aktiviert
        self.similarity_check.toggled.connect(self.similarity_slider.setEnabled)
        self.similarity_check.toggled.connect(self.similarity_label.setEnabled)
        
        similarity_layout.addWidget(self.similarity_slider)
        similarity_layout.addWidget(self.similarity_label)
        quality_layout.addRow("Skip similarity of:", similarity_layout)
        
        # Dithering
        self.dithering_check = QCheckBox("Use Dithering")
        self.dithering_check.setChecked(True)
        quality_layout.addRow(self.dithering_check)
        
        # Disposal method
        self.disposal_combo = QComboBox()
        self.disposal_combo.addItems([
            "No Disposal (0)", "Do Not Dispose (1)",
            "Restore to Background (2)", "Restore to Previous (3)"
        ])
        quality_layout.addRow("Disposal Method:", self.disposal_combo)
        
        # Lossy compression
        lossy_layout = QHBoxLayout()
        self.lossy_level_slider = QSlider(Qt.Orientation.Horizontal)
        self.lossy_level_slider.setRange(0, 10)
        self.lossy_level_slider.setValue(0)
        self.lossy_level_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.lossy_level_slider.setTickInterval(1)
        
        self.lossy_level_label = QLabel("0")
        self.lossy_level_slider.valueChanged.connect(
            lambda v: self.lossy_level_label.setText(str(v))
        )
        
        lossy_layout.addWidget(self.lossy_level_slider)
        lossy_layout.addWidget(self.lossy_level_label)
        quality_layout.addRow("Lossy Compression (0-10):", lossy_layout)
        
        self.quality_groupbox.setLayout(quality_layout)
        controls_layout = self.controls_frame.layout()
        controls_layout.addWidget(self.quality_groupbox)

    def _add_size_grip(self) -> None:
        """Add size grip for window resizing."""
        sizegrip_layout = QHBoxLayout()
        sizegrip_layout.addStretch()
        self.sizegrip = QSizeGrip(self.controls_frame)
        sizegrip_layout.addWidget(self.sizegrip)
        
        controls_layout = self.controls_frame.layout()
        controls_layout.addLayout(sizegrip_layout)
    
    def _connect_signals(self) -> None:
        """Connect all signals to their handlers."""
        # Button connections
        self.record_btn.clicked.connect(self._on_record_clicked)
        self.pause_btn.clicked.connect(self._on_pause_clicked)
        self.record_frame_btn.clicked.connect(self._on_record_frame_clicked)  # NEW
        self.save_btn.clicked.connect(self._on_save_clicked)
        self.quit_btn.clicked.connect(self.confirm_quit)
        
        # Hotkey signal connections
        self.record_signal.connect(self._on_record_clicked)
        self.pause_signal.connect(self._on_pause_clicked)
        self.stop_signal.connect(self._on_stop_clicked)
        self.record_frame_signal.connect(self._on_record_frame_clicked)  # NEW
        
        # Application lifecycle
        QApplication.instance().aboutToQuit.connect(self._cleanup_resources)
    
    def _setup_window(self) -> None:
        """Setup window properties and positioning."""
        self.setWindowTitle("Python GIF Screen Recorder")
        
        # Center on screen
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        x = (screen_geometry.width() - INITIAL_WINDOW_WIDTH) // 2
        y = (screen_geometry.height() - INITIAL_WINDOW_HEIGHT) // 2
        self.setGeometry(x, y, INITIAL_WINDOW_WIDTH, INITIAL_WINDOW_HEIGHT)
        
        # Window flags
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        
        self.show()
    
    def _setup_hotkeys(self) -> None:
        """Setup global hotkeys with error handling."""
        success = self.hotkey_manager.setup()
        self.hotkey_info_label.setText(self.hotkey_manager.status_text)
    
    def _initial_fix(self) -> None:
        """Fix for proper mask application on startup."""
        if not self.frames:
            self.update_mask()


    # NEU: Methoden zum Speichern und Wiederherstellen der Fenstergröße
    def _save_window_size(self) -> None:
        """Speichere die aktuelle Fenstergröße und Position."""
        self._saved_window_size = self.size()
        self._saved_window_pos = self.pos()
    
    def _restore_window_size(self) -> None:
        """Stelle die gespeicherte Fenstergröße wieder her."""
        if self._saved_window_size is not None:
            self.resize(self._saved_window_size)
        if self._saved_window_pos is not None:
            self.move(self._saved_window_pos)

    # Event Handlers
    def _on_record_clicked(self) -> None:
        """Handle record button click."""
        if self._is_closing:
            return
        
        mode = self.recording_manager.mode
        
        if mode == AppMode.EDITING:
            self.clear_frames(confirm=True)
        elif mode == AppMode.READY:
            self._start_recording()
        elif mode in [AppMode.RECORDING, AppMode.PAUSED]:
            self._stop_recording()
    
    def _on_pause_clicked(self) -> None:
        """Handle pause button click."""
        if self._is_closing:
            return
        
        # Spezielle Behandlung für Frame-by-Frame Modus
        if self.recording_manager.is_frame_by_frame_mode:
            # Im Frame-by-Frame Modus bedeutet "Pause" Button-Klick = Resume zu kontinuierlicher Aufnahme
            if self.recording_manager.mode == AppMode.PAUSED:
                self.recording_manager.resume()  # Das setzt auch _frame_by_frame_mode = False
            else:
                self.recording_manager.pause()
        else:
            # Normale Pause/Resume Logik
            self.recording_manager.toggle_pause()
        
        self.ui_manager.update_for_mode(self.recording_manager.mode)
    
    def _on_record_frame_clicked(self) -> None:  # NEW: Handler for single frame recording
        """Handle record frame button click."""
        if self._is_closing:
            return
        
        # Save window size before starting frame-by-frame recording
        if self.recording_manager.mode == AppMode.READY:
            self._save_window_size()
        
        record_rect = self.get_recording_rect()
        
        if self.recording_manager.start_frame_by_frame(record_rect, self.fps_spin.value()):
            self.ui_manager.update_for_mode(self.recording_manager.mode)
    
    def _on_stop_clicked(self) -> None:
        """Handle stop action."""
        if self._is_closing:
            return
        
        if self.recording_manager.mode in [AppMode.RECORDING, AppMode.PAUSED]:
            self._stop_recording()
        elif self.frames:
            self.clear_frames(confirm=True)
    
    def _on_save_clicked(self) -> None:
        """Handle save button click."""
        quality_settings = self._get_quality_settings()
        frames_to_save = self._prepare_frames_for_save(quality_settings)
        
        if not frames_to_save:
            QMessageBox.warning(self, "Error", "No frames to save.")
            return
        
        self._save_gif(frames_to_save, quality_settings)
    
    # Core Recording Logic
    def _start_recording(self) -> None:
        """Start a new recording session."""
        # NEU: Speichere Fenstergröße vor dem Aufnahmestart
        self._save_window_size()
        
        record_rect = self.get_recording_rect()
        
        if self.recording_manager.start(record_rect, self.fps_spin.value()):
            self.ui_manager.update_for_mode(self.recording_manager.mode)
    
    def _stop_recording(self) -> None:
        """Stop the current recording session."""
        self.recording_manager.stop()
        
        if self.frames:
            self.preview_widget.set_frames(self.frames, self.fps_spin.value())
        
        self.ui_manager.update_for_mode(self.recording_manager.mode)
    
    def add_frame(self, image: QImage) -> None:
        """Add a new frame to the recording."""
        self.frames.append(image)
        self.update_status_label()
    
    def clear_frames(self, confirm: bool = True) -> None:
        """Clear all recorded frames."""
        if not self.frames and confirm:
            self.ui_manager.update_for_mode(AppMode.READY)
            return
        
        if confirm and self.frames:
            reply = QMessageBox.question(
                self, "New Recording",
                "Discard current frames and start a new recording session?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        self.frames.clear()
        self.preview_widget.set_frames([], self.fps_spin.value())
        self.recording_manager._mode = AppMode.READY
        self.recording_manager._frame_by_frame_mode = False  # NEW: Reset frame-by-frame mode
        
        # Update UI first
        self.ui_manager.update_for_mode(AppMode.READY)
        
        # NEU: Stelle die gespeicherte Fenstergröße NACH dem UI-Update wieder her
        # Verwende QTimer um sicherzustellen dass es nach adjustSize() passiert
        if self._saved_window_size is not None:
            QTimer.singleShot(10, self._restore_window_size)
    
    # Helper Methods
    def _get_quality_settings(self) -> QualitySettings:
            """Get current quality settings from UI."""
            scale_factors = [1.0, 0.75, 0.5, 0.25]
            color_counts = [256, 128, 64, 32]
            
            return QualitySettings(
                scale_factor=scale_factors[self.scale_combo.currentIndex()],
                num_colors=color_counts[self.colors_combo.currentIndex()],
                use_dithering=self.dithering_check.isChecked(),
                skip_frame=self.skip_frame_spin.value(),
                lossy_level=self.lossy_level_slider.value(),
                disposal_method=self.disposal_combo.currentIndex(),
                # NEU: Ähnlichkeits-Einstellungen
                similarity_threshold=self.similarity_slider.value() / 100.0,  # Convert to 0-1 range
                enable_similarity_skip=self.similarity_check.isChecked()
            )
    
    def _prepare_frames_for_save(self, settings: QualitySettings) -> List[QImage]:
        """Prepare frames for saving based on preview selection."""
        start_index, end_index = self.preview_widget.range_slider.get_values()
        frames = self.frames[start_index : end_index + 1]
        
        if settings.skip_frame > 1:
            frames = frames[::settings.skip_frame]
        
        return frames
    
    def _save_gif(self, frames: List[QImage], settings: QualitySettings) -> None:
            """Save frames as GIF with given settings."""
            fps = self.preview_widget.preview_fps_spin.value()
            
            saved_filename = save_gif_from_frames(
                parent_widget=self,
                frames=frames,
                fps=fps,
                scale_factor=settings.scale_factor,
                num_colors=settings.num_colors,
                use_dithering=settings.use_dithering,
                skip_value=settings.skip_frame,
                lossy_level=settings.lossy_level,
                disposal_method=settings.disposal_method,
                # NEU: Ähnlichkeits-Parameter
                similarity_threshold=settings.similarity_threshold,
                enable_similarity_skip=settings.enable_similarity_skip,
                progress_callback=self._update_save_progress
            )
            
            if saved_filename:
                self.status_label.setText(f"Saved: {saved_filename}")
            else:
                self.update_status_label()
    
    def _update_save_progress(self, value: int) -> None:
        """Update status during GIF saving."""
        self.status_label.setText(f"Saving GIF: Processing frame {value}...")
    
    def update_status_label(self) -> None:
        """Update the status label based on current state."""
        mode = self.recording_manager.mode
        frame_count = len(self.frames)
        
        if mode == AppMode.RECORDING:
            if self.recording_manager.is_frame_by_frame_mode:
                self.status_label.setText(f"Frame-by-frame mode: Recording... ({frame_count} frames)")
            else:
                self.status_label.setText(f"Recording... ({frame_count} frames)")
        elif mode == AppMode.PAUSED:
            if self.recording_manager.is_frame_by_frame_mode:
                self.status_label.setText(f"Frame-by-frame mode: Ready for next frame. ({frame_count} frames)")
            else:
                self.status_label.setText(f"Paused. ({frame_count} frames)")
        elif mode == AppMode.EDITING:
            self.status_label.setText(f"Done. {frame_count} frames. Ready to edit or save.")
        else:  # READY
            rect = self.get_recording_rect()
            if rect.width() > 0 and rect.height() > 0:
                self.status_label.setText(f"Ready. Area: {rect.width()} × {rect.height()}")
            else:
                self.status_label.setText("Please enlarge the window.")
    
    def get_recording_rect(self) -> QRect:
        """Calculate screen coordinates of the recording area."""
        global_pos = self.mapToGlobal(QPoint(0, 0))
        
        # Mehr Sicherheitsabstand hinzufügen
        hole_width = self.width() - (2 * FRAME_THICKNESS) - 2 - (2 * RECORDING_AREA_SAFETY_MARGIN)
        hole_height = self.height() - self.controls_frame.height() - (2 * FRAME_THICKNESS) - 2 - (2 * RECORDING_AREA_SAFETY_MARGIN)
        
        return QRect(
            global_pos.x() + FRAME_THICKNESS + 1 + RECORDING_AREA_SAFETY_MARGIN,
            global_pos.y() + FRAME_THICKNESS + 1 + RECORDING_AREA_SAFETY_MARGIN,
            max(0, hole_width),
            max(0, hole_height)
        )
    
    def update_mask(self) -> None:
        """Create transparent recording area mask."""
        full_window_rgn = QRegion(self.rect())
        hole_width = self.width() - (2 * FRAME_THICKNESS) - 2
        hole_height = self.height() - self.controls_frame.height() - (2 * FRAME_THICKNESS) - 2
        
        if hole_width > 0 and hole_height > 0:
            transparent_hole_rgn = QRegion(
                FRAME_THICKNESS + 1, FRAME_THICKNESS + 1, hole_width, hole_height
            )
            final_mask_rgn = full_window_rgn.subtracted(transparent_hole_rgn)
            self.setMask(final_mask_rgn)
    
    # Qt Event Overrides
    def paintEvent(self, event: QPaintEvent) -> None:
        """Handle window painting."""
        painter = QPainter(self)
        
        if self.recording_manager.mode == AppMode.EDITING:
            painter.fillRect(self.rect(), CONTROLS_BACKGROUND_COLOR)
        else:
            self._paint_recording_frame(painter)
    
    def _paint_recording_frame(self, painter: QPainter) -> None:
        """Paint the red recording frame."""
        painter.fillRect(self.controls_frame.geometry(), CONTROLS_BACKGROUND_COLOR.lighter(120))
        
        recording_area_height = self.height() - self.controls_frame.height()
        
        # Draw frame borders
        painter.fillRect(0, 0, self.width(), FRAME_THICKNESS, FRAME_COLOR)
        painter.fillRect(0, recording_area_height - FRAME_THICKNESS, 
                        self.width(), FRAME_THICKNESS, FRAME_COLOR)
        painter.fillRect(0, FRAME_THICKNESS, FRAME_THICKNESS, 
                        recording_area_height - (2 * FRAME_THICKNESS), FRAME_COLOR)
        painter.fillRect(self.width() - FRAME_THICKNESS, FRAME_THICKNESS, 
                        FRAME_THICKNESS, recording_area_height - (2 * FRAME_THICKNESS), FRAME_COLOR)
    
    def resizeEvent(self, event: QResizeEvent) -> None:
        """Handle window resize."""
        super().resizeEvent(event)
        self.update_status_label()
        
        if self.recording_manager.mode != AppMode.EDITING:
            self.update_mask()
        
        self.update()
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press for window dragging."""
        # Prevent dragging during recording or pause
        if self.recording_manager.mode in [AppMode.RECORDING, AppMode.PAUSED]:
            event.ignore()
            return
        
        if event.button() == Qt.MouseButton.LeftButton:
            if QT_VERSION == 6:
                self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            else:
                self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse move for window dragging."""
        # Prevent dragging during recording or pause
        if self.recording_manager.mode in [AppMode.RECORDING, AppMode.PAUSED]:
            event.ignore()
            return

        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_pos.isNull():
            if QT_VERSION == 6:
                self.move(event.globalPosition().toPoint() - self.drag_pos)
            else:
                self.move(event.globalPos() - self.drag_pos)
            event.accept()
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release."""
        self.drag_pos = QPoint()
        event.accept()
    
    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close."""
        self._is_closing = True
        self._cleanup_resources()
        event.accept()
        QApplication.instance().quit()
    
    def confirm_quit(self) -> None:
        """Show quit confirmation dialog."""
        reply = QMessageBox.question(
            self, "Quit Application",
            "Are you sure you want to quit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.close()
    
    def _cleanup_resources(self) -> None:
        """Clean up all resources."""
        self._is_closing = True
        
        # Stop recording
        if self.recording_manager.timer:
            try:
                self.recording_manager.timer.stop()
                self.recording_manager.timer.wait(3000)
            except Exception as e:
                print(f"Error stopping recording timer: {e}")
        
        # Clean up hotkeys
        self.hotkey_manager.cleanup()
