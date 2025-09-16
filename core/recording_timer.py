import time
from utils.qt_imports import QThread, pyqtSignal, QRect, QImage, QApplication, QCursor, QPainter, QPoint, QPixmap, Qt, \
    QPen


class RecordingTimer(QThread):
    """
    A QThread that captures frames from a specific screen region at a given FPS.
    Now with proper multi-monitor support.
    """
    frame_captured = pyqtSignal(QImage)

    def __init__(self, rect: QRect, fps: int = 10):
        super().__init__()
        self.rect = rect
        self.fps = fps
        self.is_running = False
        self.is_paused = False
        # Determine the correct screen based on the recording rectangle
        self.target_screen = self._get_screen_for_rect(rect)

    def update_recording_rect(self, new_rect: QRect) -> None:
        """Update the recording rectangle and screen while recording."""
        # Update the recording rectangle
        self.rect = new_rect

        # Re-determine the target screen (in case window moved to another monitor)
        new_screen = self._get_screen_for_rect(new_rect)

        # Only log if screen changed
        if new_screen != self.target_screen:
            print(f"Switched recording to screen: {new_screen.name()} at {new_screen.geometry()}")
            self.target_screen = new_screen

    def _get_screen_for_rect(self, rect: QRect):
        """
        Determines the screen that contains the recording rectangle.
        If the rectangle spans multiple screens, the screen with the
        largest intersection is chosen.
        """
        screens = QApplication.screens()
        best_screen = QApplication.primaryScreen()  # Fallback
        max_intersection_area = 0

        for screen in screens:
            screen_geometry = screen.geometry()
            intersection = rect.intersected(screen_geometry)

            if not intersection.isEmpty():
                intersection_area = intersection.width() * intersection.height()
                if intersection_area > max_intersection_area:
                    max_intersection_area = intersection_area
                    best_screen = screen

        print(f"Recording on screen: {best_screen.name()} at {best_screen.geometry()}")
        return best_screen

    def _convert_to_screen_coordinates(self, global_rect: QRect):
        """
        Converts global coordinates to screen-specific coordinates.
        """
        screen_geometry = self.target_screen.geometry()

        # Calculate relative coordinates to the chosen screen
        relative_x = global_rect.x() - screen_geometry.x()
        relative_y = global_rect.y() - screen_geometry.y()

        return QRect(relative_x, relative_y, global_rect.width(), global_rect.height())

    def run(self):
        self.is_running = True
        interval = 1.0 / self.fps if self.fps > 0 else 0.1

        while self.is_running:
            if self.is_paused:
                self.msleep(100)  # Sleep while paused to avoid busy-waiting
                continue

            start_time = time.time()

            # Convert to screen-specific coordinates (recalculate EVERY TIME!)
            screen_rect = self._convert_to_screen_coordinates(self.rect)

            # Use the correct screen for the capture
            pixmap = self.target_screen.grabWindow(
                0,  # Desktop window ID (0 for the entire desktop)
                screen_rect.x(),
                screen_rect.y(),
                screen_rect.width(),
                screen_rect.height()
            )

            # Check if the capture was successful
            if pixmap.isNull():
                print(f"Warning: Failed to capture screen area {screen_rect}")
                self.msleep(100)
                continue

            cursor_pos = QCursor.pos()
            self.draw_cursor_in_recording(pixmap, cursor_pos)

            self.frame_captured.emit(pixmap.toImage())

            elapsed = time.time() - start_time
            sleep_duration = max(0, interval - elapsed)
            time.sleep(sleep_duration)

    def stop(self):
        """Stops the recording thread."""
        self.is_running = False

    def pause(self):
        """Pauses frame capturing."""
        self.is_paused = True

    def resume(self):
        """Resumes frame capturing."""
        self.is_paused = False

    def draw_cursor(self, painter, cursor_pos):
        """Draws a simple mouse cursor (arrow) at the specified position."""
        # Define arrow points
        arrow_points = [
            QPoint(0, 0), QPoint(0, 16), QPoint(6, 12), QPoint(10, 18),
            QPoint(12, 16), QPoint(8, 10), QPoint(16, 8), QPoint(0, 0)
        ]

        # Translate points to the cursor position
        translated_points = [cursor_pos + point for point in arrow_points]

        # White border
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.setBrush(Qt.GlobalColor.white)
        painter.drawPolygon(translated_points)

        # Black arrow
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.setBrush(Qt.GlobalColor.black)
        inner_points = [
            QPoint(1, 1), QPoint(1, 14), QPoint(6, 11), QPoint(9, 16),
            QPoint(11, 15), QPoint(7, 9), QPoint(14, 7), QPoint(1, 1)
        ]
        inner_translated = [cursor_pos + point for point in inner_points]
        painter.drawPolygon(inner_translated)

    def draw_cursor_in_recording(self, pixmap, cursor_pos):
        """Draws the cursor into the recorded image."""
        # Check if the cursor is within the recording rectangle
        if self.rect.contains(cursor_pos):
            painter = QPainter(pixmap)
            # Calculate cursor position relative to the grabbed pixmap
            relative_cursor_pos = cursor_pos - self.rect.topLeft()

            # Draw the cursor
            self.draw_cursor(painter, relative_cursor_pos)
            painter.end()