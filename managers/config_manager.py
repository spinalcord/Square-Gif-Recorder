from typing import Optional

from PyQt6.QtCore import QSettings

from utils.qt_imports import *


class ConfigManager:
    """Manages application configuration using QSettings."""

    def __init__(self, organization: str = "GifRecorder", application: str = "ScreenRecorder"):
        """Initialize the config manager with QSettings.

        Args:
            organization: Organization name for settings storage
            application: Application name for settings storage
        """
        self.settings = QSettings(organization, application)

    def save_window_state(self, window: QMainWindow) -> None:
        """Save window geometry and state.

        Args:
            window: Main window instance
        """
        self.settings.beginGroup("Window")
        self.settings.setValue("geometry", window.saveGeometry())
        self.settings.setValue("size", window.size())
        self.settings.setValue("pos", window.pos())
        self.settings.endGroup()

    def restore_window_state(self, window: QMainWindow) -> None:
        """Restore window geometry and state.

        Args:
            window: Main window instance
        """
        self.settings.beginGroup("Window")
        geometry = self.settings.value("geometry")
        if geometry:
            window.restoreGeometry(geometry)
        else:
            # Fallback to size and position if geometry not available
            size = self.settings.value("size")
            pos = self.settings.value("pos")
            if size:
                window.resize(size)
            if pos:
                window.move(pos)
        self.settings.endGroup()

    def save_recording_settings(self, fps: int, mouse_skips: int) -> None:
        """Save recording settings.

        Args:
            fps: Frames per second value
            mouse_skips: Mouse skip frames value
        """
        self.settings.beginGroup("Recording")
        self.settings.setValue("fps", fps)
        self.settings.setValue("mouse_skips", mouse_skips)
        self.settings.endGroup()

    def load_recording_settings(self) -> tuple[int, int]:
        """Load recording settings.

        Returns:
            Tuple of (fps, mouse_skips) with default values if not found
        """
        self.settings.beginGroup("Recording")
        fps = self.settings.value("fps", 15, type=int)
        mouse_skips = self.settings.value("mouse_skips", 0, type=int)
        self.settings.endGroup()
        return fps, mouse_skips

    def save_quality_settings(self,
                              scale_index: int,
                              colors_index: int,
                              skip_frame: int,
                              similarity_enabled: bool,
                              similarity_value: int,
                              dithering_enabled: bool,
                              disposal_index: int,
                              lossy_level: int) -> None:
        """Save quality settings.

        Args:
            scale_index: Scale combo box index
            colors_index: Colors combo box index
            skip_frame: Skip frame spin box value
            similarity_enabled: Similarity check state
            similarity_value: Similarity slider value
            dithering_enabled: Dithering check state
            disposal_index: Disposal method combo box index
            lossy_level: Lossy compression slider value
        """
        self.settings.beginGroup("Quality")
        self.settings.setValue("scale_index", scale_index)
        self.settings.setValue("colors_index", colors_index)
        self.settings.setValue("skip_frame", skip_frame)
        self.settings.setValue("similarity_enabled", similarity_enabled)
        self.settings.setValue("similarity_value", similarity_value)
        self.settings.setValue("dithering_enabled", dithering_enabled)
        self.settings.setValue("disposal_index", disposal_index)
        self.settings.setValue("lossy_level", lossy_level)
        self.settings.endGroup()

    def load_quality_settings(self) -> dict:
        """Load quality settings.

        Returns:
            Dictionary with quality settings and default values if not found
        """
        self.settings.beginGroup("Quality")
        quality_settings = {
            "scale_index": self.settings.value("scale_index", 0, type=int),
            "colors_index": self.settings.value("colors_index", 0, type=int),
            "skip_frame": self.settings.value("skip_frame", 1, type=int),
            "similarity_enabled": self.settings.value("similarity_enabled", True, type=bool),
            "similarity_value": self.settings.value("similarity_value", 95, type=int),
            "dithering_enabled": self.settings.value("dithering_enabled", True, type=bool),
            "disposal_index": self.settings.value("disposal_index", 0, type=int),
            "lossy_level": self.settings.value("lossy_level", 0, type=int)
        }
        self.settings.endGroup()
        return quality_settings

    def save_post_command(self, command: str) -> None:
        """Save post-processing command.

        Args:
            command: Post-processing command text
        """
        self.settings.setValue("PostCommand/command", command)

    def load_post_command(self) -> str:
        """Load post-processing command.

        Returns:
            Post-processing command text or empty string if not found
        """
        return self.settings.value("PostCommand/command", "", type=str)

    def save_all_settings(self, window) -> None:
        """Save all application settings.

        Args:
            window: GifRecorderMainWindow instance
        """
        # Save window state
        self.save_window_state(window)

        # Save recording settings
        self.save_recording_settings(
            window.fps_spin.value(),
            window.mouse_skips_spin.value()
        )

        # Save quality settings
        self.save_quality_settings(
            window.scale_combo.currentIndex(),
            window.colors_combo.currentIndex(),
            window.skip_frame_spin.value(),
            window.similarity_check.isChecked(),
            window.similarity_slider.value(),
            window.dithering_check.isChecked(),
            window.disposal_combo.currentIndex(),
            window.lossy_level_slider.value()
        )

        # Save post command
        self.save_post_command(window.post_command_text_edit.toPlainText())

        # Force write to disk
        self.settings.sync()

    def load_all_settings(self, window) -> None:
        """Load all application settings.

        Args:
            window: GifRecorderMainWindow instance
        """
        # Load recording settings
        fps, mouse_skips = self.load_recording_settings()
        window.fps_spin.setValue(fps)
        window.mouse_skips_spin.setValue(mouse_skips)

        # Load quality settings
        quality = self.load_quality_settings()
        window.scale_combo.setCurrentIndex(quality["scale_index"])
        window.colors_combo.setCurrentIndex(quality["colors_index"])
        window.skip_frame_spin.setValue(quality["skip_frame"])
        window.similarity_check.setChecked(quality["similarity_enabled"])
        window.similarity_slider.setValue(quality["similarity_value"])
        window.dithering_check.setChecked(quality["dithering_enabled"])
        window.disposal_combo.setCurrentIndex(quality["disposal_index"])
        window.lossy_level_slider.setValue(quality["lossy_level"])

        # Load post command
        window.post_command_text_edit.setPlainText(self.load_post_command())

        # Note: Window state is usually loaded before show(), so handle separately

    def clear_all_settings(self) -> None:
        """Clear all saved settings."""
        self.settings.clear()
        self.settings.sync()