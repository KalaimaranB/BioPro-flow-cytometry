"""Encyclopedia Ribbon - Access biological marker databases."""

from __future__ import annotations

from typing import TYPE_CHECKING

from biopro.shared.ui.ui_components import SecondaryButton
from biopro.ui.theme import Colors, Fonts
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

if TYPE_CHECKING:
    from analysis.state import FlowState


class EncyclopediaRibbon(QWidget):
    """Toolbar ribbon for biological encyclopedia tools."""

    open_encyclopedia_requested = pyqtSignal()

    def __init__(self, state: FlowState, parent=None) -> None:
        super().__init__(parent)
        self._state = state
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        title = QLabel("Biological Encyclopedia:")
        title.setStyleSheet(
            f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;"
            f" font-weight: 600; background: transparent;"
        )
        layout.addWidget(title)

        btn_view = SecondaryButton("📖 Search Markers")
        btn_view.setToolTip("Open the Marker Encyclopedia to search for biological details")
        btn_view.clicked.connect(self.open_encyclopedia_requested)
        layout.addWidget(btn_view)

        layout.addStretch()
