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

    @property
    def mode(self) -> AppMode:
        return self._mode

    def start(self, record_rect: QRect, fps: int, mouse_skips: int = 0) -> bool:
        """Start recording. Returns True if successful."""
        if record_rect.width() <= 0 or record_rect.height() <= 0:
            QMessageBox.warning(self.main_window, "Error", "The recording area is too small.")
            return False
        
        self.main_window.clear_frames(confirm=False)
        self._mode = AppMode.RECORDING

        self.timer = RecordingTimer(record_rect, fps, mouse_skips)
        self.timer.frame_captured.connect(self.main_window.add_frame)
        self.timer.start()
        return True
    
    def stop(self) -> None:
        """Stop recording."""
        if self.timer:
            self.timer.stop()
            self.timer.wait()
            self.timer = None
        
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

    def toggle_pause(self) -> None:
        """Toggle between pause and resume."""
        if self._mode == AppMode.RECORDING:
            self.pause()
        elif self._mode == AppMode.PAUSED:
            self.resume()
