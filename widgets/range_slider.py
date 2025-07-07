from utils.qt_imports import *

class RangeSlider(QWidget):
    """Custom Range Slider Widget for trim functionality."""
    
    rangeChanged = pyqtSignal(int, int)  # start, end values
    
    def __init__(self, minimum=0, maximum=100, parent=None):
        super().__init__(parent)
        self.minimum = minimum
        self.maximum = maximum
        self.start_value = minimum
        self.end_value = maximum
        
        self.handle_radius = 8
        self.track_height = 4
        self.active_handle = None  # 'start', 'end', or None
        
        self.setMinimumHeight(30)
        self.setMouseTracking(True)
        
    def set_range(self, minimum, maximum):
        """Set the range of the slider."""
        self.minimum = minimum
        self.maximum = maximum
        self.start_value = max(minimum, min(self.start_value, maximum))
        self.end_value = max(minimum, min(self.end_value, maximum))
        self.update()
        self.rangeChanged.emit(self.start_value, self.end_value)
    
    def set_values(self, start, end):
        """Set the current values."""
        self.start_value = max(self.minimum, min(start, self.maximum))
        self.end_value = max(self.minimum, min(end, self.maximum))
        if self.start_value > self.end_value:
            self.start_value, self.end_value = self.end_value, self.start_value
        self.update()
        self.rangeChanged.emit(self.start_value, self.end_value)
    
    def get_values(self):
        """Get current values."""
        return self.start_value, self.end_value
    
    def value_to_pixel(self, value):
        """Convert value to pixel position."""
        if self.maximum <= self.minimum:
            return self.handle_radius
        
        usable_width = self.width() - 2 * self.handle_radius
        ratio = (value - self.minimum) / (self.maximum - self.minimum)
        return self.handle_radius + ratio * usable_width
    
    def pixel_to_value(self, pixel):
        """Convert pixel position to value."""
        if self.maximum <= self.minimum:
            return self.minimum
        
        usable_width = self.width() - 2 * self.handle_radius
        ratio = (pixel - self.handle_radius) / usable_width
        ratio = max(0, min(1, ratio))
        return int(self.minimum + ratio * (self.maximum - self.minimum))
    
    def get_handle_rect(self, value):
        """Get rectangle for handle at given value."""
        center_x = self.value_to_pixel(value)
        center_y = self.height() // 2
        return QRect(
            int(center_x - self.handle_radius),
            int(center_y - self.handle_radius),
            self.handle_radius * 2,
            self.handle_radius * 2
        )
    
    def paintEvent(self, event):
        """Paint the range slider."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Track background
        track_rect = QRect(
            self.handle_radius,
            self.height() // 2 - self.track_height // 2,
            self.width() - 2 * self.handle_radius,
            self.track_height
        )
        painter.fillRect(track_rect, QColor(200, 200, 200))
        
        # Active range
        start_x = self.value_to_pixel(self.start_value)
        end_x = self.value_to_pixel(self.end_value)
        active_rect = QRect(
            int(start_x),
            self.height() // 2 - self.track_height // 2,
            int(end_x - start_x),
            self.track_height
        )
        painter.fillRect(active_rect, QColor(70, 130, 180))
        
        # Start handle
        start_rect = self.get_handle_rect(self.start_value)
        painter.setBrush(QColor(50, 100, 150))
        painter.setPen(QPen(QColor(30, 80, 130), 2))
        painter.drawEllipse(start_rect)
        
        # End handle
        end_rect = self.get_handle_rect(self.end_value)
        painter.setBrush(QColor(50, 100, 150))
        painter.setPen(QPen(QColor(30, 80, 130), 2))
        painter.drawEllipse(end_rect)
    
    def mousePressEvent(self, event):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            start_rect = self.get_handle_rect(self.start_value)
            end_rect = self.get_handle_rect(self.end_value)
            
            if start_rect.contains(event.pos()):
                self.active_handle = 'start'
            elif end_rect.contains(event.pos()):
                self.active_handle = 'end'
            else:
                # Click on track - move nearest handle
                click_value = self.pixel_to_value(event.pos().x())
                start_dist = abs(click_value - self.start_value)
                end_dist = abs(click_value - self.end_value)
                
                if start_dist < end_dist:
                    self.start_value = click_value
                    self.active_handle = 'start'
                else:
                    self.end_value = click_value
                    self.active_handle = 'end'
                
                self.update()
                self.rangeChanged.emit(self.start_value, self.end_value)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move."""
        if self.active_handle:
            new_value = self.pixel_to_value(event.pos().x())
            
            if self.active_handle == 'start':
                self.start_value = min(new_value, self.end_value)
            elif self.active_handle == 'end':
                self.end_value = max(new_value, self.start_value)
            
            self.update()
            self.rangeChanged.emit(self.start_value, self.end_value)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        self.active_handle = None