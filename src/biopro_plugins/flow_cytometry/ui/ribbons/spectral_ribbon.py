"""Spectral Ribbon - Access spectral viewing and compensation tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QWidget

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

        layout.addStretch()

        self._apply_theme_styles()

    def _apply_theme_styles(self) -> None:
        """Dynamically refresh colors when theme changes."""
        try:
            from biopro.ui.theme import Colors
        except ImportError:
            from biopro_sdk.plugin.theme_fallback import Colors
        self.setObjectName(self.__class__.__name__)
        self.setStyleSheet(
            f"QWidget#{self.objectName()} {{ background: {Colors.BG_DARK}; border-bottom: 1px solid {Colors.BORDER}; }}"
        )
