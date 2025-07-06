from typing import List, Optional
from dataclasses import dataclass
from enum import Enum

from utils.qt_imports import *
from utils.constants import *
from core.recording_timer import RecordingTimer
from utils.gif_saver import save_gif_from_frames
from pynput import keyboard


class AppMode(Enum):
    """Application states for better state management."""
    READY = "ready"
    RECORDING = "recording"
    PAUSED = "paused"
    EDITING = "editing"


@dataclass
class QualitySettings:
    """Container for GIF quality settings."""
    scale_factor: float = 1.0
    num_colors: int = 256
    use_dithering: bool = True
    skip_frame: int = 1
    lossy_level: int = 0
    disposal_method: int = 0
    similarity_threshold: float = 0.95
    enable_similarity_skip: bool = True


@dataclass
class HotkeyConfig:
    """Configuration for global hotkeys."""
    record: str = '<ctrl>+<alt>+r'
    pause: str = '<ctrl>+<alt>+p'
    stop: str = '<ctrl>+<alt>+s'
    record_frame: str = '<ctrl>+<alt>+f'  # NEW: Hotkey for single frame recording


class UIManager:
    """Manages UI state transitions and updates."""
    
    def __init__(self, main_window):
        self.main_window = main_window
        
    def update_for_mode(self, mode: AppMode) -> None:
        """Update UI elements based on current application mode."""
        is_edit = mode == AppMode.EDITING
        is_recording = mode in [AppMode.RECORDING, AppMode.PAUSED]
        
        self._update_button_states(mode)
        self._update_visibility(is_edit, is_recording)
        self._update_window_properties(is_edit)
        self._update_layout(is_edit)
        
        self.main_window.update_status_label()
        self.main_window.update()
        
        # NEU: Nur adjustSize() wenn keine gespeicherte Größe existiert
        # oder wenn wir von READY zu EDITING wechseln (nicht von EDITING zu READY)
        if is_edit != self.main_window._last_mode_was_edit:
            # Nur auto-resize wenn wir keine gespeicherte Größe haben
            # oder wenn wir zu EDITING wechseln (nicht von EDITING weg)
            if (self.main_window._saved_window_size is None or 
                (is_edit and not self.main_window._last_mode_was_edit)):
                self.main_window.adjustSize()
        
        self.main_window._last_mode_was_edit = is_edit
    
    def _update_button_states(self, mode: AppMode) -> None:
        """Update button text and states based on mode."""
        mw = self.main_window
        
        if mode == AppMode.EDITING:
            mw.record_btn.setText("New")
            mw.record_btn.setToolTip("Discard current frames and start a new recording.")
            mw.record_frame_btn.setVisible(False)  # NEW: Hide in edit mode
        elif mode == AppMode.RECORDING:
            mw.record_btn.setText("Stop")
            mw.record_btn.setToolTip("")
            # Im Frame-by-Frame Modus zeigen wir "Resume" statt "Pause"
            if mw.recording_manager.is_frame_by_frame_mode:
                mw.pause_btn.setText("Resume")
            else:
                mw.pause_btn.setText("Pause")
            mw.record_frame_btn.setVisible(False)  # NEW: Disable during continuous recording
        elif mode == AppMode.PAUSED:
            # In PAUSED mode, immer sowohl Resume als auch Record 1 Frame anzeigen
            mw.pause_btn.setText("Resume")
            mw.record_frame_btn.setVisible(True)   # NEW: Always show when paused
            mw.record_frame_btn.setEnabled(True)
        else:  # READY
            mw.record_btn.setText("Record")
            mw.record_btn.setToolTip("")
            mw.record_frame_btn.setVisible(True)   # NEW: Show in ready mode
            mw.record_frame_btn.setEnabled(True)
    
    def _update_visibility(self, is_edit: bool, is_recording: bool) -> None:
        """Update widget visibility based on mode."""
        mw = self.main_window
        
        mw.pause_btn.setVisible(is_recording)
        mw.preview_widget.setVisible(is_edit)
        mw.quality_groupbox.setVisible(is_edit)
        mw.save_btn.setVisible(is_edit)
        
        mw.fps_spin.setEnabled(not is_recording)
        mw.save_btn.setEnabled(is_edit)
    
    def _update_window_properties(self, is_edit: bool) -> None:
        """Update window transparency and mask."""
        mw = self.main_window
        
        if is_edit:
            mw.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            mw.clearMask()
        else:
            mw.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            mw.update_mask()
    
    def _update_layout(self, is_edit: bool) -> None:
        """Update layout spacer for recording area."""
        mw = self.main_window
        
        if is_edit:
            if mw.main_layout.indexOf(mw.recording_area_spacer) != -1:
                mw.main_layout.removeItem(mw.recording_area_spacer)
        else:
            if mw.main_layout.indexOf(mw.recording_area_spacer) == -1:
                mw.main_layout.insertSpacerItem(0, mw.recording_area_spacer)


