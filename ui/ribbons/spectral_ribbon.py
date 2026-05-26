"""Spectral Ribbon - Access spectral viewing and compensation tools."""

from __future__ import annotations
from typing import TYPE_CHECKING
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from biopro.ui.theme import Colors, Fonts
from biopro.shared.ui.ui_components import SecondaryButton

if TYPE_CHECKING:
    from ...analysis.state import FlowState


class SpectralRibbon(QWidget):
    """Toolbar ribbon for spectral intelligence tools."""

    open_spectral_viewer_requested = pyqtSignal()

    def __init__(self, state: FlowState, parent=None) -> None:
        super().__init__(parent)
        self._state = state
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        title = QLabel("Spectral Analysis:")
        title.setStyleSheet(
            f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;"
            f" font-weight: 600; background: transparent;"
        )
        layout.addWidget(title)

        btn_view = SecondaryButton("🌈 View Spectral Overlap")
        btn_view.setToolTip("Open the Spectral Viewer to see fluorophore emission overlaps")
        btn_view.clicked.connect(self.open_spectral_viewer_requested)
        layout.addWidget(btn_view)

        layout.addStretch()
