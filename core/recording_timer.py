# core/recording_timer.py

import time
from utils.qt_imports import QThread, pyqtSignal, QRect, QImage, QApplication, QCursor, QPainter, QPoint, QPixmap, Qt, QPen

class RecordingTimer(QThread):
    """
    A QThread that captures frames from a specific screen region at a given FPS.
    """
    frame_captured = pyqtSignal(QImage)

    def __init__(self, rect: QRect, fps: int = 10):
        super().__init__()
        self.rect = rect
        self.fps = fps
        self.is_running = False
        self.is_paused = False

    def run(self):
        self.is_running = True
        interval = 1.0 / self.fps if self.fps > 0 else 0.1
        screen = QApplication.primaryScreen()

        while self.is_running:
            if self.is_paused:
                self.msleep(100)  # Sleep while paused to avoid busy-waiting
                continue

            start_time = time.time()
            pixmap = screen.grabWindow(0, self.rect.x(), self.rect.y(), self.rect.width(), self.rect.height())

            # Draw mouse cursor onto the pixmap
            cursor_pos = QCursor.pos()
            # Check if the cursor is within the recording rectangle
            if self.rect.contains(cursor_pos):
                painter = QPainter(pixmap)
                # Calculate cursor position relative to the grabbed pixmap
                relative_cursor_pos = cursor_pos - self.rect.topLeft()
                
                # Get the current cursor pixmap. If no override cursor, use the default.
                current_cursor = QApplication.overrideCursor()
                if current_cursor and current_cursor.shape() == Qt.CursorShape.BitmapCursor:
                    cursor_pixmap = current_cursor.pixmap()
                    hotspot = current_cursor.hotSpot()
                else:
                    # Fallback for default cursor or if overrideCursor is not a bitmap
                    # This is a simplified representation; a real implementation might need
                    # to render a default arrow cursor or use platform-specific methods.
                    # For now, we'll just draw a small dot or a simple cross.
                    # A more robust solution would involve getting the system cursor image.
                    # For demonstration, let's draw a simple cross.
                    cursor_pixmap = QPixmap(32, 32)
                    cursor_pixmap.fill(Qt.GlobalColor.transparent)
                    temp_painter = QPainter(cursor_pixmap)
                    # Draw white outline
                    temp_painter.setPen(QPen(Qt.GlobalColor.white, 8)) # Thicker white pen for outline
                    temp_painter.drawLine(0, 16, 31, 16)
                    temp_painter.drawLine(16, 0, 16, 31)
                    # Draw black cross on top
                    temp_painter.setPen(QPen(Qt.GlobalColor.black, 4)) # Original black pen
                    temp_painter.drawLine(0, 16, 31, 16)
                    temp_painter.drawLine(16, 0, 16, 31)
                    temp_painter.end()
                    hotspot = QPoint(16, 16) # Center of the cross
                
                if cursor_pixmap:
                    painter.drawPixmap(relative_cursor_pos - hotspot, cursor_pixmap)
                painter.end()

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
