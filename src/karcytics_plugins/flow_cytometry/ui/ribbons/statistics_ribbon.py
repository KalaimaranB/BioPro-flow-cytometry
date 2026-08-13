"""Statistics ribbon — placeholder widget.

The Statistics tab now uses the full-screen ``StatisticsExplorer`` widget
which manages all its controls internally.  This module is kept so that
the ribbon stack index alignment (0-5) remains intact.
"""

from __future__ import annotations

from karcytics_sdk.plugin.theme_fallback import Colors
from PyQt6.QtWidgets import QHBoxLayout, QWidget

from karcytics_plugins.flow_cytometry.analysis.state import FlowState


class StatisticsRibbon(QWidget):
    """Empty placeholder ribbon for the Statistics tab.

    All statistics controls live inside :class:`~ui.widgets.statistics_explorer.StatisticsExplorer`.
    """

    def __init__(self, state: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet(f"background: {Colors.BG_DARK};")
        self._apply_theme_styles()

    def _apply_theme_styles(self) -> None:
        """Dynamically refresh colors when theme changes."""
        self.setObjectName(self.__class__.__name__)
        self.setStyleSheet(
            f"QWidget#{self.objectName()} {{ background: {Colors.BG_DARK}; border-bottom: 1px solid {Colors.BORDER}; }}"
        )
