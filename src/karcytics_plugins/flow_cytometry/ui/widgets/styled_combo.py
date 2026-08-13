import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QListView


def _get_theme_tokens():
    if "karcytics.ui.theme" in sys.modules:
        tm = sys.modules["karcytics.ui.theme"]
        return tm.Colors, tm.Fonts, tm.theme_manager
    try:
        from karcytics.ui.theme import Colors, Fonts, theme_manager

        return Colors, Fonts, theme_manager
    except ImportError:
        from karcytics_sdk.plugin.theme_fallback import Colors, Fonts, theme_manager

        return Colors, Fonts, theme_manager


class FlowComboBox(QComboBox):
    """A combo box that prevents text truncation.

    Automatically expands its dropdown menu to fit wide contents
    and disables Ellipsis truncation.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Completely prevents the combobox from shrinking and hiding text in the collapsed state
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

        view = QListView()
        view.setTextElideMode(Qt.TextElideMode.ElideNone)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setView(view)

        try:
            _, _, tm = _get_theme_tokens()
            tm.theme_changed.connect(self._apply_theme_styles)
        except Exception:
            pass

        self._apply_theme_styles()

    def _apply_theme_styles(self) -> None:
        """Dynamically refresh colors based on current theme."""
        Colors, Fonts, _ = _get_theme_tokens()
        self.setStyleSheet(
            f"QComboBox {{ background: {Colors.BG_MEDIUM};"
            f" color: {Colors.FG_PRIMARY}; border: 1px solid {Colors.BORDER};"
            f" border-radius: 4px; padding: 4px 8px;"
            f" font-size: {Fonts.SIZE_SMALL}px; }}"
            f"QComboBox::drop-down {{ border-left: 1px solid {Colors.BORDER}; }}"
            f"QComboBox QAbstractItemView {{ min-width: 200px; padding: 4px; background: {Colors.BG_DARKEST}; color: {Colors.FG_PRIMARY}; selection-background-color: {Colors.ACCENT_PRIMARY}; selection-color: {Colors.BG_DARKEST}; border: 1px solid {Colors.BORDER}; outline: none; }}"
            f"QComboBox QAbstractItemView::item {{ color: {Colors.FG_PRIMARY}; min-height: 24px; padding: 2px 4px; }}"
            f"QComboBox QAbstractItemView::item:hover {{ background-color: {Colors.BG_MEDIUM}; color: {Colors.FG_PRIMARY}; }}"
            f"QComboBox QAbstractItemView::item:selected {{ background-color: {Colors.ACCENT_PRIMARY}; color: {Colors.BG_DARKEST}; }}"
        )

    def showPopup(self):
        """Dynamically ensure the popup list fits all text before showing."""
        width = self.width()
        font_metrics = self.fontMetrics()
        for i in range(self.count()):
            text_width = font_metrics.horizontalAdvance(self.itemText(i)) + 30
            width = max(width, text_width)
        self.view().setMinimumWidth(width)
        super().showPopup()
