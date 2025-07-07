from typing import List
from utils.qt_imports import *
from widgets.range_slider import RangeSlider

class PreviewWidget(QWidget):
    """Enhanced preview widget with range slider, navigation slider, and frame deletion."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frames: List[QImage] = []
        self.current_fps = 15
        self.current_frame_index = 0
        
        # Timer for animation
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._next_frame)
        
        self._init_ui()
    
    def _init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        
        # Preview label
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(300, 200)
        self.preview_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        self.preview_label.setText("No frames to preview")
        layout.addWidget(self.preview_label)
        
        # Frame info label
        self.frame_info_label = QLabel("Frame: 0 / 0")
        self.frame_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.frame_info_label)
        
        # Navigation slider (to navigate through frames)
        nav_layout = QHBoxLayout()
        nav_layout.addWidget(QLabel("Navigate:"))
        
        self.nav_slider = QSlider(Qt.Orientation.Horizontal)
        self.nav_slider.setMinimum(0)
        self.nav_slider.setMaximum(0)
        self.nav_slider.setValue(0)
        self.nav_slider.valueChanged.connect(self._on_nav_slider_changed)
        nav_layout.addWidget(self.nav_slider)
        
        # Delete current frame button
        self.delete_frame_btn = QPushButton("Delete Current Frame")
        self.delete_frame_btn.clicked.connect(self._delete_current_frame)
        self.delete_frame_btn.setEnabled(False)
        nav_layout.addWidget(self.delete_frame_btn)
        
        layout.addLayout(nav_layout)
        
        # Range slider for trimming
        trim_layout = QVBoxLayout()
        trim_layout.addWidget(QLabel("Trim Range:"))
        
        self.range_slider = RangeSlider()
        self.range_slider.rangeChanged.connect(self._on_range_changed)
        trim_layout.addWidget(self.range_slider)
        
        # Range info
        self.range_info_label = QLabel("Range: 0 - 0")
        self.range_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        trim_layout.addWidget(self.range_info_label)
        
        layout.addLayout(trim_layout)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self._toggle_animation)
        self.play_btn.setEnabled(False)
        controls_layout.addWidget(self.play_btn)
        
        # FPS control
        controls_layout.addWidget(QLabel("Preview FPS:"))
        self.preview_fps_spin = QSpinBox()
        self.preview_fps_spin.setRange(1, 60)
        self.preview_fps_spin.setValue(15)
        self.preview_fps_spin.valueChanged.connect(self._on_fps_changed)
        controls_layout.addWidget(self.preview_fps_spin)
        
        layout.addLayout(controls_layout)
        
        # For backward compatibility - these properties are now handled by getters
    
    def set_frames(self, frames: List[QImage], fps: int = 15):
        """Set frames and update the preview."""
        self.frames = frames.copy()
        self.current_fps = fps
        self.preview_fps_spin.setValue(fps)
        self.current_frame_index = 0
        
        if self.frames:
            # Update navigation slider
            self.nav_slider.setMaximum(len(self.frames) - 1)
            self.nav_slider.setValue(0)
            
            # Update range slider
            self.range_slider.set_range(0, len(self.frames) - 1)
            self.range_slider.set_values(0, len(self.frames) - 1)
            
            # Update UI state
            self.play_btn.setEnabled(True)
            self.delete_frame_btn.setEnabled(True)
            
            # Show first frame
            self._update_preview()
        else:
            # No frames
            self.nav_slider.setMaximum(0)
            self.range_slider.set_range(0, 0)
            self.play_btn.setEnabled(False)
            self.delete_frame_btn.setEnabled(False)
            self.preview_label.setText("No frames to preview")
            self.frame_info_label.setText("Frame: 0 / 0")
            self.range_info_label.setText("Range: 0 - 0")
        
        self._stop_animation()
    
    def _update_preview(self):
        """Update the preview image."""
        if not self.frames or self.current_frame_index >= len(self.frames):
            return
        
        # Get current frame
        frame = self.frames[self.current_frame_index]
        
        # Scale image to fit preview
        scaled_pixmap = QPixmap.fromImage(frame).scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.preview_label.setPixmap(scaled_pixmap)
        
        # Update frame info
        self.frame_info_label.setText(f"Frame: {self.current_frame_index + 1} / {len(self.frames)}")
    
    def _on_nav_slider_changed(self, value):
        """Handle navigation slider change."""
        if self.frames and 0 <= value < len(self.frames):
            self.current_frame_index = value
            self._update_preview()
    
    def _on_range_changed(self, start, end):
        """Handle range slider change."""
        self.range_info_label.setText(f"Range: {start + 1} - {end + 1}")
    
    def _on_fps_changed(self, fps):
        """Handle FPS change."""
        self.current_fps = fps
        if self.animation_timer.isActive():
            self.animation_timer.setInterval(1000 // fps)
    
    def _toggle_animation(self):
        """Toggle animation playback."""
        if self.animation_timer.isActive():
            self._stop_animation()
        else:
            self._start_animation()
    
    def _start_animation(self):
        """Start animation playback."""
        if not self.frames:
            return
        
        self.animation_timer.setInterval(1000 // self.current_fps)
        self.animation_timer.start()
        self.play_btn.setText("Stop")
    
    def _stop_animation(self):
        """Stop animation playback."""
        self.animation_timer.stop()
        self.play_btn.setText("Play")
    
    def _next_frame(self):
        """Go to next frame in animation."""
        if not self.frames:
            return
        
        start, end = self.range_slider.get_values()
        
        # Only animate within trim range
        if self.current_frame_index >= end:
            self.current_frame_index = start
        else:
            self.current_frame_index += 1
        
        self.nav_slider.setValue(self.current_frame_index)
        self._update_preview()
    
    def _delete_current_frame(self):
        """Delete the current frame."""
        if not self.frames or self.current_frame_index >= len(self.frames):
            return
        
        if len(self.frames) == 1:
            QMessageBox.warning(self, "Delete Frame", "Cannot delete the last frame.")
            return
        
        # Delete the frame
        del self.frames[self.current_frame_index]
        
        # Update navigation - go to previous frame if possible
        if self.current_frame_index > 0:
            self.current_frame_index -= 1
        elif len(self.frames) > 0:
            self.current_frame_index = 0
        
        # Update UI
        if self.frames:
            # Update sliders
            self.nav_slider.setMaximum(len(self.frames) - 1)
            self.nav_slider.setValue(self.current_frame_index)
            
            # Update range slider
            old_start, old_end = self.range_slider.get_values()
            self.range_slider.set_range(0, len(self.frames) - 1)
            
            # Adjust range values if necessary
            new_start = min(old_start, len(self.frames) - 1)
            new_end = min(old_end, len(self.frames) - 1)
            if new_end >= len(self.frames):
                new_end = len(self.frames) - 1
            if new_start > new_end:
                new_start = new_end
            
            self.range_slider.set_values(new_start, new_end)
            
            self._update_preview()
        else:
            # No frames left
            self.set_frames([], self.current_fps)
        
        # Inform parent about frame deletion
        parent = self.parent()
        while parent and not hasattr(parent, 'frames'):
            parent = parent.parent()
        
        if parent and hasattr(parent, 'frames'):
            parent.frames = self.frames.copy()
            if hasattr(parent, 'update_status_label'):
                parent.update_status_label()
    
    # Backward compatibility methods
    @property
    def start_slider(self):
        """Backward compatibility for start_slider."""
        class StartSliderCompat:
            def __init__(self, range_slider):
                self.range_slider = range_slider
            
            def value(self):
                return self.range_slider.get_values()[0]
        
        return StartSliderCompat(self.range_slider)
    
    @property
    def end_slider(self):
        """Backward compatibility for end_slider."""
        class EndSliderCompat:
            def __init__(self, range_slider):
                self.range_slider = range_slider
            
            def value(self):
                return self.range_slider.get_values()[1]
        
        return EndSliderCompat(self.range_slider)