class HotkeyManager:
    """Manages global hotkeys with proper error handling."""
    
    def __init__(self, main_window, config: HotkeyConfig):
        self.main_window = main_window
        self.config = config
        self.listener: Optional[keyboard.GlobalHotKeys] = None
        self._is_active = False
    
    def setup(self) -> bool:
        """Setup global hotkeys. Returns True if successful."""
        try:
            hotkey_map = {
                self.config.record: self._safe_emit_record,
                self.config.pause: self._safe_emit_pause,
                self.config.stop: self._safe_emit_stop,
                self.config.record_frame: self._safe_emit_record_frame  # NEW
            }
            
            self.listener = keyboard.GlobalHotKeys(hotkey_map)
            self.listener.start()
            self._is_active = True
            return True
            
        except Exception as e:
            print(f"Failed to setup global hotkeys: {e}")
            self.listener = None
            self._is_active = False
            return False
    
    def cleanup(self) -> None:
        """Clean up hotkey listener."""
        if self.listener and self._is_active:
            try:
                self.listener.stop()
                self.listener = None
                self._is_active = False
            except Exception as e:
                print(f"Error stopping hotkey listener: {e}")
    
    def _safe_emit_record(self) -> None:
        if not self.main_window._is_closing:
            self.main_window.record_signal.emit()
    
    def _safe_emit_pause(self) -> None:
        if not self.main_window._is_closing:
            self.main_window.pause_signal.emit()
    
    def _safe_emit_stop(self) -> None:
        if not self.main_window._is_closing:
            self.main_window.stop_signal.emit()
    
    def _safe_emit_record_frame(self) -> None:  # NEW
        if not self.main_window._is_closing:
            self.main_window.record_frame_signal.emit()
    
    @property
    def status_text(self) -> str:
        """Get status text for hotkeys."""
        if self._is_active:
            return (f"Hotkeys: {self.config.record} (Record), {self.config.pause} (Pause), "
                   f"{self.config.stop} (Stop), {self.config.record_frame} (Record 1 Frame)")
        return "Hotkeys disabled (setup failed)"


