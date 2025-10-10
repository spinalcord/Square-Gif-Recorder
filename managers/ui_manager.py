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
        self._update_button_text(mode)
        self._update_tooltips(mode)
        self._update_visibility(is_edit, is_recording)
        self._update_window_properties(is_edit)
        self._update_layout(is_edit)

        self.main_window.update_status_label()
        self.main_window.update()

        # Auto-resize only on specific transitions
        if is_edit != self.main_window._last_mode_was_edit:
            if (self.main_window._saved_window_size is None or
                    (is_edit and not self.main_window._last_mode_was_edit)):
                self.main_window.adjustSize()

        self.main_window._last_mode_was_edit = is_edit

    def _update_button_states(self, mode: AppMode) -> None:
        """Update button states based on mode - buttons keep their names!"""
        mw = self.main_window

        if mode == AppMode.READY:
            # Ready for a new recording
            mw.record_btn.setEnabled(True)
            mw.record_frame_btn.setEnabled(True)
            mw.pause_btn.setEnabled(False)
            mw.stop_btn.setEnabled(False)
            mw.save_btn.setEnabled(False)
            mw.new_btn.setEnabled(bool(mw.frames))  # Only if frames are present
            mw.sizegrip.setEnabled(True)
            mw.sizegrip.setVisible(True)
            mw.mouse_skips_spin.setVisible(True)
            mw.mouse_skips_label.setVisible(True)

        elif mode == AppMode.RECORDING:
            # Recording is in progress
            mw.record_btn.setEnabled(False)  # No new recording during an ongoing one
            mw.pause_btn.setEnabled(True)
            mw.stop_btn.setEnabled(True)
            mw.save_btn.setEnabled(False)
            mw.new_btn.setEnabled(False)
            mw.sizegrip.setEnabled(False)
            mw.sizegrip.setVisible(True)
            mw.mouse_skips_spin.setVisible(False)
            mw.mouse_skips_label.setVisible(False)


        elif mode == AppMode.PAUSED:
            # Recording is paused
            mw.record_btn.setEnabled(False)
            mw.record_frame_btn.setEnabled(True)  # Add single frames
            mw.pause_btn.setEnabled(True)  # Resume is possible
            mw.stop_btn.setEnabled(True)
            mw.save_btn.setEnabled(False)
            mw.new_btn.setEnabled(False)
            mw.sizegrip.setEnabled(False)
            mw.sizegrip.setVisible(True)
            mw.mouse_skips_spin.setVisible(False)
            mw.mouse_skips_label.setVisible(False)

        elif mode == AppMode.EDITING:
            # Frames are available, ready for editing/saving
            mw.record_btn.setEnabled(True)  # New recording is possible
            mw.record_frame_btn.setEnabled(True)
            mw.pause_btn.setEnabled(False)
            mw.stop_btn.setEnabled(False)
            mw.save_btn.setEnabled(True)  # Saving is possible
            mw.new_btn.setEnabled(True)  # Resetting the session is possible
            mw.sizegrip.setEnabled(True)
            mw.sizegrip.setVisible(False)
            mw.mouse_skips_spin.setVisible(False)
            mw.mouse_skips_label.setVisible(False)

    def _update_tooltips(self, mode: AppMode) -> None:
        """Update button tooltips based on current mode."""
        mw = self.main_window

        if mode == AppMode.READY:
            mw.record_btn.setToolTip("Start continuous recording")
            mw.record_frame_btn.setToolTip(
                "Tries to resume/pause this will often result in 1 frame record (Experimental)")
            mw.pause_btn.setToolTip("No recording active")
            mw.stop_btn.setToolTip("No recording active")
            mw.save_btn.setToolTip("No frames to save")
            mw.new_btn.setToolTip("Clear frames and start new session" if mw.frames else "No frames to clear")

        elif mode == AppMode.RECORDING:
            mw.record_btn.setToolTip("Recording in progress - use Stop to finish")

            mw.stop_btn.setToolTip("Stop recording and switch to edit mode")
            mw.save_btn.setToolTip("Stop recording first")
            mw.new_btn.setToolTip("Stop recording first")

        elif mode == AppMode.PAUSED:
            mw.record_btn.setToolTip("Recording paused - resume or stop first")
            mw.record_frame_btn.setToolTip(
                "Tries to resume/pause this will often result in 1 frame record (Experimental)")
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

        # Show tab widget only in edit mode
        mw.edit_tabs.setVisible(is_edit)

        # Stop button: visible only during recording (RECORDING or PAUSED mode)
        mw.stop_btn.setVisible(is_recording)

        # Record button: visible when NOT recording (inverse of stop button)
        mw.record_btn.setVisible(not is_recording and not is_edit)

        # Show recording buttons in all modes except edit mode
        recording_buttons_visible = not is_edit
        mw.record_frame_btn.setVisible(recording_buttons_visible)
        mw.pause_btn.setVisible(recording_buttons_visible)
        mw.config_btn.setVisible(recording_buttons_visible)  # CHANGED: shortcuts_btn -> config_btn

        # Session buttons (Save/New) only visible in edit mode
        mw.save_btn.setVisible(is_edit)
        mw.new_btn.setVisible(is_edit)

        # FPS and Status Label only visible in recording mode (when green frame is visible)
        fps_status_visible = not is_edit
        mw.fps_label.setVisible(fps_status_visible)
        mw.fps_spin.setVisible(fps_status_visible)
        mw.status_label.setVisible(fps_status_visible)

        # FPS setting can only be changed when not recording
        mw.fps_spin.setEnabled(not is_recording)

        # Quit button is always available
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

    def _update_button_text(self, mode: AppMode):
        mw = self.main_window

        if mode == AppMode.READY:
            mw.pause_btn.setText("▮▮")
        elif mode == AppMode.RECORDING:
            mw.pause_btn.setText("▮▮")
        elif mode == AppMode.PAUSED:
            mw.pause_btn.setText("▶")
        elif mode == AppMode.EDITING:
            mw.pause_btn.setText("▮▮")