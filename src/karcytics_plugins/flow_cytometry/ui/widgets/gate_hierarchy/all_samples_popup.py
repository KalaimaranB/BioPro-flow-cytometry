"""AllSamplesPopup — floating heatmap panel showing all samples × populations.

Single Responsibility: render the cross-sample grid and tree-branch labels.
Opens as an application-level floating QFrame, not a modal dialog. Dismissed
only by pressing Escape or clicking its own × button — deliberately NOT by
clicking elsewhere, so it can stay open while the rest of the app is used
(e.g. scrolling other panels, or a tutorial step reading it alongside other
widgets) without vanishing the moment something else is clicked.
"""

from __future__ import annotations

from karcytics_sdk.plugin.theme_fallback import Colors
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

from .all_samples_model import AllSamplesModel, PopulationRow

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

    _h = h if h is not None else 0.0
    _s = s if s is not None else 0.0
    _v = v if v is not None else 0.0
    _a = a if a is not None else 1.0

    new_v = max(0.18, _v * (0.35 + 0.65 * pct / 100.0))
    new_s = max(0.2, _s * (0.35 + 0.65 * pct / 100.0))
    c.setHsvF(_h, new_s, new_v, _a)
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
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint,
        )
        self.setObjectName("AllSamplesOverviewPopup")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(640, 460)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
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
        screen = QApplication.primaryScreen()
        if not screen:
            return
        screen_rect: QRect = screen.availableGeometry()

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
        self.setFocus()

    # ── UI ────────────────────────────────────────────────────────────

    def _build_close_button(self) -> QLabel:
        btn = QLabel("×")
        btn.setObjectName("AllSamplesOverviewCloseButton")
        btn.setFixedSize(20, 20)
        btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.mousePressEvent = lambda _e: self.hide()  # type: ignore[method-assign, assignment]
        self._btn_close = btn
        return btn

    def _build_title_bar(self) -> QWidget:
        self._title_bar = QWidget()
        self._title_bar.setFixedHeight(38)
        title_layout = QHBoxLayout(self._title_bar)
        title_layout.setContentsMargins(14, 0, 14, 0)

        self._title_lbl = QLabel("⊞  All Samples — Population Overview")
        title_layout.addWidget(self._title_lbl)
        title_layout.addStretch()

        self._esc_lbl = QLabel("Esc to close")
        title_layout.addWidget(self._esc_lbl)

        title_layout.addSpacing(8)
        title_layout.addWidget(self._build_close_button())
        return self._title_bar

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_title_bar())

        # Split layout for frozen left column and scrollable right columns
        self._split_widget = QWidget()
        self._split_layout = QHBoxLayout(self._split_widget)
        self._split_layout.setContentsMargins(0, 0, 0, 0)
        self._split_layout.setSpacing(0)
        outer.addWidget(self._split_widget, stretch=1)

        # Frozen scroll area (left column)
        self._frozen_scroll = QScrollArea()
        self._frozen_scroll.setWidgetResizable(True)
        self._frozen_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._frozen_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._frozen_scroll.setFixedWidth(240)

        self._frozen_content = QWidget()
        self._frozen_grid = QGridLayout(self._frozen_content)
        self._frozen_grid.setContentsMargins(12, 12, 6, 12)
        self._frozen_grid.setSpacing(3)
        self._frozen_scroll.setWidget(self._frozen_content)

        # Main scroll area (right columns)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)

        self._content = QWidget()
        self._grid = QGridLayout(self._content)
        self._grid.setContentsMargins(6, 12, 12, 12)
        self._grid.setSpacing(3)

        self._scroll.setWidget(self._content)

        self._split_layout.addWidget(self._frozen_scroll)
        self._split_layout.addWidget(self._scroll, stretch=1)

        # Sync vertical scrolling
        frozen_vsb = self._frozen_scroll.verticalScrollBar()
        main_vsb = self._scroll.verticalScrollBar()
        if frozen_vsb and main_vsb:
            frozen_vsb.valueChanged.connect(main_vsb.setValue)
            main_vsb.valueChanged.connect(frozen_vsb.setValue)

        # Legend strip
        self._legend = QWidget()
        self._legend.setFixedHeight(28)
        legend_layout = QHBoxLayout(self._legend)
        legend_layout.setContentsMargins(14, 0, 14, 0)
        legend_layout.setSpacing(16)

        for dot_color, label_text in [
            ("#00bcd4", "Gated"),
            ("#484f58", "Not applied"),
            ("#21262d", "0 events"),
        ]:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {dot_color}; font-size: 10px; background: transparent;")
            lbl = QLabel(label_text)
            lbl.setStyleSheet(
                f"color: {Colors.FG_SECONDARY}; font-size: 10px; background: transparent;"
            )
            legend_layout.addWidget(dot)
            legend_layout.addWidget(lbl)

        legend_layout.addStretch()
        outer.addWidget(self._legend)

        self._apply_theme_styles()

    def _apply_theme_styles(self) -> None:
        """Dynamically refresh colors based on current theme."""
        self.setStyleSheet(f"""
            AllSamplesPopup {{
                background: {Colors.BG_DARKEST};
                border: 1px solid {Colors.BORDER};
                border-radius: 10px;
            }}
        """)
        if hasattr(self, "_title_bar"):
            self._title_bar.setStyleSheet(
                f"background: {Colors.BG_DARK}; border-bottom: 1px solid {Colors.BORDER};"
                " border-top-left-radius: 10px; border-top-right-radius: 10px;"
            )
        if hasattr(self, "_title_lbl"):
            self._title_lbl.setStyleSheet(
                f"color: {Colors.FG_PRIMARY}; font-size: 12px; font-weight: 600;"
                " background: transparent;"
            )
        if hasattr(self, "_esc_lbl"):
            self._esc_lbl.setStyleSheet(
                f"color: {Colors.FG_DISABLED}; font-size: 10px; background: transparent;"
            )
        if hasattr(self, "_btn_close"):
            self._btn_close.setStyleSheet(
                f"color: {Colors.FG_SECONDARY}; font-size: 15px; font-weight: bold;"
                " background: transparent; border-radius: 4px;"
            )
        if hasattr(self, "_scroll"):
            self._scroll.setStyleSheet(
                f"QScrollArea {{ background: transparent; border: none; }}"
                f"QScrollBar:vertical {{ background: {Colors.BG_DARK}; width: 6px; border-radius: 3px; }}"
                f"QScrollBar::handle:vertical {{ background: {Colors.BORDER}; border-radius: 3px; }}"
                f"QScrollBar:horizontal {{ background: {Colors.BG_DARK}; height: 6px; border-radius: 3px; }}"
                f"QScrollBar::handle:horizontal {{ background: {Colors.BORDER}; border-radius: 3px; }}"
            )
        if hasattr(self, "_frozen_scroll"):
            self._frozen_scroll.setStyleSheet(
                f"QScrollArea {{ background: transparent; border: none; border-right: 1px solid {Colors.BORDER}; }}"
                f"QScrollBar:vertical {{ width: 0px; }}"
                f"QScrollBar:horizontal {{ height: 0px; }}"
            )
        if hasattr(self, "_content"):
            self._content.setStyleSheet(f"background: {Colors.BG_DARKEST};")
        if hasattr(self, "_frozen_content"):
            self._frozen_content.setStyleSheet(f"background: {Colors.BG_DARKEST};")
        if hasattr(self, "_legend"):
            self._legend.setStyleSheet(
                f"background: {Colors.BG_DARK}; border-top: 1px solid {Colors.BORDER};"
            )

    def _rebuild_grid(self) -> None:
        """Clear and repopulate the grid from the current model."""
        # Remove all existing widgets
        for grid in (self._grid, self._frozen_grid):
            while grid.count():
                item = grid.takeAt(0)
                if item:
                    w = item.widget()
                    if w:
                        w.deleteLater()

        # Reset column stretches from any previous run
        for grid in (self._grid, self._frozen_grid):
            for c in range(grid.columnCount()):
                grid.setColumnStretch(c, 0)
            for r in range(grid.rowCount()):
                grid.setRowStretch(r, 0)

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
        from PyQt6.QtGui import QFontMetrics as _QFontMetrics

        _hdr_font = _QFont("Inter, sans-serif", 10)
        _hdr_font.setWeight(_QFont.Weight.DemiBold)
        _fm = _QFontMetrics(_hdr_font)
        col_w = max(
            64,
            max((_fm.horizontalAdvance(display_names.get(sid, sid)) + 16) for sid in sample_ids)
            if sample_ids
            else 64,
        )

        # Column 0 = branch labels (expanding) -> goes to frozen grid
        self._frozen_grid.setColumnStretch(0, 1)

        # Trailing stretch column pushes content left -> main grid
        self._grid.setColumnStretch(n_samples, 0)

        # Frozen header spacer
        empty_header = QWidget()
        empty_header.setFixedHeight(28)
        self._frozen_grid.addWidget(empty_header, 0, 0)

        # Column headers (sample names) — row 0 -> main grid
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
            header.mousePressEvent = lambda _e, s=_sid: self.sample_selected.emit(s)  # type: ignore[method-assign, misc]
            header.setToolTip(name)
            self._grid.addWidget(header, 0, col_i)

        # Population rows
        for row_i, pop_row in enumerate(self._model.rows):
            grid_row = row_i + 1

            # Branch label -> frozen grid
            branch_widget = _BranchLabel(pop_row)
            self._frozen_grid.addWidget(
                branch_widget,
                grid_row,
                0,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )

            # Heat cells — match the dynamic column width -> main grid
            for col_i, sid in enumerate(sample_ids):
                val: float | None = pop_row.cells.get(sid)
                cell = _HeatCell(pop_row.color_index, val, col_w)
                self._grid.addWidget(cell, grid_row, col_i, Qt.AlignmentFlag.AlignCenter)

        # Push everything to the top so rows don't spread out vertically
        last_row = len(self._model.rows) + 1
        self._frozen_grid.setRowStretch(last_row, 1)
        self._grid.setRowStretch(last_row, 1)

    # ── Dismiss logic ─────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        if event is None:
            return
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
        painter.drawEllipse(dot_x, y_center - self._DOT_SIZE // 2, self._DOT_SIZE, self._DOT_SIZE)

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
            text_color = QColor(Colors.FG_PRIMARY)
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
