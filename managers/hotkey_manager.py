from typing import Optional, TYPE_CHECKING
from pynput import keyboard
from core.data_classes import HotkeyConfig

if TYPE_CHECKING:
    from widgets.main_window import GifRecorderMainWindow



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
