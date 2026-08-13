"""Checkable sample list shared by the Statistics and Comparisons tabs.

Extracted from the near-identical duplicated implementations that used to
live independently in StatisticsExplorer and ComparisonsViewer.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QHBoxLayout, QListWidgetItem, QVBoxLayout, QWidget

from karcytics_plugins.flow_cytometry.ui.widgets.checkbox_style import checkbox_qss

if TYPE_CHECKING:
    from karcytics_plugins.flow_cytometry.analysis.experiment import Sample


def _get_theme_tokens():
    if "karcytics.ui.theme" in sys.modules:
        tm = sys.modules["karcytics.ui.theme"]
        return tm.Colors, tm.theme_manager
    try:
        from karcytics.ui.theme import Colors, theme_manager

        return Colors, theme_manager
    except ImportError:
        from karcytics_sdk.plugin.theme_fallback import Colors, theme_manager

        return Colors, theme_manager


class SampleChecklistWidget(QWidget):
    """Checkable list of samples plus All/None buttons.

    Signals:
        selectionChanged: emitted whenever the set of checked samples changes
            (user toggle, All/None, or a refresh() call).
    """

    selectionChanged = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from karcytics_sdk.plugin.components import BioListWidget, SecondaryButton

        # Samples never-before-seen default to checked; samples the widget has
        # already shown keep whatever check state the user last left them in.
        self._known_sample_ids: set[str] = set()

        # Single-select ("radio") mode: some plot types (FMO, Pseudocolor
        # Overlay) are only defined for exactly one sample. When enabled,
        # checking a sample unchecks every other one instead of leaving the
        # UI free to build a combination the renderer can't handle.
        self._single_select = False

        self._BioListWidget = BioListWidget
        self._SecondaryButton = SecondaryButton
        self._build_ui()

        _, theme_manager = _get_theme_tokens()
        theme_manager.theme_changed.connect(self._apply_theme_styles)
        self.destroyed.connect(self._cleanup)

    def _cleanup(self) -> None:
        _, theme_manager = _get_theme_tokens()
        try:
            theme_manager.theme_changed.disconnect(self._apply_theme_styles)
        except (TypeError, RuntimeError):
            pass

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.list_widget = self._BioListWidget()
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setToolTip("Check samples to include")
        self.list_widget.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        mini_ss = "QPushButton { padding: 3px 10px; min-height: 26px; }"
        btn_all = self._SecondaryButton("All")
        btn_all.setStyleSheet(mini_ss)
        btn_all.clicked.connect(lambda: self.set_all_checked(True))
        btn_none = self._SecondaryButton("None")
        btn_none.setStyleSheet(mini_ss)
        btn_none.clicked.connect(lambda: self.set_all_checked(False))
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._apply_theme_styles()

    def refresh(self, samples: dict[str, Sample]) -> None:
        """Repopulate from {sample_id: Sample}, preserving prior checks.

        A sample never shown by this widget before defaults to checked (so
        newly loaded/added samples are included immediately); a sample it has
        shown before keeps the user's last check state for it. In
        single-select mode, at most one item ends up checked — the first
        candidate (previously-checked, or new) wins and the rest stay
        unchecked, preserving the radio invariant across a refresh.
        """
        prev_checked = set(self.get_checked_sample_ids())

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        Colors, _ = _get_theme_tokens()
        already_checked_one = False
        for sid, sample in samples.items():
            item = QListWidgetItem(sample.display_name)
            item.setData(Qt.ItemDataRole.UserRole, sid)
            item.setForeground(QColor(Colors.FG_PRIMARY))
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            is_new = sid not in self._known_sample_ids
            should_check = sid in prev_checked or is_new
            if self._single_select:
                should_check = should_check and not already_checked_one
            item.setCheckState(Qt.CheckState.Checked if should_check else Qt.CheckState.Unchecked)
            already_checked_one = already_checked_one or should_check
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)

        self._known_sample_ids.update(samples.keys())

        row_h = self.list_widget.sizeHintForRow(0) if self.list_widget.count() > 0 else 24
        self.list_widget.setFixedHeight(max(32, self.list_widget.count() * max(24, row_h) + 4))

        self.selectionChanged.emit()

    def get_checked_sample_ids(self) -> list[str]:
        result = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result

    def set_all_checked(self, checked: bool) -> None:
        """Check/uncheck every sample. In single-select mode, "check all"
        checks only the first sample instead of violating the one-sample
        constraint (mirrors the equivalent single-channel-mode behaviour).
        """
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if not item:
                continue
            if self._single_select and checked:
                item.setCheckState(Qt.CheckState.Checked if i == 0 else Qt.CheckState.Unchecked)
            else:
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.list_widget.blockSignals(False)
        self.selectionChanged.emit()

    def set_single_select(self, enabled: bool) -> None:
        """Switch between free multi-select and single-select (radio) mode.

        Enabling it with more than one sample already checked collapses the
        selection down to the first checked one; enabling it with none
        checked defaults to the first available sample so there's always
        something to render.
        """
        if enabled == self._single_select:
            return
        self._single_select = enabled
        if not enabled:
            return

        checked = self.get_checked_sample_ids()
        self.list_widget.blockSignals(True)
        if checked:
            keep = checked[0]
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) != keep:
                    item.setCheckState(Qt.CheckState.Unchecked)
        elif self.list_widget.count() > 0:
            first = self.list_widget.item(0)
            if first:
                first.setCheckState(Qt.CheckState.Checked)
        self.list_widget.blockSignals(False)
        self.selectionChanged.emit()

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if self._single_select and item.checkState() == Qt.CheckState.Checked:
            self.list_widget.blockSignals(True)
            for i in range(self.list_widget.count()):
                other = self.list_widget.item(i)
                if other and other is not item:
                    other.setCheckState(Qt.CheckState.Unchecked)
            self.list_widget.blockSignals(False)
        self.selectionChanged.emit()

    def _apply_theme_styles(self) -> None:
        Colors, _ = _get_theme_tokens()
        self.list_widget.setStyleSheet(
            f"QListWidget {{ background: {Colors.BG_DARKEST}; border: 1px solid {Colors.BORDER};"
            f" border-radius: 4px; color: {Colors.FG_PRIMARY}; }}"
            f"QListWidget::item {{ color: {Colors.FG_PRIMARY}; padding: 4px; border-bottom: 1px solid {Colors.BORDER}; }}"
            f"QListWidget::item:hover {{ background: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY}; }}"
            f"QListWidget::item:selected {{ background: {Colors.BG_MEDIUM}; color: {Colors.FG_PRIMARY}; }}"
            + checkbox_qss()
        )
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item:
                item.setForeground(QColor(Colors.FG_PRIMARY))
