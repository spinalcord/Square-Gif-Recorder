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
        self._update_tooltips(mode)
        self._update_visibility(is_edit, is_recording)
        self._update_window_properties(is_edit)
        self._update_layout(is_edit)
        
        self.main_window.update_status_label()
        self.main_window.update()
        
        # Auto-resize nur bei bestimmten Übergängen
        if is_edit != self.main_window._last_mode_was_edit:
            if (self.main_window._saved_window_size is None or 
                (is_edit and not self.main_window._last_mode_was_edit)):
                self.main_window.adjustSize()
        
        self.main_window._last_mode_was_edit = is_edit
    
    def _update_button_states(self, mode: AppMode) -> None:
        """Update button states based on mode - buttons keep their names!"""
        mw = self.main_window
        
        if mode == AppMode.READY:
            # Bereit für neue Aufnahme
            mw.record_btn.setEnabled(True)
            mw.record_frame_btn.setEnabled(True)
            mw.pause_btn.setEnabled(False)
            mw.stop_btn.setEnabled(False)
            mw.save_btn.setEnabled(False)
            mw.new_btn.setEnabled(bool(mw.frames))  # Nur wenn Frames vorhanden
            
        elif mode == AppMode.RECORDING:
            # Aufnahme läuft
            mw.record_btn.setEnabled(False)  # Keine neue Aufnahme während laufender
            mw.record_frame_btn.setEnabled(mw.recording_manager.is_frame_by_frame_mode)
            mw.pause_btn.setEnabled(True)
            mw.stop_btn.setEnabled(True)
            mw.save_btn.setEnabled(False)
            mw.new_btn.setEnabled(False)
            
        elif mode == AppMode.PAUSED:
            # Aufnahme pausiert
            mw.record_btn.setEnabled(False)
            mw.record_frame_btn.setEnabled(True)  # Einzelframes hinzufügen
            mw.pause_btn.setEnabled(True)  # Resume möglich
            mw.stop_btn.setEnabled(True)
            mw.save_btn.setEnabled(False)
            mw.new_btn.setEnabled(False)
            
        elif mode == AppMode.EDITING:
            # Frames vorhanden, bereit zum Bearbeiten/Speichern
            mw.record_btn.setEnabled(True)   # Neue Aufnahme möglich
            mw.record_frame_btn.setEnabled(True)
            mw.pause_btn.setEnabled(False)
            mw.stop_btn.setEnabled(False)
            mw.save_btn.setEnabled(True)   # Speichern möglich
            mw.new_btn.setEnabled(True)    # Session zurücksetzen möglich
    
    def _update_tooltips(self, mode: AppMode) -> None:
        """Update button tooltips based on current mode."""
        mw = self.main_window
        
        if mode == AppMode.READY:
            mw.record_btn.setToolTip("Start continuous recording")
            mw.record_frame_btn.setToolTip("Start frame-by-frame recording mode")
            mw.pause_btn.setToolTip("No recording active")
            mw.stop_btn.setToolTip("No recording active")
            mw.save_btn.setToolTip("No frames to save")
            mw.new_btn.setToolTip("Clear frames and start new session" if mw.frames else "No frames to clear")
            
        elif mode == AppMode.RECORDING:
            mw.record_btn.setToolTip("Recording in progress - use Stop to finish")
            if mw.recording_manager.is_frame_by_frame_mode:
                mw.record_frame_btn.setToolTip("Add single frame (frame-by-frame mode)")
                mw.pause_btn.setToolTip("Pause frame-by-frame recording")
            else:
                mw.record_frame_btn.setToolTip("Not available during continuous recording")
                mw.pause_btn.setToolTip("Pause continuous recording")
            mw.stop_btn.setToolTip("Stop recording and switch to edit mode")
            mw.save_btn.setToolTip("Stop recording first")
            mw.new_btn.setToolTip("Stop recording first")
            
        elif mode == AppMode.PAUSED:
            mw.record_btn.setToolTip("Recording paused - resume or stop first")
            mw.record_frame_btn.setToolTip("Add single frame while paused")
            mw.pause_btn.setToolTip("Resume recording")
            mw.stop_btn.setToolTip("Stop recording and switch to edit mode")
            mw.save_btn.setToolTip("Stop recording first")
            mw.new_btn.setToolTip("Stop recording first")
            
        elif mode == AppMode.EDITING:
            frame_count = len(mw.frames)
            mw.record_btn.setToolTip("Start new recording (will ask to discard current frames)")
            mw.record_frame_btn.setToolTip("Start new frame-by-frame recording")
            mw.pause_btn.setToolTip("No recording active")
            mw.stop_btn.setToolTip("No recording active")
            mw.save_btn.setToolTip(f"Save {frame_count} frames as GIF")
            mw.new_btn.setToolTip("Discard current frames and start new session")
        
    def _update_visibility(self, is_edit: bool, is_recording: bool) -> None:
        """Update widget visibility based on mode."""
        mw = self.main_window
        
        # Tab-Widget nur im Edit-Modus anzeigen
        mw.edit_tabs.setVisible(is_edit)
        
        # Recording-Buttons in allen Modi außer Edit-Modus anzeigen
        recording_buttons_visible = not is_edit
        mw.record_btn.setVisible(recording_buttons_visible)
        mw.record_frame_btn.setVisible(recording_buttons_visible)
        mw.pause_btn.setVisible(recording_buttons_visible)
        mw.stop_btn.setVisible(recording_buttons_visible)
        mw.shortcuts_btn.setVisible(recording_buttons_visible)
        
        # Session buttons (Save/New) only visible in edit mode
        mw.save_btn.setVisible(is_edit)
        mw.new_btn.setVisible(is_edit)
        
        # FPS and Status Label only visible in recording mode (when green frame is visible)
        fps_status_visible = not is_edit
        mw.fps_label.setVisible(fps_status_visible)
        mw.fps_spin.setVisible(fps_status_visible)
        mw.status_label.setVisible(fps_status_visible)
        
        # FPS-Einstellung nur änderbar wenn nicht aufgenommen wird
        mw.fps_spin.setEnabled(not is_recording)
        
        # Quit-Button immer verfügbar
        mw.quit_btn.setEnabled(True)
        
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