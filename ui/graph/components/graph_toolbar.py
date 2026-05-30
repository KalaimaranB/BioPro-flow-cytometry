"""Graph Toolbar — Navigation and breadcrumbs for GraphWindow."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

try:
    from biopro.ui.theme import Colors, Fonts
except ImportError:
    class Colors:
        BG_DARKEST   = "#0d1117"
        BG_DARK      = "#161b22"
        BG_MEDIUM    = "#21262d"
        FG_PRIMARY   = "#e6edf3"
        FG_SECONDARY = "#8b949e"
        BORDER       = "#30363d"
        ACCENT_PRIMARY = "#00bcd4"
    class Fonts:
        SIZE_SMALL = 11

class GraphToolbar(QWidget):
    """Navigation and breadcrumbs for GraphWindow."""

    navigation_requested = pyqtSignal(str)  # "next_sample", "prev_sample", "parent_gate"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Prev / Next sample arrows
        self._btn_prev = QPushButton("◀ Prev Sample")
        self._btn_next = QPushButton("Next Sample ▶")
        for btn in (self._btn_prev, self._btn_next):
            btn.setFixedHeight(24)
            self._style_btn(btn)
            layout.addWidget(btn)
            
        self._btn_prev.clicked.connect(lambda: self.navigation_requested.emit("prev_sample"))
        self._btn_next.clicked.connect(lambda: self.navigation_requested.emit("next_sample"))
        
        layout.addSpacing(16)
        
        # Up to parent button
        self._btn_parent = QPushButton("↑ Parent Gate")
        self._btn_parent.setFixedHeight(24)
        self._style_btn(self._btn_parent)
        self._btn_parent.setVisible(False)
        self._btn_parent.clicked.connect(lambda: self.navigation_requested.emit("parent_gate"))
        layout.addWidget(self._btn_parent)

        self._breadcrumb = QLabel()
        self._breadcrumb.setStyleSheet(
            f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;"
            f" background: {Colors.BG_DARK}; padding: 4px 8px;"
            f" border-radius: 4px;"
        )
        layout.addWidget(self._breadcrumb)
        layout.addStretch()

    def _style_btn(self, btn: QPushButton) -> None:
        btn.setStyleSheet(
            f"QPushButton {{ background: {Colors.BG_MEDIUM};"
            f" color: {Colors.FG_PRIMARY}; border: 1px solid {Colors.BORDER};"
            f" border-radius: 3px; font-size: 11px; font-weight: 600; padding: 2px 8px; }}"
            f"QPushButton:hover {{ background: {Colors.BG_DARK};"
            f" color: {Colors.ACCENT_PRIMARY}; }}"
        )

    def set_parent_button_visible(self, visible: bool) -> None:
        self._btn_parent.setVisible(visible)

    def set_breadcrumb_text(self, text: str) -> None:
        self._breadcrumb.setText(text)
