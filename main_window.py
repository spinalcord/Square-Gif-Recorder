from typing import List, Optional

from utils.qt_imports import *
from utils.constants import *
from core.recording_timer import RecordingTimer
from widgets.preview_widget import PreviewWidget
from utils.gif_saver import save_gif_from_frames

from pynput import keyboard

class GifRecorderMainWindow(QMainWindow):
    """
    The main application window, managing recording state, UI modes, and user interactions.
    """
    # Define signals for hotkey actions to ensure thread-safe GUI updates
    record_signal = pyqtSignal()
    pause_signal = pyqtSignal()
    stop_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.frames: List[QImage] = []
        self.is_recording = False
        self.is_paused = False
        self.record_timer: Optional[RecordingTimer] = None
        self.drag_pos = QPoint()
        self._last_mode_was_edit = True  # Start in "ready" mode, which behaves like edit mode off
        self.hotkey_listener = None  # Initialize as None
        self._is_closing = False  # Flag to prevent hotkey actions during shutdown

        self._init_ui()
        self._update_ui_for_mode()
        self._setup_global_hotkeys()

        QApplication.instance().aboutToQuit.connect(self.on_application_quit)
        self.show()
        # A small fix to ensure the mask is drawn correctly on startup
        QTimer.singleShot(0, self.initial_fix)

    def initial_fix(self):
        """Ensures the mask is correctly applied on first launch."""
        if not self.frames:
            self.update_mask()
            self.update()

    def _init_ui(self):
        self.setWindowTitle("Python GIF Screen Recorder")
        # Center the window on the screen
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        x = (screen_geometry.width() - 500) // 2
        y = (screen_geometry.height() - 720) // 2
        self.setGeometry(x, y, 500, 720)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout(central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # This spacer creates the transparent recording area
        self.recording_area_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.main_layout.addSpacerItem(self.recording_area_spacer)

        # --- Controls Area ---
        self.controls_frame = QWidget()
        controls_layout = QVBoxLayout(self.controls_frame)
        controls_layout.setContentsMargins(10, 10, 10, 10)
        
        # Toolbar
        toolbar_layout = QHBoxLayout()
        self.record_btn = QPushButton("Record")
        self.record_btn.clicked.connect(self.handle_record_button)
        toolbar_layout.addWidget(self.record_btn)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.handle_pause_button)
        toolbar_layout.addWidget(self.pause_btn)

        toolbar_layout.addWidget(QLabel("Recording FPS:"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(15)
        toolbar_layout.addWidget(self.fps_spin)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.handle_save_button)
        toolbar_layout.addWidget(self.save_btn)

        self.quit_btn = QPushButton("Quit")
        self.quit_btn.clicked.connect(self.confirm_quit)
        toolbar_layout.addWidget(self.quit_btn)
        controls_layout.addLayout(toolbar_layout)

        # Status Label
        self.status_label = QLabel("Ready.")
        controls_layout.addWidget(self.status_label)

        # Hotkey Info Label
        self.hotkey_info_label = QLabel("")
        self.hotkey_info_label.setStyleSheet("font-size: 10px; color: gray;")
        controls_layout.addWidget(self.hotkey_info_label)
        
        # Preview Widget
        self.preview_widget = PreviewWidget()
        controls_layout.addWidget(self.preview_widget)
        
        # Quality Settings
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
        self.skip_frame_spin.setToolTip("Reduces frame rate to decrease file size (1=all, 2=every second, etc.)")
        quality_layout.addRow("Use every n-th frame:", self.skip_frame_spin)
        
        self.dithering_check = QCheckBox("Use Dithering")
        self.dithering_check.setChecked(True)
        quality_layout.addRow(self.dithering_check)

        # New: Disposal Method ComboBox
        self.disposal_combo = QComboBox()
        self.disposal_combo.addItems([
            "No Disposal (0)",
            "Do Not Dispose (1)",
            "Restore to Background (2)",
            "Restore to Previous (3)"
        ])
        self.disposal_combo.setCurrentIndex(0) # Default to 0
        quality_layout.addRow("Disposal Method:", self.disposal_combo)

        # New: Lossy Compression Slider
        lossy_layout = QHBoxLayout()
        self.lossy_level_slider = QSlider(Qt.Orientation.Horizontal)
        self.lossy_level_slider.setRange(0, 10)
        self.lossy_level_slider.setValue(0) # Default to no lossy compression
        self.lossy_level_slider.setSingleStep(1)
        self.lossy_level_slider.setPageStep(1)
        self.lossy_level_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.lossy_level_slider.setTickInterval(1)
        self.lossy_level_label = QLabel("0")
        self.lossy_level_slider.valueChanged.connect(lambda value: self.lossy_level_label.setText(str(value)))
        lossy_layout.addWidget(self.lossy_level_slider)
        lossy_layout.addWidget(self.lossy_level_label)
        quality_layout.addRow("Lossy Compression (0-10):", lossy_layout)

        self.quality_groupbox.setLayout(quality_layout)
        controls_layout.addWidget(self.quality_groupbox)

        # Size Grip for resizing
        sizegrip_layout = QHBoxLayout()
        sizegrip_layout.addStretch()
        self.sizegrip = QSizeGrip(self.controls_frame)
        sizegrip_layout.addWidget(self.sizegrip)
        controls_layout.addLayout(sizegrip_layout)
        
        self.main_layout.addWidget(self.controls_frame)

    # --- UI Mode and State Management ---

    def _is_edit_mode(self) -> bool:
        """Determines if the application is in 'edit mode' (post-recording)."""
        return not self.is_recording and len(self.frames) > 0

    def _update_ui_for_mode(self):
        """Switches the UI visibility and properties based on the current mode."""
        is_edit = self._is_edit_mode()
        self.pause_btn.setVisible(self.is_recording)

        if is_edit:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            self.clearMask()
            self.record_btn.setText("New")
            self.record_btn.setToolTip("Discard current frames and start a new recording.")
            self.preview_widget.show()
            self.quality_groupbox.show()
            self.save_btn.show()
            self.fps_spin.setEnabled(True)
            self.save_btn.setEnabled(True)
            if self.main_layout.indexOf(self.recording_area_spacer) != -1:
                self.main_layout.removeItem(self.recording_area_spacer)
        else: # Recording or Ready mode
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.update_mask()
            self.record_btn.setText("Stop" if self.is_recording else "Record")
            self.record_btn.setToolTip("")
            self.preview_widget.hide()
            self.quality_groupbox.hide()
            self.save_btn.hide()
            self.fps_spin.setEnabled(not self.is_recording)
            if self.main_layout.indexOf(self.recording_area_spacer) == -1:
                self.main_layout.insertSpacerItem(0, self.recording_area_spacer)
        
        self.update_status_label()
        self.update() # Force repaint
        
        # Adjust window size if the mode change affects vertical space
        if is_edit != self._last_mode_was_edit:
            self.adjustSize()
        
        self._last_mode_was_edit = is_edit

    # --- Event Handling ---

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        if self._is_edit_mode():
             painter.fillRect(self.rect(), CONTROLS_BACKGROUND_COLOR)
        else:
            # Draw the red recording frame
            # Draw the red recording frame using filled rectangles to ensure no overlap with transparent area
            painter.fillRect(self.controls_frame.geometry(), CONTROLS_BACKGROUND_COLOR.lighter(120))
            
            # Calculate the height of the recording area
            recording_area_height = self.height() - self.controls_frame.height()

            # Draw top bar
            painter.fillRect(0, 0, self.width(), FRAME_THICKNESS, FRAME_COLOR)
            # Draw bottom bar
            painter.fillRect(0, recording_area_height - FRAME_THICKNESS, self.width(), FRAME_THICKNESS, FRAME_COLOR)
            # Draw left bar
            painter.fillRect(0, FRAME_THICKNESS, FRAME_THICKNESS, recording_area_height - (2 * FRAME_THICKNESS), FRAME_COLOR)
            # Draw right bar
            painter.fillRect(self.width() - FRAME_THICKNESS, FRAME_THICKNESS, FRAME_THICKNESS, recording_area_height - (2 * FRAME_THICKNESS), FRAME_COLOR)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self.update_status_label()
        if not self._is_edit_mode():
            self.update_mask()
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # Handle API difference between PyQt5 and PyQt6 for global position
            if QT_VERSION == 6:
                self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            else:
                self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_pos.isNull():
            if QT_VERSION == 6:
                self.move(event.globalPosition().toPoint() - self.drag_pos)
            else:
                self.move(event.globalPos() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.drag_pos = QPoint()
        event.accept()
        
    def closeEvent(self, event: QCloseEvent):
        """Handle window close event with proper cleanup."""
        self._is_closing = True
        self._cleanup_resources()
        event.accept()
        QApplication.instance().quit()

    def confirm_quit(self):
        """Asks the user for confirmation before quitting the application."""
        reply = QMessageBox.question(self, "Quit Application",
                                     "Are you sure you want to quit?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.close()

    def on_application_quit(self):
        """Ensures all resources are cleaned up when the app closes."""
        self._is_closing = True
        self._cleanup_resources()

    def _cleanup_resources(self):
        """Centralized cleanup method for all resources."""
        # Stop recording timer first
        if self.record_timer and self.record_timer.isRunning():
            try:
                self.record_timer.stop()
                self.record_timer.wait(3000)  # Wait max 3 seconds
                self.record_timer = None
            except Exception as e:
                print(f"Error stopping recording timer: {e}")

        # Stop hotkey listener
        if hasattr(self, 'hotkey_listener') and self.hotkey_listener is not None:
            try:
                if hasattr(self.hotkey_listener, 'running') and self.hotkey_listener.running:
                    self.hotkey_listener.stop()
                    # Don't use join() as it can cause deadlocks
                    # The listener thread will terminate gracefully
                self.hotkey_listener = None
            except Exception as e:
                print(f"Error stopping hotkey listener: {e}")

    # --- Button Handlers ---
    
    def handle_record_button(self):
        """Handle record button with safety check for shutdown."""
        if self._is_closing:
            return
            
        if self._is_edit_mode():
            self.clear_frames(confirm=True)
        elif not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def handle_stop_button(self):
        """Handles the stop action, regardless of current mode."""
        if self._is_closing:
            return
            
        if self.is_recording:
            self.stop_recording()
        elif self.frames:
            # If in edit mode with frames, "stop" means clear frames
            self.clear_frames(confirm=True)

    def handle_pause_button(self):
        """Handle pause button with safety check for shutdown."""
        if self._is_closing or not self.is_recording or not self.record_timer:
            return

        self.is_paused = not self.is_paused
        if self.is_paused:
            self.record_timer.pause()
            self.pause_btn.setText("Resume")
        else:
            self.record_timer.resume()
            self.pause_btn.setText("Pause")
        self.update_status_label()

    def handle_save_button(self):
        start_index = self.preview_widget.start_slider.value()
        end_index = self.preview_widget.end_slider.value()
        frames_to_save = self.frames[start_index : end_index + 1]

        skip_value = self.skip_frame_spin.value()
        if skip_value > 1:
            frames_to_save = frames_to_save[::skip_value]

        if not frames_to_save:
            QMessageBox.warning(self, "Error", "The selected range (after skipping frames) is empty.")
            return

        scale_factor = [1.0, 0.75, 0.5, 0.25][self.scale_combo.currentIndex()]
        num_colors = [256, 128, 64, 32][self.colors_combo.currentIndex()]
        use_dithering = self.dithering_check.isChecked()
        fps = self.preview_widget.preview_fps_spin.value()
        
        saved_filename = save_gif_from_frames(
            parent_widget=self,
            frames=frames_to_save,
            fps=fps,
            scale_factor=scale_factor,
            num_colors=num_colors,
            use_dithering=use_dithering,
            skip_value=skip_value,
            lossy_level=self.lossy_level_slider.value(), # Pass the new lossy level
            disposal_method=self.disposal_combo.currentIndex(), # Pass the selected disposal method
            progress_callback=self._update_save_progress
        )
        if saved_filename:
            self.status_label.setText(f"Saved: {saved_filename}")
        else:
            self.update_status_label() # Revert status if save was cancelled or failed

    # --- Core Logic ---

    def start_recording(self):
        record_rect = self.get_recording_rect()
        if record_rect.width() <= 0 or record_rect.height() <= 0:
            QMessageBox.warning(self, "Error", "The recording area is too small.")
            return

        self.clear_frames(confirm=False)
        self.is_recording = True
        self.is_paused = False
        self.pause_btn.setText("Pause")

        self.record_timer = RecordingTimer(record_rect, self.fps_spin.value())
        self.record_timer.frame_captured.connect(self.add_frame)
        self.record_timer.start()
        self._update_ui_for_mode()

    def stop_recording(self):
        if self.record_timer:
            self.record_timer.stop()
            self.record_timer.wait()
            self.record_timer = None
        self.is_recording = False
        self.is_paused = False

        if self.frames:
            self.preview_widget.set_frames(self.frames, self.fps_spin.value())
        
        self._update_ui_for_mode()

    def clear_frames(self, confirm: bool = True):
        if not self.frames:
            # If called with confirm=False, directly switch to ready mode
            if not confirm:
                self._update_ui_for_mode()
            return

        if confirm:
            reply = QMessageBox.question(self, "New Recording",
                "Discard current frames and start a new recording session?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.frames.clear()
        self.preview_widget.set_frames([], self.fps_spin.value())
        self.is_recording = False
        self.is_paused = False
        self._update_ui_for_mode()

    def add_frame(self, image: QImage):
        self.frames.append(image)
        if self.is_recording:
            self.update_status_label()
            
    def _update_save_progress(self, value: int):
        """Updates the status label with GIF saving progress."""
        self.status_label.setText(f"Saving GIF: Processing frame {value}...")

    # --- Helper Methods ---

    def update_mask(self):
        """Creates the transparent 'hole' for the recording area."""
        full_window_rgn = QRegion(self.rect())
        # Shrink the hole by 1 pixel on each side to ensure the frame is never recorded
        hole_width = self.width() - (2 * FRAME_THICKNESS) - 2
        hole_height = self.height() - self.controls_frame.height() - (2 * FRAME_THICKNESS) - 2
        hole_width = max(0, hole_width)
        hole_height = max(0, hole_height)

        transparent_hole_rgn = QRegion(
            FRAME_THICKNESS + 1, FRAME_THICKNESS + 1, hole_width, hole_height
        )
        final_mask_rgn = full_window_rgn.subtracted(transparent_hole_rgn)
        self.setMask(final_mask_rgn)

    def update_status_label(self):
        if self.is_recording:
            status = f"Paused. ({len(self.frames)} frames)" if self.is_paused else f"Recording... ({len(self.frames)} frames)"
            self.status_label.setText(status)
        elif self.frames:
             self.status_label.setText(f"Done. {len(self.frames)} frames. Ready to edit or save.")
        else:
            rect = self.get_recording_rect()
            if rect.width() > 0 and rect.height() > 0:
                self.status_label.setText(f"Ready. Area: {rect.width()} × {rect.height()}")
            else:
                self.status_label.setText("Please enlarge the window.")
                
    def get_recording_rect(self) -> QRect:
        """Calculates the screen coordinates of the transparent recording area."""
        global_pos = self.mapToGlobal(QPoint(0, 0))
        # Shrink the recording rectangle by 1 pixel on each side to ensure the frame is never recorded
        hole_width = self.width() - (2 * FRAME_THICKNESS) - 2
        hole_height = self.height() - self.controls_frame.height() - (2 * FRAME_THICKNESS) - 2
        return QRect(
            global_pos.x() + FRAME_THICKNESS + 1,
            global_pos.y() + FRAME_THICKNESS + 1,
            hole_width,
            hole_height
        )

    # --- Global Hotkey Management ---

    def _setup_global_hotkeys(self):
        """Sets up global hotkeys for record, pause, and stop with error handling."""
        try:
            # Define hotkeys. Using a combination to avoid common single key conflicts.
            record_hotkey = '<ctrl>+<alt>+r'
            pause_hotkey = '<ctrl>+<alt>+p'
            stop_hotkey = '<ctrl>+<alt>+s'

            # Connect signals to the actual handler methods
            self.record_signal.connect(self.handle_record_button)
            self.pause_signal.connect(self.handle_pause_button)
            self.stop_signal.connect(self.handle_stop_button)

            # Create wrapper functions that emit the signals
            def on_record_hotkey():
                if not self._is_closing:
                    self.record_signal.emit()

            def on_pause_hotkey():
                if not self._is_closing:
                    self.pause_signal.emit()

            def on_stop_hotkey():
                if not self._is_closing:
                    self.stop_signal.emit()

            # Create a mapping of hotkeys to their respective wrapper methods
            hotkey_map = {
                record_hotkey: on_record_hotkey,
                pause_hotkey: on_pause_hotkey,
                stop_hotkey: on_stop_hotkey
            }

            # Create a global listener with error handling
            self.hotkey_listener = keyboard.GlobalHotKeys(hotkey_map)
            self.hotkey_listener.start()
            self.hotkey_info_label.setText("Hotkeys: Ctrl+Alt+R (Record), Ctrl+Alt+P (Pause), Ctrl+Alt+S (Stop)")
            
        except Exception as e:
            print(f"Failed to setup global hotkeys: {e}")
            self.hotkey_info_label.setText("Hotkeys disabled (setup failed)")
            self.hotkey_listener = None
        
        self.update_status_label() # Update status label to reflect initial state