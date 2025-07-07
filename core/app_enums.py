from enum import Enum

class AppMode(Enum):
    """Application states for better state management."""
    READY = "ready"
    RECORDING = "recording"
    PAUSED = "paused"
    EDITING = "editing"
