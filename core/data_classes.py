from dataclasses import dataclass

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
    record_frame: str = '<ctrl>+<cmd>+f'  # NEW: Hotkey for single frame recording
