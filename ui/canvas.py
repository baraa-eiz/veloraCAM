from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QImage
from PySide6.QtWidgets import QWidget

class CAMCanvas(QWidget):
    """
    Real-time high-performance 2D machining simulator.
    Displays heightmap overlays, color-coded operation path lines, and safe rapid travels.
    """
    clicked_pos = Signal(int, int, Qt.MouseButton)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(350, 350)
        self.img_pixmap = None
        self.stock_x = 300.0
        self.stock_y = 300.0
        self.forbidden_mask = None
        self.operations_paths = []  # List of dict: {"name": str, "type": str, "moves": [(x,y,z,cmd)], "color": QColor, "enabled": bool}
        
    def set_heightmap(self, pil_image):
        """Loads and converts PIL heightmap to PySide QPixmap."""
        if pil_image is None:
            self.img_pixmap = None
            self.update()
            return
            
        pil_conv = pil_image.convert("RGBA")
        width, height = pil_conv.size
        data = pil_conv.tobytes("raw", "RGBA")
        qimg = QImage(data, width, height, QImage.Format_RGBA8888)
        self.img_pixmap = QPixmap.fromImage(qimg)
        self.update()

    def set_forbidden_mask(self, mask):
        self.forbidden_mask = mask
        self.update()

    def set_stock_dimensions(self, sx, sy):
        self.stock_x = max(10.0, sx)
        self.stock_y = max(10.0, sy)
        self.update()

    def set_toolpaths(self, paths):
        """
        Receives operational toolpaths to render.
        Format of paths: list of dicts with keys: 'name', 'type', 'moves', 'color', 'enabled'
        """
        self.operations_paths = paths
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 1. Fill deep charcoal workspace background
        painter.fillRect(self.rect(), QColor("#141419"))
        
        # Determine canvas scaling boundaries
        w, h = self.width(), self.height()
        margin = 30
        draw_w = w - 2 * margin
        draw_h = h - 2 * margin
        
        scale_x = draw_w / self.stock_x
        scale_y = draw_h / self.stock_y
        scale = min(scale_x, scale_y)
        
        # Center stock panel
        off_x = margin + (draw_w - self.stock_x * scale) / 2.0
        off_y = margin + (draw_h - self.stock_y * scale) / 2.0
        
        def to_canvas(wx, wy):
            # Map physical mm coordinates to screen pixels
            # Y is inverted in PySide viewports (0,0 is top-left)
            cx = off_x + wx * scale
            cy = off_y + (self.stock_y - wy) * scale
            return QPointF(cx, cy)
            
        # 2. Draw workpiece stock bordercard
        stock_rect = QRectF(off_x, off_y, self.stock_x * scale, self.stock_y * scale)
        painter.fillRect(stock_rect, QColor("#1e1e26"))
        
        # 3. Overlay heightmap image if present (faded alpha)
        if self.img_pixmap:
            painter.setOpacity(0.25)
            painter.drawPixmap(stock_rect.toRect(), self.img_pixmap)
            painter.setOpacity(1.0)
            
        # 4. Draw Forbidden Zones overlay in semi-transparent red
        if self.forbidden_mask is not None:
            # Simple bounding box representation for overlay
            painter.setOpacity(0.15)
            painter.fillRect(stock_rect, QColor("#e63946"))
            painter.setOpacity(1.0)
            
        # Draw physical stock wireframe border
        border_pen = QPen(QColor("#008be6"), 2)
        painter.setPen(border_pen)
        painter.drawRect(stock_rect)
        
        # 5. Draw operational toolpaths vectors
        for op in self.operations_paths:
            if not op.get("enabled", True):
                continue
                
            moves = op.get("moves", [])
            if not moves:
                continue
                
            op_type = op.get("type", "")
            
            # Map distinct colors based on operation style
            if op_type == "Raster Roughing" or op_type == "Flat Clearing":
                line_color = QColor("#ff9f1c")  # Orange
            elif op_type == "Finishing Raster" or op_type == "Ball Nose Finishing" or op_type == "V-Carve Detailing":
                line_color = QColor("#2ec4b6")  # Teal
            elif op_type == "V-Groove Bending":
                line_color = QColor("#e0115f")  # Ruby/Magenta
            elif op_type == "Contour Cutout" or op_type == "Edge Cleanup":
                line_color = QColor("#55a630")  # Green
            else:
                line_color = QColor("#ffffff")
                
            # Direct path drawing
            pen_feed = QPen(line_color, 1.2, Qt.SolidLine)
            pen_rapid = QPen(QColor("#ff4d4d"), 1.0, Qt.DashLine)
            
            last_pt = None
            for x, y, z, cmd in moves:
                curr_pt = to_canvas(x, y)
                if last_pt is not None:
                    if cmd == "G00":
                        painter.setPen(pen_rapid)
                    else:
                        painter.setPen(pen_feed)
                    painter.drawLine(last_pt, curr_pt)
                last_pt = curr_pt
                
        # 6. Draw coordinate zero-point crosshair (Front-Left)
        origin_pt = to_canvas(0.0, 0.0)
        origin_pen = QPen(QColor("#00d2ff"), 2)
        painter.setPen(origin_pen)
        painter.drawLine(origin_pt.x() - 10, origin_pt.y(), origin_pt.x() + 10, origin_pt.y())
        painter.drawLine(origin_pt.x(), origin_pt.y() - 10, origin_pt.x(), origin_pt.y() + 10)
        
        # Draw labels
        painter.setPen(QColor("#a0a0b2"))
        painter.drawText(stock_rect.bottomLeft() + QPointF(0, 15), "Origin (X0 Y0)")
        painter.drawText(stock_rect.topRight() - QPointF(60, 5), f"{self.stock_x:.0f}x{self.stock_y:.0f} mm")

    def mousePressEvent(self, event):
        self.clicked_pos.emit(event.x(), event.y(), event.button())
        super().mousePressEvent(event)
