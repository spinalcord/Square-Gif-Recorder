from typing import Optional, TYPE_CHECKING
from utils.qt_imports import *
from core.app_enums import AppMode
from core.recording_timer import RecordingTimer

if TYPE_CHECKING:
    from widgets.main_window import GifRecorderMainWindow

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
            QTimer.singleShot(50, self.record_single_frame)
        elif self._mode == AppMode.PAUSED:
            # Capture one frame by temporarily resuming and pausing again
            self.record_single_frame()
        
        return True
    
    def record_single_frame(self) -> None:  # NEW
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