class RecordingManager:
    """Manages recording state and operations."""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.timer: Optional[RecordingTimer] = None
        self._mode = AppMode.READY
        self._frame_by_frame_mode = False  # NEW: Track if we're in frame-by-frame mode
    
    @property
    def mode(self) -> AppMode:
        return self._mode
    
    @property
    def is_frame_by_frame_mode(self) -> bool:  # NEW
        return self._frame_by_frame_mode
    
    def start(self, record_rect: QRect, fps: int) -> bool:
        """Start recording. Returns True if successful."""
        if record_rect.width() <= 0 or record_rect.height() <= 0:
            QMessageBox.warning(self.main_window, "Error", "The recording area is too small.")
            return False
        
        self.main_window.clear_frames(confirm=False)
        self._mode = AppMode.RECORDING
        self._frame_by_frame_mode = False  # NEW: Normal recording mode
        
        self.timer = RecordingTimer(record_rect, fps)
        self.timer.frame_captured.connect(self.main_window.add_frame)
        self.timer.start()
        return True
    
    def start_frame_by_frame(self, record_rect: QRect, fps: int) -> bool:  # NEW
        """Start frame-by-frame recording. Returns True if successful."""
        if record_rect.width() <= 0 or record_rect.height() <= 0:
            QMessageBox.warning(self.main_window, "Error", "The recording area is too small.")
            return False
        
        # Only clear frames if we're starting fresh (not already in frame-by-frame mode)
        if not self._frame_by_frame_mode and self._mode == AppMode.READY:
            self.main_window.clear_frames(confirm=False)
        
        # Always set frame-by-frame mode when this method is called
        self._frame_by_frame_mode = True
        
        # If no timer exists or we're in READY mode, create new timer
        if not self.timer or self._mode == AppMode.READY:
            self.timer = RecordingTimer(record_rect, fps)
            self.timer.frame_captured.connect(self.main_window.add_frame)
            self.timer.start()
            self.timer.pause()  # Immediately pause
            self._mode = AppMode.PAUSED
            
            # Capture the first frame immediately
            QTimer.singleShot(50, self._capture_single_frame)
        elif self._mode == AppMode.PAUSED:
            # Capture one frame by temporarily resuming and pausing again
            self._capture_single_frame()
        
        return True
    
    def _capture_single_frame(self) -> None:  # NEW
        """Capture a single frame by briefly resuming and pausing."""
        if self.timer and self._mode == AppMode.PAUSED:
            # Temporarily resume to capture one frame
            self.timer.resume()
            self._mode = AppMode.RECORDING
            
            # Pause again after a very short time to capture just one frame
            QTimer.singleShot(100, self._pause_after_single_frame)
    
    def _pause_after_single_frame(self) -> None:  # NEW
        """Pause the timer after capturing a single frame."""
        if self.timer and self._mode == AppMode.RECORDING and self._frame_by_frame_mode:
            self.timer.pause()
            self._mode = AppMode.PAUSED
            # WICHTIG: UI nach dem Single-Frame Capture aktualisieren
            self.main_window.ui_manager.update_for_mode(self._mode)
    
    def stop(self) -> None:
        """Stop recording."""
        if self.timer:
            self.timer.stop()
            self.timer.wait()
            self.timer = None
        
        self._frame_by_frame_mode = False  # NEW: Reset frame-by-frame mode
        self._mode = AppMode.EDITING if self.main_window.frames else AppMode.READY
    
    def pause(self) -> None:
        """Pause recording."""
        if self._mode == AppMode.RECORDING and self.timer:
            self.timer.pause()
            self._mode = AppMode.PAUSED
    
    def resume(self) -> None:
        """Resume recording."""
        if self._mode == AppMode.PAUSED and self.timer:
            self.timer.resume()
            self._mode = AppMode.RECORDING
            self._frame_by_frame_mode = False  # NEW: Exit frame-by-frame mode when resuming
    
    def toggle_pause(self) -> None:
        """Toggle between pause and resume."""
        if self._mode == AppMode.RECORDING:
            self.pause()
        elif self._mode == AppMode.PAUSED:
            self.resume()


