"""AllSamplesPopup — floating heatmap panel showing all samples × populations.

Single Responsibility: render the cross-sample grid and tree-branch labels.
Opens as an application-level floating QFrame, not a modal dialog.
Dismissed by clicking outside or pressing Escape.
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QKeyEvent,
    QPainter,
    QPainterPath,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

try:
    from biopro.ui.theme import Colors, Fonts
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
        FAMILY_UI = "Inter, SF Pro Display, sans-serif"
        SIZE_SMALL = 11


from .all_samples_model import AllSamplesModel, PopulationRow

# Palette: index → hex colour string (matches IcicleLayoutEngine)
_PALETTE_HEX = [
    "#7c4dff",  # 0 purple
    "#00bcd4",  # 1 teal
    "#42a5f5",  # 2 blue
    "#ffa726",  # 3 orange
    "#ef5350",  # 4 pink
    "#66bb6a",  # 5 green
]


def _saturate(hex_color: str, pct: float) -> str:
    """Darken a colour proportionally to low event percentage."""
    c = QColor(hex_color)
    h, s, v, a = c.getHsvF()
    v = max(0.18, v * (0.35 + 0.65 * pct / 100.0))
    s = max(0.2, s * (0.35 + 0.65 * pct / 100.0))
    c.setHsvF(h, s, v, a)
    return c.name()


class AllSamplesPopup(QFrame):
    """Floating popup showing the full cross-sample heatmap with tree branches.

    Usage::
        popup = AllSamplesPopup(parent_widget)
        popup.show_near(trigger_button, state, reference_sample_id)
    """

    sample_selected = pyqtSignal(str)  # Emitted when a column header is clicked

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(640, 460)
        self._model = AllSamplesModel()
        self._setup_ui()

    # ── Public API ────────────────────────────────────────────────────

    def show_near(
        self,
        trigger: QWidget,
        state,
        reference_sample_id: str,
    ) -> None:
        """Rebuild content and show the popup anchored below the trigger widget.

        Args:
            trigger:             Button or widget that was clicked.
            state:               FlowState — read-only.
            reference_sample_id: Sample whose gate tree defines row order.
        """
        self._model.build(state, reference_sample_id)
        self._rebuild_grid()

        # Position: below trigger, shifted left if near screen edge
        global_bottom_left = trigger.mapToGlobal(QPoint(0, trigger.height() + 4))
        screen_rect: QRect = QApplication.primaryScreen().availableGeometry()

        x = global_bottom_left.x()
        y = global_bottom_left.y()
        if x + self.width() > screen_rect.right():
            x = screen_rect.right() - self.width() - 8
        if y + self.height() > screen_rect.bottom():
            y = global_bottom_left.y() - trigger.height() - self.height() - 4

        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()

    # ── UI ────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            AllSamplesPopup {
                background: #0d1117;
                border: 1px solid #2a4a5a;
                border-radius: 10px;
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Title bar
        title_bar = QWidget()
        title_bar.setFixedHeight(38)
        title_bar.setStyleSheet(
            "background: #161b22; border-bottom: 1px solid #2a4a5a;"
            " border-top-left-radius: 10px; border-top-right-radius: 10px;"
        )
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(14, 0, 14, 0)

        title_lbl = QLabel("⊞  All Samples — Population Overview")
        title_lbl.setStyleSheet(
            f"color: {Colors.FG_PRIMARY}; font-size: 12px; font-weight: 600;"
            " background: transparent;"
        )
        title_layout.addWidget(title_lbl)
        title_layout.addStretch()

        esc_lbl = QLabel("Esc to close")
        esc_lbl.setStyleSheet(
            f"color: {Colors.FG_DISABLED}; font-size: 10px; background: transparent;"
        )
        title_layout.addWidget(esc_lbl)
        outer.addWidget(title_bar)

        # Scroll area containing the grid
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: #161b22; width: 6px; border-radius: 3px; }"
            "QScrollBar::handle:vertical { background: #2a4a5a; border-radius: 3px; }"
            "QScrollBar:horizontal { background: #161b22; height: 6px; border-radius: 3px; }"
            "QScrollBar::handle:horizontal { background: #2a4a5a; border-radius: 3px; }"
        )

        self._content = QWidget()
        self._content.setStyleSheet("background: #0d1117;")
        self._grid = QGridLayout(self._content)
        self._grid.setContentsMargins(12, 12, 12, 12)
        self._grid.setSpacing(3)

        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll, stretch=1)

        # Legend strip
        legend = QWidget()
        legend.setFixedHeight(28)
        legend.setStyleSheet("background: #161b22; border-top: 1px solid #2a4a5a;")
        legend_layout = QHBoxLayout(legend)
        legend_layout.setContentsMargins(14, 0, 14, 0)
        legend_layout.setSpacing(16)

        for dot_color, label_text in [
            ("#00bcd4", "Gated"),
            ("#484f58", "Not applied"),
            ("#21262d", "0 events"),
        ]:
            dot = QLabel("●")
            dot.setStyleSheet(
                f"color: {dot_color}; font-size: 10px; background: transparent;"
            )
            lbl = QLabel(label_text)
            lbl.setStyleSheet(
                f"color: {Colors.FG_SECONDARY}; font-size: 10px; background: transparent;"
            )
            legend_layout.addWidget(dot)
            legend_layout.addWidget(lbl)

        legend_layout.addStretch()
        outer.addWidget(legend)

    def _rebuild_grid(self) -> None:
        """Clear and repopulate the grid from the current model."""
        # Remove all existing widgets
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Reset column stretches from any previous run
        for c in range(self._grid.columnCount()):
            self._grid.setColumnStretch(c, 0)
        for r in range(self._grid.rowCount()):
            self._grid.setRowStretch(r, 0)

        if not self._model.rows:
            empty = QLabel("No gates found on the reference sample.")
            empty.setStyleSheet(
                f"color: {Colors.FG_DISABLED}; font-size: 11px; background: transparent;"
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(empty, 0, 0)
            return

        sample_ids = self._model.sample_ids
        display_names = self._model.sample_display_names
        n_samples = len(sample_ids)

        # Compute a dynamic column width: at least 64px but grows with the
        # longest sample display name so nothing gets cut off.
        from PyQt6.QtGui import QFont as _QFont
        from PyQt6.QtGui import QFontMetrics as _QFM

        _hdr_font = _QFont("Inter, sans-serif", 10)
        _hdr_font.setWeight(_QFont.Weight.DemiBold)
        _fm = _QFM(_hdr_font)
        col_w = max(
            64,
            max(
                (_fm.horizontalAdvance(display_names.get(sid, sid)) + 16)
                for sid in sample_ids
            )
            if sample_ids
            else 64,
        )

        # Column 0 = branch labels (expanding), columns 1..N = fixed-width heat cells,
        # trailing stretch column pushes content left.
        self._grid.setColumnStretch(0, 1)
        self._grid.setColumnStretch(n_samples + 1, 0)

        # Column headers (sample names) — row 0
        for col_i, sid in enumerate(sample_ids):
            name = display_names.get(sid, sid)
            header = QLabel(name)
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.setFixedWidth(col_w)
            header.setFixedHeight(28)
            header.setStyleSheet(
                f"color: {Colors.FG_SECONDARY}; font-size: 10px; font-weight: 600;"
                " background: transparent;"
            )
            header.setCursor(Qt.CursorShape.PointingHandCursor)
            _sid = sid
            header.mousePressEvent = lambda _e, s=_sid: self.sample_selected.emit(s)
            header.setToolTip(name)
            self._grid.addWidget(header, 0, col_i + 1)

        # Population rows
        for row_i, pop_row in enumerate(self._model.rows):
            grid_row = row_i + 1

            # Branch label
            branch_widget = _BranchLabel(pop_row)
            self._grid.addWidget(
                branch_widget,
                grid_row,
                0,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )

            # Heat cells — match the dynamic column width
            for col_i, sid in enumerate(sample_ids):
                val: float | None = pop_row.cells.get(sid)
                cell = _HeatCell(pop_row.color_index, val, col_w)
                self._grid.addWidget(
                    cell, grid_row, col_i + 1, Qt.AlignmentFlag.AlignCenter
                )

        # Push everything to the top so rows don't spread out vertically
        last_row = len(self._model.rows) + 1
        self._grid.setRowStretch(last_row, 1)

    # ── Dismiss logic ─────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)


class _BranchLabel(QWidget):
    """Draws the tree-branch connector + coloured dot + population name."""

    _DOT_SIZE = 8

    def __init__(self, row: PopulationRow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._row = row
        self.setFixedHeight(30)
        self.setMinimumWidth(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        palette_hex = (
            _PALETTE_HEX[self._row.color_index % len(_PALETTE_HEX)]
            if 0 <= self._row.color_index < len(_PALETTE_HEX)
            else "#8b949e"
        )
        dot_color = QColor(palette_hex)
        branch_color = QColor("#2a4a5a")
        text_color = QColor("#e6edf3")

        # Branch string
        branch = self._row.branch_str
        font = QFont("Courier New, monospace", 9)
        painter.setFont(font)
        painter.setPen(branch_color)
        fm = QFontMetrics(font)
        branch_w = fm.horizontalAdvance(branch)
        y_center = self.height() // 2
        painter.drawText(4, y_center + fm.ascent() // 2, branch)

        # Coloured dot
        dot_x = 4 + branch_w + 4
        painter.setBrush(dot_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(
            dot_x, y_center - self._DOT_SIZE // 2, self._DOT_SIZE, self._DOT_SIZE
        )

        # Name text
        name_font = QFont("Inter, sans-serif", 10)
        painter.setFont(name_font)
        painter.setPen(text_color)
        fm2 = QFontMetrics(name_font)
        name_x = dot_x + self._DOT_SIZE + 6
        available = self.width() - name_x - 4
        name = fm2.elidedText(self._row.name, Qt.TextElideMode.ElideRight, available)
        painter.drawText(name_x, y_center + fm2.ascent() // 2, name)

        painter.end()


class _HeatCell(QWidget):
    """One heatmap cell: coloured block with percentage text."""

    def __init__(
        self,
        color_index: int,
        value: float | None,
        col_width: int = 64,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color_index = color_index
        self._value = value
        self.setFixedSize(col_width, 30)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._value is None:
            # Not applied
            fill = QColor("#21262d")
            text_color = QColor("#484f58")
            label = "—"
        elif self._value == 0.0:
            fill = QColor("#1a2030")
            text_color = QColor("#484f58")
            label = "0%"
        else:
            base = _PALETTE_HEX[self._color_index % len(_PALETTE_HEX)]
            fill = QColor(_saturate(base, self._value))
            text_color = QColor("#ffffff")
            label = f"{self._value:.1f}%"

        path = QPainterPath()
        path.addRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 4, 4)
        painter.fillPath(path, fill)

        font = QFont("Inter, sans-serif", 9)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(
            QRect(0, 0, self.width(), self.height()),
            Qt.AlignmentFlag.AlignCenter,
            label,
        )
        painter.end()
