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
    record_signal = pyqtSignal()
    pause_signal = pyqtSignal()
    stop_signal = pyqtSignal()
    record_frame_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        
        self.frames: List[QImage] = []
        self.drag_pos = QPoint()
        self._last_mode_was_edit = True
        self._is_closing = False
        self._saved_window_size: Optional[QSize] = None
        self._saved_window_pos: Optional[QPoint] = None
        
        # Performance optimizations
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._delayed_resize_update)
        self._last_mask_size = QSize()
        self._cached_mask = QRegion()
        
        self.ui_manager = UIManager(self)
        self.recording_manager = RecordingManager(self)
        self.hotkey_manager = HotkeyManager(self, HotkeyConfig())
        
        self._init_ui()
        self._connect_signals()
        self._setup_window()
        self._setup_hotkeys()
        
        self.ui_manager.update_for_mode(AppMode.READY)
        QTimer.singleShot(0, self._initial_fix)

    def _init_ui(self) -> None:
        self._create_central_widget()
        self._create_controls()
        self._create_edit_tabs()
        self._add_size_grip()
    
    def _create_central_widget(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.recording_area_spacer = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )
        self.main_layout.addSpacerItem(self.recording_area_spacer)
    
    def _create_controls(self) -> None:
        self.controls_frame = QWidget()
        controls_layout = QVBoxLayout(self.controls_frame)
        controls_layout.setContentsMargins(10, 10, 10, 10)
        
        toolbar = self._create_toolbar()
        controls_layout.addLayout(toolbar)
        
        self.status_label = QLabel("Ready.")
        controls_layout.addWidget(self.status_label)
        
        self.hotkey_info_label = QLabel("")
        self.hotkey_info_label.setStyleSheet("font-size: 10px; color: gray;")
        self.hotkey_info_label.setWordWrap(True)
        controls_layout.addWidget(self.hotkey_info_label)
        
        self.main_layout.addWidget(self.controls_frame)
    
    def _create_toolbar(self) -> QVBoxLayout:
        toolbar_layout = QVBoxLayout()
        
        self.record_btn = QPushButton("Record")
        self.pause_btn = QPushButton("Pause")
        self.record_frame_btn = QPushButton("Resume && Pause")
        self.save_btn = QPushButton("Save")
        self.quit_btn = QPushButton("Quit")
        
        fps_layout = QHBoxLayout()
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(15)
        fps_layout.addWidget(QLabel("Recording FPS:"))
        fps_layout.addWidget(self.fps_spin)
        
        toolbar_layout.addWidget(self.record_btn)
        toolbar_layout.addWidget(self.pause_btn)
        toolbar_layout.addWidget(self.record_frame_btn)
        
        self.record_frame_spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        toolbar_layout.addItem(self.record_frame_spacer)
        
        toolbar_layout.addLayout(fps_layout)
        toolbar_layout.addWidget(self.save_btn)
        toolbar_layout.addWidget(self.quit_btn)
        
        return toolbar_layout
    
    def _create_edit_tabs(self) -> None:
        self.edit_tabs = QTabWidget()
        
        quality_tab = QWidget()
        quality_tab_layout = QVBoxLayout(quality_tab)
        
        self.quality_groupbox = QGroupBox("Quality Settings")
        quality_layout = QFormLayout()
        
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["100%", "75%", "50%", "25%"])
        quality_layout.addRow("Scale:", self.scale_combo)
        
        self.colors_combo = QComboBox()
        self.colors_combo.addItems(["256 (Default)", "128", "64", "32"])
        quality_layout.addRow("Colors:", self.colors_combo)
        
        self.skip_frame_spin = QSpinBox()
        self.skip_frame_spin.setRange(1, 20)
        self.skip_frame_spin.setValue(1)
        self.skip_frame_spin.setToolTip("Reduces frame rate (1=all, 2=every second, etc.)")
        quality_layout.addRow("Use every n-th frame:", self.skip_frame_spin)
        
        self.similarity_check = QCheckBox("Skip similar frames")
        self.similarity_check.setChecked(True)
        self.similarity_check.setToolTip("Automatically skip frames that are very similar to the previous frame")
        quality_layout.addRow(self.similarity_check)
        
        similarity_layout = QHBoxLayout()
        self.similarity_slider = QSlider(Qt.Orientation.Horizontal)
        self.similarity_slider.setRange(85, 99)
        self.similarity_slider.setValue(95)
        self.similarity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.similarity_slider.setTickInterval(5)
        self.similarity_slider.setToolTip("Higher values = more frames skipped (more aggressive)")
        
        self.similarity_label = QLabel("95%")
        self.similarity_slider.valueChanged.connect(
            lambda v: self.similarity_label.setText(f"{v}%")
        )
        
        self.similarity_check.toggled.connect(self.similarity_slider.setEnabled)
        self.similarity_check.toggled.connect(self.similarity_label.setEnabled)
        
        similarity_layout.addWidget(self.similarity_slider)
        similarity_layout.addWidget(self.similarity_label)
        quality_layout.addRow("Skip similarity of:", similarity_layout)
        
        self.dithering_check = QCheckBox("Use Dithering")
        self.dithering_check.setChecked(True)
        quality_layout.addRow(self.dithering_check)
        
        self.disposal_combo = QComboBox()
        self.disposal_combo.addItems([
            "No Disposal (0)", "Do Not Dispose (1)",
            "Restore to Background (2)", "Restore to Previous (3)"
        ])
        quality_layout.addRow("Disposal Method:", self.disposal_combo)
        
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
        quality_tab_layout.addWidget(self.quality_groupbox)
        self.edit_tabs.addTab(quality_tab, "Quality Settings")

        preview_tab = QWidget()
        preview_layout = QVBoxLayout(preview_tab)
        self.preview_widget = PreviewWidget()
        preview_layout.addWidget(self.preview_widget)
        self.edit_tabs.addTab(preview_tab, "Preview && Trimming")

        self.controls_frame.layout().addWidget(self.edit_tabs)
        self.preview_widget.frame_deleted.connect(self._on_frame_deleted)
        self.preview_widget.frames_updated.connect(self._on_frames_updated)

    def _on_frame_deleted(self, deleted_index: int):
        """Handle frame deletion from preview widget."""
        # Frame was already deleted from preview_widget.frames
        # Just update our own frames list
        self.frames = self.preview_widget.frames.copy()
        self.update_status_label()

    def _on_frames_updated(self, updated_frames: List[QImage]):
        """Handle frames update from preview widget."""
        self.frames = updated_frames.copy()
        self.update_status_label()

    def _add_size_grip(self) -> None:
        sizegrip_layout = QHBoxLayout()
        sizegrip_layout.addStretch()
        self.sizegrip = QSizeGrip(self.controls_frame)
        sizegrip_layout.addWidget(self.sizegrip)
        self.controls_frame.layout().addLayout(sizegrip_layout)

    def _connect_signals(self) -> None:
        self.record_btn.clicked.connect(self._on_record_clicked)
        self.pause_btn.clicked.connect(self._on_pause_clicked)
        self.record_frame_btn.clicked.connect(self._on_record_frame_clicked)
        self.save_btn.clicked.connect(self._on_save_clicked)
        self.quit_btn.clicked.connect(self.confirm_quit)
        
        self.record_signal.connect(self._on_record_clicked)
        self.pause_signal.connect(self._on_pause_clicked)
        self.stop_signal.connect(self._on_stop_clicked)
        self.record_frame_signal.connect(self._on_record_frame_clicked)
        
        QApplication.instance().aboutToQuit.connect(self._cleanup_resources)
    
    def _setup_window(self) -> None:
        self.setWindowTitle("Python GIF Screen Recorder")
        
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        x = (screen_geometry.width() - INITIAL_WINDOW_WIDTH) // 2
        y = (screen_geometry.height() - INITIAL_WINDOW_HEIGHT) // 2
        self.setGeometry(x, y, INITIAL_WINDOW_WIDTH, INITIAL_WINDOW_HEIGHT)
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        
        # Performance optimizations
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_UpdatesDisabled, False)
        
        self.setStyleSheet("QPushButton:disabled { color: #808080; }")
        self.show()
    
    def _setup_hotkeys(self) -> None:
        success = self.hotkey_manager.setup()
        self.hotkey_info_label.setText(self.hotkey_manager.status_text)
    
    def _initial_fix(self) -> None:
        if not self.frames:
            self.update_mask()

    def _save_window_size(self) -> None:
        self._saved_window_size = self.size()
        self._saved_window_pos = self.pos()
    
    def _restore_window_size(self) -> None:
        if self._saved_window_size is not None:
            self.resize(self._saved_window_size)
        if self._saved_window_pos is not None:
            self.move(self._saved_window_pos)

    def _on_record_clicked(self) -> None:
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
        if self._is_closing:
            return
        
        if self.recording_manager.is_frame_by_frame_mode:
            if self.recording_manager.mode == AppMode.PAUSED:
                self.recording_manager.resume()
            else:
                self.recording_manager.pause()
        else:
            self.recording_manager.toggle_pause()
        
        self.ui_manager.update_for_mode(self.recording_manager.mode)
    
    def _on_record_frame_clicked(self) -> None:
        if self._is_closing:
            return
        
        if self.recording_manager.mode == AppMode.READY:
            self._save_window_size()
        
        record_rect = self.get_recording_rect()
        
        if self.recording_manager.start_frame_by_frame(record_rect, self.fps_spin.value()):
            self.ui_manager.update_for_mode(self.recording_manager.mode)
    
    def _on_stop_clicked(self) -> None:
        if self._is_closing:
            return
        
        if self.recording_manager.mode in [AppMode.RECORDING, AppMode.PAUSED]:
            self._stop_recording()
        elif self.frames:
            self.clear_frames(confirm=True)
    
    def _on_save_clicked(self) -> None:
        quality_settings = self._get_quality_settings()
        frames_to_save = self._prepare_frames_for_save(quality_settings)
        
        if not frames_to_save:
            QMessageBox.warning(self, "Error", "No frames to save.")
            return
        
        self._save_gif(frames_to_save, quality_settings)
    
    def _start_recording(self) -> None:
        self._save_window_size()
        record_rect = self.get_recording_rect()
        
        if self.recording_manager.start(record_rect, self.fps_spin.value()):
            self.ui_manager.update_for_mode(self.recording_manager.mode)
    
    def _stop_recording(self) -> None:
        self.recording_manager.stop()
        
        if self.frames:
            self.preview_widget.set_frames(self.frames, self.fps_spin.value())
        
        self.ui_manager.update_for_mode(self.recording_manager.mode)
    
    def add_frame(self, image: QImage) -> None:
        self.frames.append(image)
        self.update_status_label()
    
    def clear_frames(self, confirm: bool = True) -> None:
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
        self.recording_manager._frame_by_frame_mode = False
        
        self.ui_manager.update_for_mode(AppMode.READY)
        
        if self._saved_window_size is not None:
            QTimer.singleShot(10, self._restore_window_size)
    
    def _get_quality_settings(self) -> QualitySettings:
        scale_factors = [1.0, 0.75, 0.5, 0.25]
        color_counts = [256, 128, 64, 32]
        
        return QualitySettings(
            scale_factor=scale_factors[self.scale_combo.currentIndex()],
            num_colors=color_counts[self.colors_combo.currentIndex()],
            use_dithering=self.dithering_check.isChecked(),
            skip_frame=self.skip_frame_spin.value(),
            lossy_level=self.lossy_level_slider.value(),
            disposal_method=self.disposal_combo.currentIndex(),
            similarity_threshold=self.similarity_slider.value() / 100.0,
            enable_similarity_skip=self.similarity_check.isChecked()
        )
    
    def _prepare_frames_for_save(self, settings: QualitySettings) -> List[QImage]:
        start_index, end_index = self.preview_widget.range_slider.get_values()
        frames = self.frames[start_index : end_index + 1]
        
        if settings.skip_frame > 1:
            frames = frames[::settings.skip_frame]
        
        return frames
    
    def _save_gif(self, frames: List[QImage], settings: QualitySettings) -> None:
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
            similarity_threshold=settings.similarity_threshold,
            enable_similarity_skip=settings.enable_similarity_skip,
            progress_callback=self._update_save_progress
        )
        
        if saved_filename:
            self.status_label.setText(f"Saved: {saved_filename}")
        else:
            self.update_status_label()
    
    def _update_save_progress(self, value: int) -> None:
        self.status_label.setText(f"Saving GIF: Processing frame {value}...")
    
    def update_status_label(self) -> None:
        mode = self.recording_manager.mode
        frame_count = len(self.frames)
        
        if mode == AppMode.RECORDING:
            self.status_label.setText(f"Recording... ({frame_count} frames)")
        elif mode == AppMode.PAUSED:
            self.status_label.setText(f"Paused. ({frame_count} frames)")
        elif mode == AppMode.EDITING:
            self.status_label.setText(f"Done. {frame_count} frames. Ready to edit or save.")
        else:
            rect = self.get_recording_rect()
            if rect.width() > 0 and rect.height() > 0:
                self.status_label.setText(f"Ready. Area: {rect.width()} × {rect.height()}")
            else:
                self.status_label.setText("Please enlarge the window.")
    
    def get_recording_rect(self) -> QRect:
        global_pos = self.mapToGlobal(QPoint(0, 0))
        
        hole_width = self.width() - (2 * FRAME_THICKNESS) - 2 - (2 * RECORDING_AREA_SAFETY_MARGIN)
        hole_height = self.height() - self.controls_frame.height() - (2 * FRAME_THICKNESS) - 2 - (2 * RECORDING_AREA_SAFETY_MARGIN)
        
        return QRect(
            global_pos.x() + FRAME_THICKNESS + 1 + RECORDING_AREA_SAFETY_MARGIN,
            global_pos.y() + FRAME_THICKNESS + 1 + RECORDING_AREA_SAFETY_MARGIN,
            max(0, hole_width),
            max(0, hole_height)
        )
    
    def update_mask(self) -> None:
        current_size = self.size()
        
        # Use cached mask if size hasn't changed
        if current_size == self._last_mask_size and not self._cached_mask.isEmpty():
            self.setMask(self._cached_mask)
            return
        
        full_window_rgn = QRegion(self.rect())
        hole_width = self.width() - (2 * FRAME_THICKNESS) - 2
        hole_height = self.height() - self.controls_frame.height() - (2 * FRAME_THICKNESS) - 2
        
        if hole_width > 0 and hole_height > 0:
            transparent_hole_rgn = QRegion(
                FRAME_THICKNESS + 1, FRAME_THICKNESS + 1, hole_width, hole_height
            )
            self._cached_mask = full_window_rgn.subtracted(transparent_hole_rgn)
            self._last_mask_size = current_size
            self.setMask(self._cached_mask)
    
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)  # Disable antialiasing for performance
        
        if self.recording_manager.mode == AppMode.EDITING:
            painter.fillRect(self.rect(), CONTROLS_BACKGROUND_COLOR)
        else:
            self._paint_recording_frame(painter)
    
    def _paint_recording_frame(self, painter: QPainter) -> None:
        painter.fillRect(self.controls_frame.geometry(), CONTROLS_BACKGROUND_COLOR.lighter(120))
        
        recording_area_height = self.height() - self.controls_frame.height()
        
        painter.fillRect(0, 0, self.width(), FRAME_THICKNESS, FRAME_COLOR)
        painter.fillRect(0, recording_area_height - FRAME_THICKNESS, 
                        self.width(), FRAME_THICKNESS, FRAME_COLOR)
        painter.fillRect(0, FRAME_THICKNESS, FRAME_THICKNESS, 
                        recording_area_height - (2 * FRAME_THICKNESS), FRAME_COLOR)
        painter.fillRect(self.width() - FRAME_THICKNESS, FRAME_THICKNESS, 
                        FRAME_THICKNESS, recording_area_height - (2 * FRAME_THICKNESS), FRAME_COLOR)
    
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        
        # Debounce resize updates to reduce lag during scaling
        self._resize_timer.stop()
        self._resize_timer.start(50)  # 50ms delay
    
    def _delayed_resize_update(self) -> None:
        """Delayed update after resize to improve performance"""
        self.update_status_label()
        
        if self.recording_manager.mode != AppMode.EDITING:
            self.update_mask()
        
        self.update()
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
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
        self.drag_pos = QPoint()
        event.accept()
    
    def closeEvent(self, event: QCloseEvent) -> None:
        self._is_closing = True
        self._cleanup_resources()
        event.accept()
        QApplication.instance().quit()
    
    def confirm_quit(self) -> None:
        reply = QMessageBox.question(
            self, "Quit Application",
            "Are you sure you want to quit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.close()
    
    def _cleanup_resources(self) -> None:
        self._is_closing = True
        
        # Stop resize timer
        if hasattr(self, '_resize_timer'):
            self._resize_timer.stop()
        
        if self.recording_manager.timer:
            try:
                self.recording_manager.timer.stop()
                self.recording_manager.timer.wait(3000)
            except Exception as e:
                print(f"Error stopping recording timer: {e}")
        
        self.hotkey_manager.cleanup()