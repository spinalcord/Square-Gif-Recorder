from utils.qt_imports import *
from core.data_classes import HotkeyConfig
from managers.config_manager import ConfigManager

class ConfigDialog(QDialog):
    """Dialog for configuring application settings, especially hotkeys."""

    def __init__(self, parent=None, current_config: HotkeyConfig = None):
        super().__init__(parent)
        self.current_config = current_config or HotkeyConfig()
        self._init_ui()
        self._load_current_config()

    def _init_ui(self):
        self.setWindowTitle("Configuration")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Hotkeys group
        hotkey_group = QGroupBox("Hotkeys")
        hotkey_layout = QFormLayout()

        # Create line edits for each hotkey
        self.record_edit = QLineEdit()
        self.record_edit.setPlaceholderText("e.g. <ctrl>+<alt>+r or <cmd>+<alt>+r")
        hotkey_layout.addRow("Record:", self.record_edit)

        self.pause_edit = QLineEdit()
        self.pause_edit.setPlaceholderText("e.g. <ctrl>+<alt>+p")
        hotkey_layout.addRow("Pause:", self.pause_edit)

        self.stop_edit = QLineEdit()
        self.stop_edit.setPlaceholderText("e.g. <ctrl>+<alt>+s")
        hotkey_layout.addRow("Stop:", self.stop_edit)

        self.record_frame_edit = QLineEdit()
        self.record_frame_edit.setPlaceholderText("e.g. <ctrl>+<alt>+f")
        hotkey_layout.addRow("Record Frame:", self.record_frame_edit)

        hotkey_group.setLayout(hotkey_layout)
        layout.addWidget(hotkey_group)

        # Info label
        info_label = QLabel(
            "<b>Available modifiers:</b><br>"
            "<cmd> - Super/Windows/Command key<br>"
            "<ctrl> - Control key<br>"
            "<alt> - Alt key<br>"
            "<shift> - Shift key<br><br>"
            "Example: <cmd>+<ctrl>+r"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Buttons
        button_layout = QHBoxLayout()

        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(self.reset_btn)

        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._on_save)
        self.save_btn.setDefault(True)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

    def _load_current_config(self):
        """Load current hotkey configuration into the line edits."""
        self.record_edit.setText(self.current_config.record)
        self.pause_edit.setText(self.current_config.pause)
        self.stop_edit.setText(self.current_config.stop)
        self.record_frame_edit.setText(self.current_config.record_frame)

    def _reset_to_defaults(self):
        """Reset all hotkeys to default values."""
        default_config = HotkeyConfig()
        self.record_edit.setText(default_config.record)
        self.pause_edit.setText(default_config.pause)
        self.stop_edit.setText(default_config.stop)
        self.record_frame_edit.setText(default_config.record_frame)

    def _on_save(self):
        """Validate and save the configuration."""
        # Basic validation
        record = self.record_edit.text().strip()
        pause = self.pause_edit.text().strip()
        stop = self.stop_edit.text().strip()
        record_frame = self.record_frame_edit.text().strip()

        if not all([record, pause, stop, record_frame]):
            QMessageBox.warning(
                self,
                "Invalid Configuration",
                "All hotkey fields must be filled."
            )
            return

        # Check for duplicates
        hotkeys = [record, pause, stop, record_frame]
        if len(hotkeys) != len(set(hotkeys)):
            QMessageBox.warning(
                self,
                "Invalid Configuration",
                "Hotkeys must be unique."
            )
            return

        self.accept()

    def get_config(self) -> HotkeyConfig:
        """Return the configured HotkeyConfig."""
        return HotkeyConfig(
            record=self.record_edit.text().strip(),
            pause=self.pause_edit.text().strip(),
            stop=self.stop_edit.text().strip(),
            record_frame=self.record_frame_edit.text().strip()
        )