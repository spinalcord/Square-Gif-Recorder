# widgets/preview_widget.py

from typing import List
from utils.qt_imports import *

class PreviewWidget(QWidget):
    """
    A widget to preview the recorded frames, trim them, and adjust playback speed.
    """
    def __init__(self):
        super().__init__()
        self.frames: List[QImage] = []
        self.current_frame_index = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)

        self._init_ui()
        self.update_fps()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 5, 0, 0)

        self.preview_label = QLabel("Preview will be displayed here after recording.")
        self.preview_label.setMinimumSize(300, 150)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_label.setStyleSheet("border: 1px solid gray; background-color: black; color: white;")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.preview_label)

        # Playback controls
        playback_controls = QHBoxLayout()
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self.toggle_preview)
        playback_controls.addWidget(self.play_btn)

        self.frame_label = QLabel("Frame: 0/0")
        playback_controls.addWidget(self.frame_label)

        playback_controls.addWidget(QLabel("Speed:"))
        self.preview_fps_spin = QSpinBox()
        self.preview_fps_spin.setRange(1, 60)
        self.preview_fps_spin.setValue(10)
        self.preview_fps_spin.valueChanged.connect(self.update_fps)
        playback_controls.addWidget(self.preview_fps_spin)
        layout.addLayout(playback_controls)

        # Trimming controls
        self.trim_groupbox = QGroupBox("Trim GIF")
        trim_layout = QGridLayout()
        trim_layout.addWidget(QLabel("Start:"), 0, 0)
        self.start_slider = QSlider(Qt.Orientation.Horizontal)
        self.start_slider.valueChanged.connect(self.update_trim_range)
        self.start_slider.sliderPressed.connect(self.stop_timer_on_drag)
        trim_layout.addWidget(self.start_slider, 0, 1)
        self.start_label = QLabel("0")
        trim_layout.addWidget(self.start_label, 0, 2)

        trim_layout.addWidget(QLabel("End:"), 1, 0)
        self.end_slider = QSlider(Qt.Orientation.Horizontal)
        self.end_slider.valueChanged.connect(self.update_trim_range)
        self.end_slider.sliderPressed.connect(self.stop_timer_on_drag)
        trim_layout.addWidget(self.end_slider, 1, 1)
        self.end_label = QLabel("0")
        trim_layout.addWidget(self.end_label, 1, 2)

        self.trim_groupbox.setLayout(trim_layout)
        layout.addWidget(self.trim_groupbox)
        self.trim_groupbox.setEnabled(False)

        self.setLayout(layout)

    def set_frames(self, frames: List[QImage], original_fps: int):
        self.frames = frames
        self.current_frame_index = 0
        self.preview_fps_spin.setValue(original_fps)

        if self.timer.isActive():
            self.timer.stop()
        self.play_btn.setText("▶ Play")

        if self.frames:
            total_frames = len(self.frames)
            self.frame_label.setText(f"Frame: 1/{total_frames}")
            self.trim_groupbox.setEnabled(True)
            self.start_slider.setRange(0, total_frames - 1)
            self.end_slider.setRange(0, total_frames - 1)
            self.start_slider.setValue(0)
            self.end_slider.setValue(total_frames - 1)
            self.start_label.setText("1")
            self.end_label.setText(f"{total_frames}")
        else:
            self.preview_label.setText("Preview will be displayed here after recording.")
            self.preview_label.setPixmap(QPixmap())
            self.frame_label.setText("Frame: 0/0")
            self.trim_groupbox.setEnabled(False)
            self.start_label.setText("0")
            self.end_label.setText("0")

        self.update_preview()

    def update_preview(self):
        if not self.frames or not (0 <= self.current_frame_index < len(self.frames)):
            self.preview_label.setText("Preview will be displayed here after recording.")
            self.preview_label.setPixmap(QPixmap())
            return

        original_pixmap = QPixmap.fromImage(self.frames[self.current_frame_index])
        scaled_pixmap = original_pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.preview_label.setPixmap(scaled_pixmap)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_label.setText(
            f"Frame: {self.current_frame_index + 1}/{len(self.frames)}"
        )

    def toggle_preview(self):
        if not self.frames:
            return
        if self.timer.isActive():
            self.timer.stop()
            self.play_btn.setText("▶ Play")
        else:
            # If playback is at the end, restart from the beginning of the trim range
            if not (self.start_slider.value() <= self.current_frame_index <= self.end_slider.value()):
                self.current_frame_index = self.start_slider.value()
            self.timer.start()
            self.play_btn.setText("⏸ Pause")

    def next_frame(self):
        if not self.frames:
            return
        
        start_frame, end_frame = self.start_slider.value(), self.end_slider.value()
        if start_frame >= end_frame:
            self.current_frame_index = start_frame
        else:
            self.current_frame_index += 1
            if self.current_frame_index > end_frame:
                self.current_frame_index = start_frame
        
        self.update_preview()

    def update_fps(self):
        fps = self.preview_fps_spin.value()
        interval = int(1000 / fps) if fps > 0 else 1000
        self.timer.setInterval(interval)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self.update_preview()

    def stop_timer_on_drag(self):
        if self.timer.isActive():
            self.timer.stop()
            self.play_btn.setText("▶ Play")

    def update_trim_range(self):
        # Prevent recursive signals
        self.start_slider.blockSignals(True)
        self.end_slider.blockSignals(True)

        # Ensure start slider is not greater than end slider
        if self.start_slider.value() > self.end_slider.value():
            if self.sender() == self.start_slider:
                self.end_slider.setValue(self.start_slider.value())
            else:
                self.start_slider.setValue(self.end_slider.value())

        self.start_label.setText(f"{self.start_slider.value() + 1}")
        self.end_label.setText(f"{self.end_slider.value() + 1}")

        # Update the preview to the current slider position being dragged
        self.current_frame_index = self.sender().value()
        self.update_preview()

        self.start_slider.blockSignals(False)
        self.end_slider.blockSignals(False)