class RangeSlider(QWidget):
    """Custom Range Slider Widget for trim functionality."""
    
    rangeChanged = pyqtSignal(int, int)  # start, end values
    
    def __init__(self, minimum=0, maximum=100, parent=None):
        super().__init__(parent)
        self.minimum = minimum
        self.maximum = maximum
        self.start_value = minimum
        self.end_value = maximum
        
        self.handle_radius = 8
        self.track_height = 4
        self.active_handle = None  # 'start', 'end', or None
        
        self.setMinimumHeight(30)
        self.setMouseTracking(True)
        
    def set_range(self, minimum, maximum):
        """Set the range of the slider."""
        self.minimum = minimum
        self.maximum = maximum
        self.start_value = max(minimum, min(self.start_value, maximum))
        self.end_value = max(minimum, min(self.end_value, maximum))
        self.update()
        self.rangeChanged.emit(self.start_value, self.end_value)
    
    def set_values(self, start, end):
        """Set the current values."""
        self.start_value = max(self.minimum, min(start, self.maximum))
        self.end_value = max(self.minimum, min(end, self.maximum))
        if self.start_value > self.end_value:
            self.start_value, self.end_value = self.end_value, self.start_value
        self.update()
        self.rangeChanged.emit(self.start_value, self.end_value)
    
    def get_values(self):
        """Get current values."""
        return self.start_value, self.end_value
    
    def value_to_pixel(self, value):
        """Convert value to pixel position."""
        if self.maximum <= self.minimum:
            return self.handle_radius
        
        usable_width = self.width() - 2 * self.handle_radius
        ratio = (value - self.minimum) / (self.maximum - self.minimum)
        return self.handle_radius + ratio * usable_width
    
    def pixel_to_value(self, pixel):
        """Convert pixel position to value."""
        if self.maximum <= self.minimum:
            return self.minimum
        
        usable_width = self.width() - 2 * self.handle_radius
        ratio = (pixel - self.handle_radius) / usable_width
        ratio = max(0, min(1, ratio))
        return int(self.minimum + ratio * (self.maximum - self.minimum))
    
    def get_handle_rect(self, value):
        """Get rectangle for handle at given value."""
        center_x = self.value_to_pixel(value)
        center_y = self.height() // 2
        return QRect(
            int(center_x - self.handle_radius),
            int(center_y - self.handle_radius),
            self.handle_radius * 2,
            self.handle_radius * 2
        )
    
    def paintEvent(self, event):
        """Paint the range slider."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Track background
        track_rect = QRect(
            self.handle_radius,
            self.height() // 2 - self.track_height // 2,
            self.width() - 2 * self.handle_radius,
            self.track_height
        )
        painter.fillRect(track_rect, QColor(200, 200, 200))
        
        # Active range
        start_x = self.value_to_pixel(self.start_value)
        end_x = self.value_to_pixel(self.end_value)
        active_rect = QRect(
            int(start_x),
            self.height() // 2 - self.track_height // 2,
            int(end_x - start_x),
            self.track_height
        )
        painter.fillRect(active_rect, QColor(70, 130, 180))
        
        # Start handle
        start_rect = self.get_handle_rect(self.start_value)
        painter.setBrush(QColor(50, 100, 150))
        painter.setPen(QPen(QColor(30, 80, 130), 2))
        painter.drawEllipse(start_rect)
        
        # End handle
        end_rect = self.get_handle_rect(self.end_value)
        painter.setBrush(QColor(50, 100, 150))
        painter.setPen(QPen(QColor(30, 80, 130), 2))
        painter.drawEllipse(end_rect)
    
    def mousePressEvent(self, event):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            start_rect = self.get_handle_rect(self.start_value)
            end_rect = self.get_handle_rect(self.end_value)
            
            if start_rect.contains(event.pos()):
                self.active_handle = 'start'
            elif end_rect.contains(event.pos()):
                self.active_handle = 'end'
            else:
                # Click on track - move nearest handle
                click_value = self.pixel_to_value(event.pos().x())
                start_dist = abs(click_value - self.start_value)
                end_dist = abs(click_value - self.end_value)
                
                if start_dist < end_dist:
                    self.start_value = click_value
                    self.active_handle = 'start'
                else:
                    self.end_value = click_value
                    self.active_handle = 'end'
                
                self.update()
                self.rangeChanged.emit(self.start_value, self.end_value)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move."""
        if self.active_handle:
            new_value = self.pixel_to_value(event.pos().x())
            
            if self.active_handle == 'start':
                self.start_value = min(new_value, self.end_value)
            elif self.active_handle == 'end':
                self.end_value = max(new_value, self.start_value)
            
            self.update()
            self.rangeChanged.emit(self.start_value, self.end_value)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        self.active_handle = None


