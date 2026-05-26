"""SampleViewWidget — custom-painted node-link chart for one sample.

Single Responsibility: render TreeNodeRects and handle mouse events.
Delegates all layout geometry to NodeTreeEngine.
Delegates all tooltip display to HoverCard.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QPoint, QRect, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import QMenu, QSizePolicy, QWidget

try:
    from biopro.ui.theme import Colors, Fonts, theme_manager
except ImportError:
    class Colors:
        BG_DARKEST = "#0d1117"
        BG_DARK = "#161b22"
        BG_MEDIUM = "#21262d"
        FG_PRIMARY = "#e6edf3"
        FG_SECONDARY = "#8b949e"
        FG_DISABLED = "#484f58"
        BORDER = "#30363d"
        ACCENT_PRIMARY = "#00bcd4"
    class Fonts:
        FAMILY_UI = "Inter, SF Pro Display, -apple-system, sans-serif"
        SIZE_SMALL = 11
    class _FakeManager:
        class _S:
            def connect(self, *a): pass
        theme_changed = _S()
    theme_manager = _FakeManager()

from .node_tree_engine import NodeTreeEngine, TreeNodeRect
from .hover_card import HoverCard

# Depth-level colour palette (matches HoverCard and AllSamplesModel)
_PALETTE = [
    QColor("#7c4dff"),  # 0 root    — purple
    QColor("#00bcd4"),  # 1 depth 1 — teal
    QColor("#42a5f5"),  # 2 depth 2 — blue
    QColor("#ffa726"),  # 3 depth 3 — orange
    QColor("#ef5350"),  # 4 depth 4 — pink/red
    QColor("#66bb6a"),  # 5 depth 5 — green
]
_SELECTED_BORDER = QColor("#ffffff")
_RADIUS = 6    # corner radius


class SampleViewWidget(QWidget):
    """Custom painter node-link flowchart widget.

    Signals:
        node_clicked(node_id):         Single click selects a population.
        node_double_clicked(node_id):  Double click opens a new graph.
        rename_requested(node_id):     Via context menu.
        delete_requested(node_id):     Via context menu.
    """

    node_clicked        = pyqtSignal(str)
    node_double_clicked = pyqtSignal(str)
    rename_requested    = pyqtSignal(str)
    delete_requested    = pyqtSignal(str)

    def __init__(self, state, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._rects: list[TreeNodeRect] = []
        self._selected_id: str | None = None
        self._hovered_id:  str | None = None
        self._hover_card   = HoverCard(self)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setMinimumHeight(200)
        self.setMinimumWidth(200)

        theme_manager.theme_changed.connect(self.update)

    # ── Public API ────────────────────────────────────────────────────

    def set_rects(self, rects: list[TreeNodeRect]) -> None:
        """Replace the rect list and repaint."""
        self._rects = rects
        self._selected_id = None
        self._hover_card.hide()

        if rects:
            # Rects from NodeTreeEngine are 0-based (left edge = 0, top already padded).
            tree_w = max(r.x + r.width / 2 for r in rects)
            tree_h = max(r.y + r.height / 2 for r in rects)
            self._tree_width = tree_w
        else:
            self._tree_width = 0.0
            tree_h = 200.0

        # Allow the widget to grow but not shrink below what the tree needs
        self.setMinimumSize(int(self._tree_width + 40), int(tree_h + 40))
        self.update()

    def set_selected(self, node_id: str | None) -> None:
        self._selected_id = node_id
        self.update()

    def clear(self) -> None:
        self._rects = []
        self._selected_id = None
        self._hover_card.hide()
        self.update()

    # ── Painting ──────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        if not self._rects:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Compute horizontal centering offset so the tree sits in the middle
        # of the available widget width.  NodeTreeEngine produces 0-based coords
        # (leftmost node left-edge = 0), so we simply shift right by half the
        # remaining space.
        tree_w = getattr(self, "_tree_width", 0.0)
        x_offset = max(0.0, (self.width() - tree_w) / 2.0)

        # 1. Draw connections (bezier curves)
        pen_line = QPen(QColor(Colors.BORDER), 2)
        painter.setPen(pen_line)

        node_map = {r.node_id: r for r in self._rects}

        for r in self._rects:
            if r.parent_id and r.parent_id in node_map:
                p = node_map[r.parent_id]
                start_x = p.x + x_offset
                start_y = p.y + p.height / 2
                end_x   = r.x + x_offset
                end_y   = r.y - r.height / 2

                path = QPainterPath()
                path.moveTo(start_x, start_y)
                ctrl1_x = start_x
                ctrl1_y = start_y + (end_y - start_y) / 2
                ctrl2_x = end_x
                ctrl2_y = start_y + (end_y - start_y) / 2
                path.cubicTo(ctrl1_x, ctrl1_y, ctrl2_x, ctrl2_y, end_x, end_y)
                painter.drawPath(path)

        # 2. Draw nodes
        for r in self._rects:
            px_x = int(r.x - r.width / 2 + x_offset)
            px_y = int(r.y - r.height / 2)
            px_w = int(r.width)
            px_h = int(r.height)

            rect_f = QRectF(px_x, px_y, px_w, px_h)

            # Fill colour
            fill = _PALETTE[r.color_index % len(_PALETTE)]

            # Hover highlight: lighten slightly
            if r.node_id == self._hovered_id:
                fill = fill.lighter(120)

            # Background fill
            path = QPainterPath()
            path.addRoundedRect(rect_f, _RADIUS, _RADIUS)
            
            # Use a dark background with colored top border, or solid color?
            # A sleek professional look: Dark block, colored left rim
            painter.fillPath(path, QColor(Colors.BG_DARK))
            
            # Top accent rim
            rim_rect = QRectF(px_x, px_y, px_w, 6)
            rim_path = QPainterPath()
            rim_path.addRoundedRect(rim_rect, _RADIUS, _RADIUS)
            # Clip the bottom edge of the rim to make it flush
            painter.fillPath(rim_path, fill)
            painter.fillRect(QRectF(px_x, px_y + 3, px_w, 3), fill)
            
            # Outline
            if r.node_id == self._selected_id:
                painter.setPen(QPen(_SELECTED_BORDER, 2))
            else:
                painter.setPen(QPen(QColor(Colors.BORDER), 1))
            painter.drawPath(path)

            self._draw_label(painter, r, rect_f, fill)

        painter.end()

    def _draw_label(
        self, painter: QPainter, r: TreeNodeRect, rect_f: QRectF, fill_color: QColor
    ) -> None:
        text_color = QColor("#ffffff")

        # Name line
        name_font = QFont(Fonts.FAMILY_UI if hasattr(Fonts, "FAMILY_UI") else "sans-serif", 11, QFont.Weight.Bold)
        painter.setFont(name_font)
        painter.setPen(text_color)
        fm = QFontMetrics(name_font)
        padding_left = 12
        available = int(r.width) - padding_left - 4

        name = fm.elidedText(r.name, Qt.TextElideMode.ElideRight, available)

        # Percentage & Count line
        pct_font = QFont(Fonts.FAMILY_UI if hasattr(Fonts, "FAMILY_UI") else "sans-serif", 10)
        pct_font.setWeight(QFont.Weight.Normal)
        pct_str = f"{r.pct_parent:.1f}% ({r.count:,})"

        # Vertically centre both lines together
        fm_name = QFontMetrics(name_font)
        fm_pct  = QFontMetrics(pct_font)
        total_h = fm_name.height() + 2 + fm_pct.height()
        top_y   = rect_f.top() + (rect_f.height() - total_h) / 2 + fm_name.ascent()

        painter.setFont(name_font)
        painter.setPen(text_color)
        painter.drawText(
            int(rect_f.left() + padding_left), int(top_y), name
        )

        pct_color = QColor(Colors.FG_SECONDARY)
        painter.setFont(pct_font)
        painter.setPen(pct_color)
        painter.drawText(
            int(rect_f.left() + padding_left),
            int(top_y + fm_name.descent() + 2 + fm_pct.ascent()),
            pct_str,
        )

    # ── Mouse events ──────────────────────────────────────────────────

    def _rect_at(self, pos: QPoint) -> TreeNodeRect | None:
        tree_w = getattr(self, "_tree_width", 0.0)
        x_offset = max(0.0, (self.width() - tree_w) / 2.0)
        for r in self._rects:
            rx = r.x - r.width / 2 + x_offset
            ry = r.y - r.height / 2
            if rx <= pos.x() <= rx + r.width and ry <= pos.y() <= ry + r.height:
                return r
        return None

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        hit = self._rect_at(event.pos())
        if hit:
            if self._hovered_id != hit.node_id:
                self._hovered_id = hit.node_id
                self.update()

                # Count how many samples have this gate
                total = len(self._state.experiment.samples)
                gated = sum(
                    1 for s in self._state.experiment.samples.values()
                    if s.gate_tree.find_node_by_id(hit.node_id) is not None
                )

                self._hover_card.show_for(
                    hit,
                    event.globalPosition().toPoint(),
                    samples_gated=gated,
                    total_samples=total,
                )
        else:
            if self._hovered_id is not None:
                self._hovered_id = None
                self._hover_card.hide()
                self.update()

    def leaveEvent(self, _event) -> None:
        self._hovered_id = None
        self._hover_card.hide()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        hit = self._rect_at(event.pos())
        if hit:
            self._selected_id = hit.node_id
            self.update()
            self.node_clicked.emit(hit.node_id)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        hit = self._rect_at(event.pos())
        if hit:
            self.node_double_clicked.emit(hit.node_id)

    def contextMenuEvent(self, event) -> None:
        hit = self._rect_at(event.pos())
        if not hit:
            return

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {Colors.BG_MEDIUM};
                color: {Colors.FG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {Colors.ACCENT_PRIMARY};
                color: #ffffff;
            }}
        """)
        action_rename = menu.addAction("Rename Gate")
        action_delete = menu.addAction("Delete Gate")
        # Ensure root node cannot be deleted or renamed if necessary, but UI handles that via node logic
        if hit.depth == 0:
            action_delete.setEnabled(False)
            action_rename.setEnabled(False)

        action = menu.exec(event.globalPos())
        if action == action_rename:
            self.rename_requested.emit(hit.node_id)
        elif action == action_delete:
            self.delete_requested.emit(hit.node_id)
