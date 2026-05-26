"""Graphical representation of a Gate population on the canvas."""

from PyQt6.QtWidgets import QGraphicsObject, QGraphicsSceneMouseEvent, QGraphicsSceneHoverEvent
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QFont, QPen, QBrush

from biopro.ui.theme import Colors, Fonts


class NodeItem(QGraphicsObject):
    """A graphical node representing a single population gate."""

    # Emitted when double-clicked
    node_double_clicked = pyqtSignal(str)
    
    # Drag signals
    edge_drag_started = pyqtSignal(str, QPointF)  # node_id, start_pos
    edge_dragged = pyqtSignal(QPointF)            # current_scene_pos
    edge_drag_released = pyqtSignal(str, QPointF) # source_node_id, release_scene_pos
    
    # Dimensions
    WIDTH = 200
    HEIGHT = 270
    RADIUS = 8
    PORT_RADIUS = 6

    def __init__(self, node_id: str, name: str, parent=None):
        super().__init__(parent)
        self.node_id = node_id
        self.name = name
        
        # Data
        self.event_count = 0
        self.parent_percentage = 0.0
        self.is_logic_node = False
        self.logic_operator = "AND"
        
        # State
        self.x_param = None
        self.y_param = None
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self._is_hovered = False
        self._hovered_port = None  # 'input' or 'output'
        self._is_dragging_edge = False
        
        self._plot_pixmap = None

    def set_plot_image(self, qimg: QImage) -> None:
        """Set the rendered plot image."""
        from PyQt6.QtGui import QPixmap
        self._plot_pixmap = QPixmap.fromImage(qimg)
        self.update()

    def boundingRect(self) -> QRectF:
        # Include a little padding for the ports that stick out
        return QRectF(
            -self.PORT_RADIUS,
            0,
            self.WIDTH + self.PORT_RADIUS * 2,
            self.HEIGHT
        )

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Base Card path
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.WIDTH, self.HEIGHT, self.RADIUS, self.RADIUS)
        
        # Colors
        bg_color = QColor(Colors.BG_MEDIUM)
        if self.is_logic_node:
            if self.logic_operator == "AND":
                bg_color = QColor("#2A3E4C") # Dark blue tint
            elif self.logic_operator == "OR":
                bg_color = QColor("#4A3525") # Dark orange/brown tint
            elif self.logic_operator == "NOT":
                bg_color = QColor("#4A2525") # Dark red tint
                
        if self._is_hovered:
            bg_color = bg_color.lighter(120)
            
        border_color = QColor(Colors.ACCENT_PRIMARY) if self.isSelected() else QColor(Colors.BORDER)
        border_width = 2 if self.isSelected() else 1
        
        # Draw Shadow / Body
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, border_width))
        painter.drawPath(path)
        
        # Draw Ports
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Left Port (Input)
        in_color = QColor(Colors.ACCENT_PRIMARY).lighter(150) if self._hovered_port == 'input' else QColor(Colors.ACCENT_PRIMARY)
        painter.setBrush(QBrush(in_color))
        painter.drawEllipse(
            QPointF(0, self.HEIGHT / 2),
            self.PORT_RADIUS * (1.5 if self._hovered_port == 'input' else 1.0), 
            self.PORT_RADIUS * (1.5 if self._hovered_port == 'input' else 1.0)
        )
        
        # Right Port (Output)
        out_color = QColor(Colors.ACCENT_PRIMARY).lighter(150) if self._hovered_port == 'output' else QColor(Colors.ACCENT_PRIMARY)
        painter.setBrush(QBrush(out_color))
        painter.drawEllipse(
            QPointF(self.WIDTH, self.HEIGHT / 2),
            self.PORT_RADIUS * (1.5 if self._hovered_port == 'output' else 1.0), 
            self.PORT_RADIUS * (1.5 if self._hovered_port == 'output' else 1.0)
        )
        
        # Draw Text
        painter.setPen(QColor(Colors.FG_PRIMARY))
        font = QFont(Fonts.FAMILY_UI, Fonts.SIZE_SMALL, QFont.Weight.Bold)
        painter.setFont(font)
        
        text_rect = QRectF(12, 12, self.WIDTH - 24, 20)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.name)
        
        # Draw Stats
        painter.setPen(QColor(Colors.FG_SECONDARY))
        stats_font = QFont(Fonts.FAMILY_UI, Fonts.SIZE_SMALL - 1)
        painter.setFont(stats_font)
        
        stats_rect = QRectF(12, 36, self.WIDTH - 24, 32)
        stats_text = f"{self.event_count:,} events\n{self.parent_percentage:.1f}% of parent"
        painter.drawText(stats_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, stats_text)

        # Draw Plot Pixmap
        if self._plot_pixmap and not self.is_logic_node:
            plot_rect = QRectF(10, 70, self.WIDTH - 20, self.HEIGHT - 80)
            
            # To ensure the pixmap obeys the rounded rectangle bounds if it touches the bottom,
            # we draw it directly. Since we have a margin (10px from edges), it naturally fits 
            # inside the rounded boundaries without needing clipping.
            scaled_pixmap = self._plot_pixmap.scaled(
                int(plot_rect.width()), 
                int(plot_rect.height()), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Center the pixmap within the allocated plot_rect
            dx = plot_rect.x() + (plot_rect.width() - scaled_pixmap.width()) / 2
            dy = plot_rect.y() + (plot_rect.height() - scaled_pixmap.height()) / 2
            painter.drawPixmap(QPointF(dx, dy), scaled_pixmap)
            
            # Draw a subtle border around the plot
            painter.setPen(QPen(QColor(Colors.BORDER), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(dx, dy, scaled_pixmap.width(), scaled_pixmap.height()))
            
            # Draw axis labels
            if self.x_param and self.y_param:
                label_font = QFont(Fonts.FAMILY_UI, 8, QFont.Weight.Bold)
                painter.setFont(label_font)
                fm = painter.fontMetrics()
                
                pill_bg = QColor(Colors.BG_DARKEST)
                pill_bg.setAlpha(200)
                text_fg = QColor(Colors.FG_PRIMARY)

                # Bottom X-axis label
                x_text = self.x_param
                x_tw = fm.horizontalAdvance(x_text)
                x_th = fm.height()
                
                x_cx = dx + scaled_pixmap.width() / 2
                x_by = dy + scaled_pixmap.height() - 4
                
                x_pill_rect = QRectF(x_cx - x_tw/2 - 4, x_by - x_th, x_tw + 8, x_th)
                
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(pill_bg))
                painter.drawRoundedRect(x_pill_rect, 3, 3)
                
                painter.setPen(QPen(text_fg))
                painter.drawText(x_pill_rect, Qt.AlignmentFlag.AlignCenter, x_text)
                
                # Left Y-axis label
                painter.save()
                y_text = self.y_param
                y_tw = fm.horizontalAdvance(y_text)
                y_th = fm.height()
                
                y_cx = dx + 4 + y_th / 2
                y_cy = dy + scaled_pixmap.height() / 2
                
                painter.translate(y_cx, y_cy)
                painter.rotate(-90)
                
                y_pill_rect = QRectF(-y_tw/2 - 4, -y_th/2, y_tw + 8, y_th)
                
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(pill_bg))
                painter.drawRoundedRect(y_pill_rect, 3, 3)
                
                painter.setPen(QPen(text_fg))
                painter.drawText(y_pill_rect, Qt.AlignmentFlag.AlignCenter, y_text)
                painter.restore()

    def get_input_port_pos(self) -> QPointF:
        """Get scene coordinates of the input port."""
        return self.mapToScene(QPointF(0, self.HEIGHT / 2))

    def get_output_port_pos(self) -> QPointF:
        """Get scene coordinates of the output port."""
        return self.mapToScene(QPointF(self.WIDTH, self.HEIGHT / 2))

    def _get_port_at(self, pos: QPointF) -> Optional[str]:
        """Return 'input' or 'output' if pos is near a port, else None."""
        # Check input port
        in_pos = QPointF(0, self.HEIGHT / 2)
        if (pos - in_pos).manhattanLength() <= self.PORT_RADIUS * 2:
            return 'input'
            
        # Check output port
        out_pos = QPointF(self.WIDTH, self.HEIGHT / 2)
        if (pos - out_pos).manhattanLength() <= self.PORT_RADIUS * 2:
            return 'output'
            
        return None

    # ── Events ────────────────────────────────────────────────────────
    
    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self._is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        port = self._get_port_at(event.pos())
        if port != self._hovered_port:
            self._hovered_port = port
            if port:
                self.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.unsetCursor()
            self.update()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        self._is_hovered = False
        if self._hovered_port:
            self._hovered_port = None
            self.unsetCursor()
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        port = self._get_port_at(event.pos())
        if port == 'output' and event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging_edge = True
            self.edge_drag_started.emit(self.node_id, self.get_output_port_pos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._is_dragging_edge:
            self.edge_dragged.emit(event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._is_dragging_edge:
            self._is_dragging_edge = False
            self.edge_drag_released.emit(self.node_id, event.scenePos())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.node_double_clicked.emit(self.node_id)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)
            
    def itemChange(self, change, value):
        if change == QGraphicsObject.GraphicsItemChange.ItemPositionHasChanged:
            # We will catch this in the manager to update edge positions
            pass
        return super().itemChange(change, value)
