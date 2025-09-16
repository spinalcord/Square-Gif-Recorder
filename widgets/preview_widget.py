from typing import List, Optional
from utils.qt_imports import *
from widgets.range_slider import RangeSlider

class PreviewWidget(QWidget):
    """Enhanced preview widget with range slider, navigation slider, and frame deletion."""
    
    # Signals for better communication
    frame_deleted = pyqtSignal(int)  # Emits deleted frame index
    frames_updated = pyqtSignal(list)  # Emits updated frames list
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frames: List[QImage] = []
        self.current_fps = 15
        self.current_frame_index = 0
        
        # Performance optimizations
        self._cached_pixmaps: dict[int, QPixmap] = {}  # Cache scaled pixmaps
        self._last_preview_size = QSize()
        self._update_timer = QTimer()  # Debounce updates
        self._update_timer.setSingleShot(True)
        self._update_timer.timeout.connect(self._delayed_update_preview)
        
        # Animation timer
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._next_frame)
        
        # Track if we're in the middle of updating to prevent recursive calls
        self._updating = False
        
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # Preview label with better sizing
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(400, 300)  # Larger minimum size
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, 
            QSizePolicy.Policy.Expanding
        )
        self.preview_label.setStyleSheet("""
            QLabel {
                border: 2px solid #cccccc; 
                background-color: #f8f8f8;
                border-radius: 4px;
            }
        """)
        self.preview_label.setText("No frames to preview")
        layout.addWidget(self.preview_label)
        
        # Frame info with better formatting
        self.frame_info_label = QLabel("Frame: 0 / 0")
        self.frame_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_info_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(self.frame_info_label)
        
        # Navigation controls in a group box
        nav_group = QGroupBox("Navigation")
        nav_layout = QVBoxLayout(nav_group)
        
        # Navigation slider with better labeling
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel("Frame:"))
        
        self.nav_slider = QSlider(Qt.Orientation.Horizontal)
        self.nav_slider.setMinimum(0)
        self.nav_slider.setMaximum(0)
        self.nav_slider.setValue(0)
        self.nav_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.nav_slider.setTickInterval(10)
        slider_layout.addWidget(self.nav_slider)
        
        nav_layout.addLayout(slider_layout)
        
        # Navigation buttons
        nav_buttons_layout = QHBoxLayout()
        
        self.first_frame_btn = QPushButton("◀◀")
        self.first_frame_btn.setMaximumWidth(40)
        self.first_frame_btn.setToolTip("First frame")
        
        self.prev_frame_btn = QPushButton("◀")
        self.prev_frame_btn.setMaximumWidth(40)
        self.prev_frame_btn.setToolTip("Previous frame")
        
        self.next_frame_btn = QPushButton("▶")
        self.next_frame_btn.setMaximumWidth(40)
        self.next_frame_btn.setToolTip("Next frame")
        
        self.last_frame_btn = QPushButton("▶▶")
        self.last_frame_btn.setMaximumWidth(40)
        self.last_frame_btn.setToolTip("Last frame")
        
        self.delete_frame_btn = QPushButton("🗑 Delete Current Frame")
        self.delete_frame_btn.setStyleSheet("QPushButton { color: #d32f2f; }")
        
        nav_buttons_layout.addWidget(self.first_frame_btn)
        nav_buttons_layout.addWidget(self.prev_frame_btn)
        nav_buttons_layout.addWidget(self.next_frame_btn)
        nav_buttons_layout.addWidget(self.last_frame_btn)
        nav_buttons_layout.addStretch()
        nav_buttons_layout.addWidget(self.delete_frame_btn)
        
        nav_layout.addLayout(nav_buttons_layout)
        layout.addWidget(nav_group)
        
        # Range slider for trimming
        trim_group = QGroupBox("Trim Range")
        trim_layout = QVBoxLayout(trim_group)
        
        self.range_slider = RangeSlider()
        trim_layout.addWidget(self.range_slider)
        
        # Range info with start/end labels
        range_info_layout = QHBoxLayout()
        self.range_start_label = QLabel("Start: 1")
        self.range_end_label = QLabel("End: 1")
        self.range_duration_label = QLabel("Duration: 0.0s")
        
        range_info_layout.addWidget(self.range_start_label)
        range_info_layout.addStretch()
        range_info_layout.addWidget(self.range_duration_label)
        range_info_layout.addStretch()
        range_info_layout.addWidget(self.range_end_label)
        
        trim_layout.addLayout(range_info_layout)
        layout.addWidget(trim_group)
        
        # Playback controls
        controls_group = QGroupBox("Playback Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setEnabled(False)
        controls_layout.addWidget(self.play_btn)
        
        # FPS control with better styling
        controls_layout.addWidget(QLabel("Preview FPS:"))
        self.preview_fps_spin = QSpinBox()
        self.preview_fps_spin.setRange(1, 60)
        self.preview_fps_spin.setValue(15)
        self.preview_fps_spin.setSuffix(" fps")
        controls_layout.addWidget(self.preview_fps_spin)
        
        # Loop option
        self.loop_check = QCheckBox("Loop")
        self.loop_check.setChecked(True)
        controls_layout.addWidget(self.loop_check)
        
        controls_layout.addStretch()
        layout.addWidget(controls_group)
        
        # Initially disable all controls
        self._set_controls_enabled(False)
    
    def _connect_signals(self):
        """Connect all signals to their handlers."""
        self.nav_slider.valueChanged.connect(self._on_nav_slider_changed)
        self.range_slider.rangeChanged.connect(self._on_range_changed)
        self.preview_fps_spin.valueChanged.connect(self._on_fps_changed)
        self.play_btn.clicked.connect(self._toggle_animation)
        
        # Navigation buttons
        self.first_frame_btn.clicked.connect(lambda: self._go_to_frame(0))
        self.prev_frame_btn.clicked.connect(self._go_to_previous_frame)
        self.next_frame_btn.clicked.connect(self._go_to_next_frame)
        self.last_frame_btn.clicked.connect(lambda: self._go_to_frame(len(self.frames) - 1))
        self.delete_frame_btn.clicked.connect(self._delete_current_frame)
    
    def set_frames(self, frames: List[QImage], fps: int = 15):
        """Set frames and update the preview."""
        if self._updating:
            return
            
        self._updating = True
        
        # Clear cache when frames change
        self._clear_pixmap_cache()
        
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
            self._set_controls_enabled(True)
            
            # Show first frame
            self._update_preview_immediate()
        else:
            # No frames
            self.nav_slider.setMaximum(0)
            self.range_slider.set_range(0, 0)
            self._set_controls_enabled(False)
            self.preview_label.setText("No frames to preview")
            self.frame_info_label.setText("Frame: 0 / 0")
            self._update_range_info(0, 0)
        
        self._stop_animation()
        self._updating = False
    
    def _set_controls_enabled(self, enabled: bool):
        """Enable/disable all controls based on frame availability."""
        self.play_btn.setEnabled(enabled)
        self.delete_frame_btn.setEnabled(enabled)
        self.first_frame_btn.setEnabled(enabled)
        self.prev_frame_btn.setEnabled(enabled)
        self.next_frame_btn.setEnabled(enabled)
        self.last_frame_btn.setEnabled(enabled)
        self.nav_slider.setEnabled(enabled)
    
    def _clear_pixmap_cache(self):
        """Clear the pixmap cache to free memory."""
        self._cached_pixmaps.clear()
    
    def _get_cached_pixmap(self, frame_index: int) -> Optional[QPixmap]:
        """Get cached pixmap for frame, creating if necessary."""
        if frame_index not in self._cached_pixmaps:
            if frame_index < len(self.frames):
                current_size = self.preview_label.size()
                
                # Only cache if size hasn't changed
                if current_size == self._last_preview_size:
                    frame = self.frames[frame_index]
                    scaled_pixmap = QPixmap.fromImage(frame).scaled(
                        current_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self._cached_pixmaps[frame_index] = scaled_pixmap
                    return scaled_pixmap
                else:
                    # Size changed, clear cache and update
                    self._clear_pixmap_cache()
                    self._last_preview_size = current_size
                    return None
        
        return self._cached_pixmaps.get(frame_index)
    
    def _update_preview_immediate(self):
        """Immediately update the preview image."""
        if not self.frames or self.current_frame_index >= len(self.frames):
            return
        
        # Try to get cached pixmap first
        pixmap = self._get_cached_pixmap(self.current_frame_index)
        
        if pixmap is None:
            # Create new pixmap
            frame = self.frames[self.current_frame_index]
            pixmap = QPixmap.fromImage(frame).scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        
        self.preview_label.setPixmap(pixmap)
        
        # Update frame info
        self.frame_info_label.setText(
            f"Frame: {self.current_frame_index + 1} / {len(self.frames)}"
        )
    
    def _update_preview(self):
        """Debounced preview update."""
        self._update_timer.stop()
        self._update_timer.start(16)  # ~60fps update limit
    
    def _delayed_update_preview(self):
        """Delayed preview update for performance."""
        self._update_preview_immediate()
    
    def _go_to_frame(self, frame_index: int):
        """Navigate to specific frame."""
        if self.frames and 0 <= frame_index < len(self.frames):
            self.current_frame_index = frame_index
            self.nav_slider.setValue(frame_index)
            self._update_preview_immediate()
    
    def _go_to_previous_frame(self):
        """Navigate to previous frame."""
        if self.current_frame_index > 0:
            self._go_to_frame(self.current_frame_index - 1)
    
    def _go_to_next_frame(self):
        """Navigate to next frame."""
        if self.current_frame_index < len(self.frames) - 1:
            self._go_to_frame(self.current_frame_index + 1)
    
    def _on_nav_slider_changed(self, value):
        """Handle navigation slider change."""
        if not self._updating and self.frames and 0 <= value < len(self.frames):
            self.current_frame_index = value
            self._update_preview()
    
    def _on_range_changed(self, start, end):
        """Handle range slider change."""
        self._update_range_info(start, end)
    
    def _update_range_info(self, start: int, end: int):
        """Update range information labels."""
        self.range_start_label.setText(f"Start: {start + 1}")
        self.range_end_label.setText(f"End: {end + 1}")
        
        if self.current_fps > 0:
            duration = (end - start + 1) / self.current_fps
            self.range_duration_label.setText(f"Duration: {duration:.1f}s")
        else:
            self.range_duration_label.setText("Duration: 0.0s")
    
    def _on_fps_changed(self, fps):
        """Handle FPS change."""
        self.current_fps = fps
        if self.animation_timer.isActive():
            self.animation_timer.setInterval(1000 // fps)
        
        # Update duration display
        start, end = self.range_slider.get_values()
        self._update_range_info(start, end)
    
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
        self.play_btn.setText("▮▮")
    
    def _stop_animation(self):
        """Stop animation playback."""
        self.animation_timer.stop()
        self.play_btn.setText("▶ Play")
    
    def _next_frame(self):
        """Go to next frame in animation."""
        if not self.frames:
            return
        
        start, end = self.range_slider.get_values()
        
        # Only animate within trim range
        if self.current_frame_index >= end:
            if self.loop_check.isChecked():
                self.current_frame_index = start
            else:
                self._stop_animation()
                return
        else:
            self.current_frame_index += 1
        
        self.nav_slider.setValue(self.current_frame_index)
        self._update_preview_immediate()
    
    def _delete_current_frame(self):
        """Delete the current frame with improved feedback."""
        if not self.frames or self.current_frame_index >= len(self.frames):
            return
        
        if len(self.frames) == 1:
            QMessageBox.warning(self, "Delete Frame", 
                              "Cannot delete the last frame.\nAt least one frame is required.")
            return
        
        # Confirm deletion for safety
        reply = QMessageBox.question(
            self, "Delete Frame",
            f"Delete frame {self.current_frame_index + 1} of {len(self.frames)}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        deleted_index = self.current_frame_index
        
        # Remove from cache first
        if deleted_index in self._cached_pixmaps:
            del self._cached_pixmaps[deleted_index]
        
        # Shift cache indices
        new_cache = {}
        for idx, pixmap in self._cached_pixmaps.items():
            if idx > deleted_index:
                new_cache[idx - 1] = pixmap
            elif idx < deleted_index:
                new_cache[idx] = pixmap
        self._cached_pixmaps = new_cache
        
        # Delete the frame
        del self.frames[deleted_index]
        
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
            
            self._update_preview_immediate()
        else:
            # No frames left
            self.set_frames([], self.current_fps)
        
        # Emit signals for parent to handle
        self.frame_deleted.emit(deleted_index)
        self.frames_updated.emit(self.frames)
    
    def resizeEvent(self, event):
        """Handle resize events by clearing pixmap cache."""
        super().resizeEvent(event)
        # Clear cache on resize as pixmap sizes are no longer valid
        self._clear_pixmap_cache()
        if self.frames:
            self._update_preview()
    
    # Backward compatibility methods (improved)
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