class PreviewWidget(QWidget):
    """Enhanced preview widget with range slider, navigation slider, and frame deletion."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frames: List[QImage] = []
        self.current_fps = 15
        self.current_frame_index = 0
        
        # Timer for animation
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._next_frame)
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        
        # Preview label
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(300, 200)
        self.preview_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        self.preview_label.setText("No frames to preview")
        layout.addWidget(self.preview_label)
        
        # Frame info label
        self.frame_info_label = QLabel("Frame: 0 / 0")
        self.frame_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.frame_info_label)
        
        # Navigation slider (to navigate through frames)
        nav_layout = QHBoxLayout()
        nav_layout.addWidget(QLabel("Navigate:"))
        
        self.nav_slider = QSlider(Qt.Orientation.Horizontal)
        self.nav_slider.setMinimum(0)
        self.nav_slider.setMaximum(0)
        self.nav_slider.setValue(0)
        self.nav_slider.valueChanged.connect(self._on_nav_slider_changed)
        nav_layout.addWidget(self.nav_slider)
        
        # Delete current frame button
        self.delete_frame_btn = QPushButton("Delete Current Frame")
        self.delete_frame_btn.clicked.connect(self._delete_current_frame)
        self.delete_frame_btn.setEnabled(False)
        nav_layout.addWidget(self.delete_frame_btn)
        
        layout.addLayout(nav_layout)
        
        # Range slider for trimming
        trim_layout = QVBoxLayout()
        trim_layout.addWidget(QLabel("Trim Range:"))
        
        self.range_slider = RangeSlider()
        self.range_slider.rangeChanged.connect(self._on_range_changed)
        trim_layout.addWidget(self.range_slider)
        
        # Range info
        self.range_info_label = QLabel("Range: 0 - 0")
        self.range_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        trim_layout.addWidget(self.range_info_label)
        
        layout.addLayout(trim_layout)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self._toggle_animation)
        self.play_btn.setEnabled(False)
        controls_layout.addWidget(self.play_btn)
        
        # FPS control
        controls_layout.addWidget(QLabel("Preview FPS:"))
        self.preview_fps_spin = QSpinBox()
        self.preview_fps_spin.setRange(1, 60)
        self.preview_fps_spin.setValue(15)
        self.preview_fps_spin.valueChanged.connect(self._on_fps_changed)
        controls_layout.addWidget(self.preview_fps_spin)
        
        layout.addLayout(controls_layout)
        
        # For backward compatibility - these properties are now handled by getters
    
    def set_frames(self, frames: List[QImage], fps: int = 15):
        """Set frames and update the preview."""
        self.frames = frames.copy()
        self.current_fps = fps
        self.preview_fps_spin.setValue(fps)
        self.current_frame_index = 0
        
        if self.frames:
            # Update navigation slider
            self.nav_slider.setMaximum(len(self.frames) - 1)
            self.nav_slider.setValue(0)
            
            # Update range slider
            self.range_slider.set_range(0, len(self.frames) - 1)
            self.range_slider.set_values(0, len(self.frames) - 1)
            
            # Update UI state
            self.play_btn.setEnabled(True)
            self.delete_frame_btn.setEnabled(True)
            
            # Show first frame
            self._update_preview()
        else:
            # No frames
            self.nav_slider.setMaximum(0)
            self.range_slider.set_range(0, 0)
            self.play_btn.setEnabled(False)
            self.delete_frame_btn.setEnabled(False)
            self.preview_label.setText("No frames to preview")
            self.frame_info_label.setText("Frame: 0 / 0")
            self.range_info_label.setText("Range: 0 - 0")
        
        self._stop_animation()
    
    def _update_preview(self):
        """Update the preview image."""
        if not self.frames or self.current_frame_index >= len(self.frames):
            return
        
        # Get current frame
        frame = self.frames[self.current_frame_index]
        
        # Scale image to fit preview
        scaled_pixmap = QPixmap.fromImage(frame).scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.preview_label.setPixmap(scaled_pixmap)
        
        # Update frame info
        self.frame_info_label.setText(f"Frame: {self.current_frame_index + 1} / {len(self.frames)}")
    
    def _on_nav_slider_changed(self, value):
        """Handle navigation slider change."""
        if self.frames and 0 <= value < len(self.frames):
            self.current_frame_index = value
            self._update_preview()
    
    def _on_range_changed(self, start, end):
        """Handle range slider change."""
        self.range_info_label.setText(f"Range: {start + 1} - {end + 1}")
    
    def _on_fps_changed(self, fps):
        """Handle FPS change."""
        self.current_fps = fps
        if self.animation_timer.isActive():
            self.animation_timer.setInterval(1000 // fps)
    
    def _toggle_animation(self):
        """Toggle animation playback."""
        if self.animation_timer.isActive():
            self._stop_animation()
        else:
            self._start_animation()
    
    def _start_animation(self):
        """Start animation playback."""
        if not self.frames:
            return
        
        self.animation_timer.setInterval(1000 // self.current_fps)
        self.animation_timer.start()
        self.play_btn.setText("Stop")
    
    def _stop_animation(self):
        """Stop animation playback."""
        self.animation_timer.stop()
        self.play_btn.setText("Play")
    
    def _next_frame(self):
        """Go to next frame in animation."""
        if not self.frames:
            return
        
        start, end = self.range_slider.get_values()
        
        # Only animate within trim range
        if self.current_frame_index >= end:
            self.current_frame_index = start
        else:
            self.current_frame_index += 1
        
        self.nav_slider.setValue(self.current_frame_index)
        self._update_preview()
    
    def _delete_current_frame(self):
        """Delete the current frame."""
        if not self.frames or self.current_frame_index >= len(self.frames):
            return
        
        if len(self.frames) == 1:
            QMessageBox.warning(self, "Delete Frame", "Cannot delete the last frame.")
            return
        
        # Delete the frame
        del self.frames[self.current_frame_index]
        
        # Update navigation - go to previous frame if possible
        if self.current_frame_index > 0:
            self.current_frame_index -= 1
        elif len(self.frames) > 0:
            self.current_frame_index = 0
        
        # Update UI
        if self.frames:
            # Update sliders
            self.nav_slider.setMaximum(len(self.frames) - 1)
            self.nav_slider.setValue(self.current_frame_index)
            
            # Update range slider
            old_start, old_end = self.range_slider.get_values()
            self.range_slider.set_range(0, len(self.frames) - 1)
            
            # Adjust range values if necessary
            new_start = min(old_start, len(self.frames) - 1)
            new_end = min(old_end, len(self.frames) - 1)
            if new_end >= len(self.frames):
                new_end = len(self.frames) - 1
            if new_start > new_end:
                new_start = new_end
            
            self.range_slider.set_values(new_start, new_end)
            
            self._update_preview()
        else:
            # No frames left
            self.set_frames([], self.current_fps)
        
        # Inform parent about frame deletion
        parent = self.parent()
        while parent and not hasattr(parent, 'frames'):
            parent = parent.parent()
        
        if parent and hasattr(parent, 'frames'):
            parent.frames = self.frames.copy()
            if hasattr(parent, 'update_status_label'):
                parent.update_status_label()
    
    # Backward compatibility methods
    @property
    def start_slider(self):
        """Backward compatibility for start_slider."""
        class StartSliderCompat:
            def __init__(self, range_slider):
                self.range_slider = range_slider
            
            def value(self):
                return self.range_slider.get_values()[0]
        
        return StartSliderCompat(self.range_slider)
    
    @property
    def end_slider(self):
        """Backward compatibility for end_slider."""
        class EndSliderCompat:
            def __init__(self, range_slider):
                self.range_slider = range_slider
            
            def value(self):
                return self.range_slider.get_values()[1]
        
        return EndSliderCompat(self.range_slider)


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
        self._last_mode_was_edit = True
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
        self.record_frame_btn = QPushButton("Record 1 Frame")  # NEW: Single frame recording button
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
        x = (screen_geometry.width() - 500) // 2
        y = (screen_geometry.height() - 720) // 2
        self.setGeometry(x, y, 500, 720)
        
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
            self.update()

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
        safety_margin = 3  # Zusätzliche Pixel Abstand
        
        hole_width = self.width() - (2 * FRAME_THICKNESS) - 2 - (2 * safety_margin)
        hole_height = self.height() - self.controls_frame.height() - (2 * FRAME_THICKNESS) - 2 - (2 * safety_margin)
        
        return QRect(
            global_pos.x() + FRAME_THICKNESS + 1 + safety_margin,
            global_pos.y() + FRAME_THICKNESS + 1 + safety_margin,
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