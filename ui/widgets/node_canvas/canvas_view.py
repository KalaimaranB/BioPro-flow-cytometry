"""Node Canvas - View layer for the Pipeline feature."""

from typing import Any
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, QPointF, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QWheelEvent, QMouseEvent, QKeyEvent

from analysis.state import FlowState
from biopro.ui.theme import Colors

from .canvas_manager import CanvasManager


class _CanvasGraphicsView(QGraphicsView):
    """Infinite panning and zooming view for the node canvas."""

    def __init__(self, scene: QGraphicsScene, parent: QWidget | None = None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        
        self._is_panning = False
        self._pan_start_pos = QPointF()
        
        self._apply_theme_styles()

    def _apply_theme_styles(self) -> None:
        """Dynamically refresh colors when theme changes."""
        self.setBackgroundBrush(QColor(Colors.BG_DARKEST))
        self._grid_size = 40
        self._grid_pen = QPen(QColor(Colors.BORDER), 1)
        self.viewport().update()
        self._pan_start_pos = QPointF()

    def drawBackground(self, painter: QPainter, rect) -> None:
        """Draw the infinite dot grid background."""
        super().drawBackground(painter, rect)
        painter.setPen(self._grid_pen)
        
        left = int(rect.left()) - (int(rect.left()) % self._grid_size)
        top = int(rect.top()) - (int(rect.top()) % self._grid_size)
        
        # Draw a dot grid
        points = []
        for x in range(left, int(rect.right()), self._grid_size):
            for y in range(top, int(rect.bottom()), self._grid_size):
                points.append(QPointF(x, y))
                
        painter.drawPoints(points)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom in/out with the scroll wheel."""
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor
        
        # Check angle delta to determine zoom direction
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            zoom_factor = zoom_out_factor
            
        current_zoom = self.transform().m11()
        if zoom_factor > 1.0 and current_zoom >= 3.0:
            return
        if zoom_factor < 1.0 and current_zoom <= 0.1:
            return
            
        self.scale(zoom_factor, zoom_factor)

    def zoom_in(self) -> None:
        if self.transform().m11() < 3.0:
            self.scale(1.2, 1.2)
            
    def zoom_out(self) -> None:
        if self.transform().m11() > 0.1:
            self.scale(1.0 / 1.2, 1.0 / 1.2)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Middle click or Space+Left click to pan."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self._pan_start_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_panning:
            delta = event.position() - self._pan_start_pos
            self._pan_start_pos = event.position()
            
            # Map delta to scene coordinates relative to view scale
            hs = self.horizontalScrollBar()
            vs = self.verticalScrollBar()
            hs.setValue(hs.value() - int(delta.x()))
            vs.setValue(vs.value() - int(delta.y()))
            
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class NodeCanvas(QWidget):
    """The central widget for the Node Canvas view."""
    
    node_double_clicked = pyqtSignal(str)
    node_removed = pyqtSignal(str)                   # node_id
    connection_requested = pyqtSignal(str, str, str) # sample_id, source_id, target_id
    connection_removed = pyqtSignal(str, str, str)   # sample_id, source_id, target_id

    def __init__(self, state: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._setup_ui()
        
        self.current_sample_id = None
        
        # Initialize the manager which builds and updates the scene
        self._manager = CanvasManager(self.state, self._scene)
        self._manager.node_double_clicked.connect(self.node_double_clicked.emit)
        self._manager.connection_requested.connect(
            lambda src, tgt: self.connection_requested.emit(self.current_sample_id, src, tgt)
            if self.current_sample_id else None
        )
        self._manager.connection_removed.connect(
            lambda src, tgt: self.connection_removed.emit(self.current_sample_id, src, tgt)
            if self.current_sample_id else None
        )

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self._scene = QGraphicsScene(self)
        # Give the scene a large initial rect to allow panning around
        self._scene.setSceneRect(-5000, -5000, 10000, 10000)
        
        self._view = _CanvasGraphicsView(self._scene)
        layout.addWidget(self._view)
        
        # ── Overlay Controls ──
        overlay_layout = QHBoxLayout(self._view)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        overlay_layout.setContentsMargins(0, 0, 16, 16)
        overlay_layout.setSpacing(8)
        
        btn_style = (
            f"QPushButton {{"
            f"  background: {Colors.BG_MEDIUM};"
            f"  color: {Colors.FG_PRIMARY};"
            f"  border: 1px solid {Colors.BORDER};"
            f"  border-radius: 4px;"
            f"  padding: 6px 12px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {Colors.BG_LIGHT};"
            f"  border: 1px solid {Colors.ACCENT_PRIMARY};"
            f"}}"
        )
        
        self.btn_zoom_in = QPushButton("Zoom In (+)")
        self.btn_zoom_in.setStyleSheet(btn_style)
        self.btn_zoom_in.clicked.connect(self._view.zoom_in)
        
        self.btn_zoom_out = QPushButton("Zoom Out (-)")
        self.btn_zoom_out.setStyleSheet(btn_style)
        self.btn_zoom_out.clicked.connect(self._view.zoom_out)
        
        self.btn_fit = QPushButton("Fit View (F)")
        self.btn_fit.setStyleSheet(btn_style)
        self.btn_fit.clicked.connect(self.center_on_nodes)
        
        self.btn_pan = QPushButton("Pan Tool")
        self.btn_pan.setCheckable(True)
        self.btn_pan.setStyleSheet(btn_style)
        self.btn_pan.toggled.connect(self._on_pan_toggled)
        
        overlay_layout.addWidget(self.btn_pan)
        overlay_layout.addWidget(self.btn_zoom_out)
        overlay_layout.addWidget(self.btn_zoom_in)
        overlay_layout.addWidget(self.btn_fit)
        
        self._apply_theme_styles()

    def _apply_theme_styles(self) -> None:
        """Dynamically refresh control button styles when theme changes."""
        btn_style = (
            f"QPushButton {{"
            f"  background: {Colors.BG_MEDIUM};"
            f"  color: {Colors.FG_PRIMARY};"
            f"  border: 1px solid {Colors.BORDER};"
            f"  border-radius: 4px;"
            f"  padding: 6px 12px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {Colors.BG_LIGHT};"
            f"  border: 1px solid {Colors.ACCENT_PRIMARY};"
            f"}}"
        )
        self.btn_zoom_in.setStyleSheet(btn_style)
        self.btn_zoom_out.setStyleSheet(btn_style)
        self.btn_fit.setStyleSheet(btn_style)
        self.btn_pan.setStyleSheet(btn_style)
        
        if hasattr(self._view, "_apply_theme_styles"):
            self._view._apply_theme_styles()

    def _on_pan_toggled(self, checked: bool) -> None:
        if checked:
            self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        else:
            self._view.setDragMode(QGraphicsView.DragMode.NoDrag)

    def set_sample(self, sample_id: str) -> None:
        """Switch the canvas to display a specific sample."""
        self.current_sample_id = sample_id
        self._manager.load_sample(sample_id)
        self.center_on_nodes()
        
    def center_on_nodes(self) -> None:
        """Auto-frame the view to fit the current nodes."""
        rect = self._scene.itemsBoundingRect()
        if not rect.isNull():
            # Pad the rect a bit so nodes aren't touching edges
            margin = 50.0
            rect.adjust(-margin, -margin, margin, margin)
            self._view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_F:
            self.center_on_nodes()
            event.accept()
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            from .items.edge_item import EdgeItem
            from .items.node_item import NodeItem
            for item in self._scene.selectedItems():
                if isinstance(item, EdgeItem):
                    self._manager.connection_removed.emit(item.source_node.node_id, item.target_node.node_id)
                elif isinstance(item, NodeItem):
                    self.node_removed.emit(item.node_id)
            event.accept()
        else:
            super().keyPressEvent(event)
