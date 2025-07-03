import time
from utils.qt_imports import QThread, pyqtSignal, QRect, QImage, QApplication, QCursor, QPainter, QPoint, QPixmap, Qt, QPen

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
        # Ermittle den korrekten Bildschirm basierend auf dem Aufnahmerechteck
        self.target_screen = self._get_screen_for_rect(rect)

    def _get_screen_for_rect(self, rect: QRect):
        """
        Ermittelt den Bildschirm, der das Aufnahmerechteck enthält.
        Falls das Rechteck über mehrere Bildschirme geht, wird der Bildschirm
        mit der größten Überschneidung gewählt.
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
        Konvertiert globale Koordinaten zu bildschirmspezifischen Koordinaten.
        """
        screen_geometry = self.target_screen.geometry()
        
        # Berechne relative Koordinaten zum gewählten Bildschirm
        relative_x = global_rect.x() - screen_geometry.x()
        relative_y = global_rect.y() - screen_geometry.y()
        
        return QRect(relative_x, relative_y, global_rect.width(), global_rect.height())

    def run(self):
        self.is_running = True
        interval = 1.0 / self.fps if self.fps > 0 else 0.1
        
        # Konvertiere zu bildschirmspezifischen Koordinaten
        screen_rect = self._convert_to_screen_coordinates(self.rect)
        
        print(f"Global rect: {self.rect}")
        print(f"Screen rect: {screen_rect}")
        print(f"Screen geometry: {self.target_screen.geometry()}")

        while self.is_running:
            if self.is_paused:
                self.msleep(100)  # Sleep while paused to avoid busy-waiting
                continue

            start_time = time.time()
            
            # Verwende den korrekten Bildschirm für die Aufnahme
            pixmap = self.target_screen.grabWindow(
                0,  # Desktop window ID (0 für den gesamten Bildschirm)
                screen_rect.x(), 
                screen_rect.y(), 
                screen_rect.width(), 
                screen_rect.height()
            )
            
            # Überprüfe ob die Aufnahme erfolgreich war
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
        """Zeichnet einen einfachen Mauszeiger (Pfeil) an der angegebenen Position."""
        # Pfeil-Punkte definieren
        arrow_points = [
            QPoint(0, 0), QPoint(0, 16), QPoint(6, 12), QPoint(10, 18),
            QPoint(12, 16), QPoint(8, 10), QPoint(16, 8), QPoint(0, 0)
        ]
        
        # Punkte zur Cursor-Position verschieben
        translated_points = [cursor_pos + point for point in arrow_points]
        
        # Weißer Rand
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.setBrush(Qt.GlobalColor.white)
        painter.drawPolygon(translated_points)
        
        # Schwarzer Pfeil
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.setBrush(Qt.GlobalColor.black)
        inner_points = [
            QPoint(1, 1), QPoint(1, 14), QPoint(6, 11), QPoint(9, 16),
            QPoint(11, 15), QPoint(7, 9), QPoint(14, 7), QPoint(1, 1)
        ]
        inner_translated = [cursor_pos + point for point in inner_points]
        painter.drawPolygon(inner_translated)

    def draw_cursor_in_recording(self, pixmap, cursor_pos):
        """Zeichnet den Cursor ins aufgenommene Bild."""
        # Check if the cursor is within the recording rectangle
        if self.rect.contains(cursor_pos):
            painter = QPainter(pixmap)
            # Calculate cursor position relative to the grabbed pixmap
            relative_cursor_pos = cursor_pos - self.rect.topLeft()
            
            # Zeichne den Cursor
            self.draw_cursor(painter, relative_cursor_pos)
            painter.end()