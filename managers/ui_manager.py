from typing import TYPE_CHECKING
from core.app_enums import AppMode
from utils.qt_imports import *

if TYPE_CHECKING:
    from widgets.main_window import GifRecorderMainWindow

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
            mw.record_frame_btn.setEnabled(False)  # Disable in edit mode
        elif mode == AppMode.RECORDING:
            mw.record_btn.setText("Stop")
            mw.record_btn.setToolTip("")
            # Im Frame-by-Frame Modus zeigen wir "Resume" statt "Pause"
            if mw.recording_manager.is_frame_by_frame_mode:
                mw.pause_btn.setText("Resume")
            else:
                mw.pause_btn.setText("Pause")
            mw.record_frame_btn.setEnabled(False)  # Disable during continuous recording
        elif mode == AppMode.PAUSED:
            # In PAUSED mode, immer sowohl Resume als auch Record 1 Frame anzeigen
            mw.pause_btn.setText("Resume")
            mw.record_frame_btn.setVisible(True)   # NEW: Always show when paused
            mw.record_frame_btn.setEnabled(True)
        else:  # READY
            mw.record_btn.setText("Record")
            mw.record_btn.setToolTip("")
            mw.record_frame_btn.setEnabled(True)   # Enable in ready mode
    
    def _update_visibility(self, is_edit: bool, is_recording: bool) -> None:
        """Update widget visibility based on mode."""
        mw = self.main_window
        
        mw.pause_btn.setEnabled(is_recording)
        mw.edit_tabs.setVisible(is_edit) # NEW: Control visibility of the tab widget
        mw.save_btn.setEnabled(is_edit)
        
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
