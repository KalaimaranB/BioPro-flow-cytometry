"""Grouped population tree shared by the Statistics and Comparisons tabs.

Replaces the old per-sample-duplicated tree (one full nested gate hierarchy
repeated under every checked sample) with two sections:

* "Shared Populations" — populations present under the same name in *every*
  checked sample (the normal result of group gate propagation). Checking one
  applies it to every sample that has it.
* "Sample-Specific" — a collapsed sub-tree per sample for anything that
  doesn't match across all checked samples.

A search box filters both sections by label text, which is what actually
solves the "massive set of populations" scaling problem the grouping alone
doesn't: even within "Shared" or one sample's "Specific" list there can be
many rows.

Single-population "radio" mode (used by plot types that take exactly one
population per sample, e.g. Violin/FMO in Comparisons) intentionally keeps
the old flat per-sample tree instead of the Shared/Specific grouping: radio
selection is inherently a per-sample choice, so cross-sample grouping adds
nothing there, and reusing the simple flat layout avoids having to define
what "check a shared row" means under a one-per-sample constraint.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from karcytics_plugins.flow_cytometry.analysis.population_matching import (
    ALL_EVENTS_LABEL,
    PATH_SEP,
    PopulationGroups,
    compute_population_groups,
)
from karcytics_plugins.flow_cytometry.ui.widgets.checkbox_style import checkbox_qss

if TYPE_CHECKING:
    from karcytics_plugins.flow_cytometry.analysis.experiment import Sample

# Sentinel stored in Qt.ItemDataRole.UserRole for non-checkable header/sample
# rows, matching the `False` sentinel already used by the legacy per-sample
# trees this widget replaces.
_HEADER = False
_SHARED_ROLE = "__shared__"


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


def _filter_item(item: QTreeWidgetItem, needle: str) -> bool:
    """Hide rows that don't match `needle` unless a descendant matches. Returns visibility."""
    self_match = (not needle) or (needle in item.text(0).lower())
    child_visible = False
    for c in range(item.childCount()):
        child = item.child(c)
        if child is not None and _filter_item(child, needle):
            child_visible = True
    visible = self_match or child_visible
    item.setHidden(not visible)
    return visible


class PopulationTreeWidget(QWidget):
    """Population checklist: grouped Shared/Sample-Specific (multi-select) or
    flat per-sample radio selection (single-select), with a search filter.

    Signals:
        selectionChanged: emitted whenever the checked-population set changes.
    """

    selectionChanged = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._multi_select = True
        self._samples: dict[str, Sample] = {}
        self._checked_sample_ids: list[str] = []
        self._groups: PopulationGroups = PopulationGroups()

        # Multi-select persistent check state, keyed by label-path.
        self._checked_shared: set[str] = set()
        self._known_shared: set[str] = set()
        self._checked_per_sample: dict[str, set[str]] = {}
        self._known_per_sample: dict[str, set[str]] = {}

        self._search_text = ""

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

    # ── UI construction ─────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        from karcytics_sdk.plugin.components import SecondaryButton

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search populations...")
        self._search_box.textChanged.connect(self._on_search_changed)
        layout.addWidget(self._search_box)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumHeight(200)
        layout.addWidget(self.tree)

        btn_row = QHBoxLayout()
        mini_ss = "QPushButton { padding: 3px 10px; min-height: 26px; }"
        btn_all = SecondaryButton("All")
        btn_all.setStyleSheet(mini_ss)
        btn_all.clicked.connect(lambda: self.check_all(True))
        btn_none = SecondaryButton("None")
        btn_none.setStyleSheet(mini_ss)
        btn_none.clicked.connect(lambda: self.check_all(False))
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._apply_theme_styles()

    # ── Public API ───────────────────────────────────────────────────────────

    def set_multi_select(self, enabled: bool) -> None:
        """Switch between grouped multi-select and flat per-sample radio mode."""
        if enabled == self._multi_select:
            return
        self._multi_select = enabled
        self._rebuild()

    def refresh(self, samples: dict[str, Sample], checked_sample_ids: list[str]) -> None:
        """Recompute population groups for the checked samples and redraw."""
        self._samples = samples
        self._checked_sample_ids = [sid for sid in checked_sample_ids if sid in samples]
        self._groups = compute_population_groups([samples[sid] for sid in self._checked_sample_ids])

        # New populations default to checked the first time they're seen;
        # afterwards the user's own check state is preserved across refreshes.
        for label in self._groups.shared:
            if label not in self._known_shared:
                self._known_shared.add(label)
                self._checked_shared.add(label)
        for sid, labels in self._groups.per_sample.items():
            known = self._known_per_sample.setdefault(sid, set())
            checked = self._checked_per_sample.setdefault(sid, set())
            for label in labels:
                if label not in known:
                    known.add(label)
                    checked.add(label)

        self._rebuild()

    def check_all(self, checked: bool) -> None:
        if self._multi_select:
            if checked:
                self._checked_shared = set(self._groups.shared)
                self._checked_per_sample = {
                    sid: set(labels) for sid, labels in self._groups.per_sample.items()
                }
            else:
                self._checked_shared = set()
                self._checked_per_sample = {sid: set() for sid in self._groups.per_sample}
            self._rebuild()
        else:
            state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            self.tree.blockSignals(True)
            it = QTreeWidgetItemIterator(self.tree)
            while it.value():
                item = it.value()
                if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                    item.setCheckState(0, state)
                it += 1
            self.tree.blockSignals(False)
        self.selectionChanged.emit()

    def get_checked_populations(self) -> list[tuple[str, str | None, str]]:
        """Return (sample_id, node_id, label) triples for every checked population."""
        if not self._multi_select:
            return self._get_checked_from_tree()

        result: list[tuple[str, str | None, str]] = []
        for sid in self._checked_sample_ids:
            node_idx = self._groups.node_index.get(sid, {})
            for label in self._checked_shared:
                if label in node_idx:
                    result.append((sid, node_idx[label], label))
            for label in self._checked_per_sample.get(sid, set()):
                if label in node_idx:
                    result.append((sid, node_idx[label], label))
        return result

    def set_search_text(self, text: str) -> None:
        self._search_box.setText(text)

    # ── Rebuild ──────────────────────────────────────────────────────────────

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top is not None:
                _filter_item(top, self._search_text)

    def _rebuild(self) -> None:
        try:
            self.tree.itemChanged.disconnect()
        except TypeError:
            pass

        self.tree.blockSignals(True)
        self.tree.clear()

        if self._multi_select:
            self._rebuild_multi_select()
            self.tree.itemChanged.connect(self._on_item_changed_multi)
        else:
            self._rebuild_single_select()
            self.tree.itemChanged.connect(self._on_pop_item_changed_single)

        self.tree.blockSignals(False)
        self._apply_theme_styles()

        if self._search_text:
            for i in range(self.tree.topLevelItemCount()):
                top = self.tree.topLevelItem(i)
                if top is not None:
                    _filter_item(top, self._search_text)

    def _rebuild_multi_select(self) -> None:
        shared_header = QTreeWidgetItem([f"▾ Shared Populations ({len(self._groups.shared)})"])
        shared_header.setData(0, Qt.ItemDataRole.UserRole, _HEADER)
        shared_header.setData(0, Qt.ItemDataRole.UserRole + 1, _HEADER)
        shared_header.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.tree.addTopLevelItem(shared_header)
        self._build_nested_rows(
            shared_header,
            self._groups.shared,
            role_data=_SHARED_ROLE,
            negated_lookup=self._negated_for_shared,
            checked_lookup=lambda label: label in self._checked_shared,
        )
        shared_header.setExpanded(True)

        specific_samples = [
            sid for sid in self._checked_sample_ids if self._groups.per_sample.get(sid)
        ]
        specific_header = QTreeWidgetItem(
            [f"▾ Sample-Specific ({len(specific_samples)} sample(s))"]
        )
        specific_header.setData(0, Qt.ItemDataRole.UserRole, _HEADER)
        specific_header.setData(0, Qt.ItemDataRole.UserRole + 1, _HEADER)
        specific_header.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.tree.addTopLevelItem(specific_header)

        for sid in specific_samples:
            sample = self._samples.get(sid)
            labels = self._groups.per_sample.get(sid, [])
            sample_header = QTreeWidgetItem(
                [f"{sample.display_name if sample else sid} ({len(labels)})"]
            )
            sample_header.setData(0, Qt.ItemDataRole.UserRole, _HEADER)
            sample_header.setData(0, Qt.ItemDataRole.UserRole + 1, _HEADER)
            sample_header.setFlags(Qt.ItemFlag.ItemIsEnabled)
            specific_header.addChild(sample_header)
            self._build_nested_rows(
                sample_header,
                labels,
                role_data=sid,
                negated_lookup=lambda label, _sid=sid: self._negated_for_sample(_sid, label),
                checked_lookup=lambda label, _sid=sid: (
                    label in self._checked_per_sample.get(_sid, set())
                ),
            )

    def _build_nested_rows(
        self,
        header_item: QTreeWidgetItem,
        labels: list[str],
        role_data: str,
        negated_lookup,
        checked_lookup,
    ) -> None:
        built: dict[str, QTreeWidgetItem] = {}
        for label in sorted(labels, key=lambda label: label.count(PATH_SEP)):
            if label == ALL_EVENTS_LABEL:
                parent_item, icon, leaf = header_item, "⬡  ", ALL_EVENTS_LABEL
            else:
                parent_path = label.rsplit(PATH_SEP, 1)[0] if PATH_SEP in label else None
                parent_item = header_item
                if parent_path is not None:
                    found = built.get(parent_path)
                    if found is not None:
                        parent_item = found
                leaf = label.rsplit(PATH_SEP, 1)[-1]
                icon = "⊘ " if negated_lookup(label) else "◆ "
            item = QTreeWidgetItem([f"{icon}{leaf}"])
            item.setData(0, Qt.ItemDataRole.UserRole, role_data)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, label)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                0, Qt.CheckState.Checked if checked_lookup(label) else Qt.CheckState.Unchecked
            )
            parent_item.addChild(item)
            built[label] = item

    def _negated_for_shared(self, label: str) -> bool:
        for sid in self._checked_sample_ids:
            node_id = self._groups.node_index.get(sid, {}).get(label)
            if node_id:
                return self._negated_for_sample(sid, label)
        return False

    def _negated_for_sample(self, sid: str, label: str) -> bool:
        node_id = self._groups.node_index.get(sid, {}).get(label)
        sample = self._samples.get(sid)
        if not node_id or not sample or not sample.gate_tree:
            return False
        node = sample.gate_tree.find_node_by_id(node_id)
        return bool(node and node.negated)

    def _on_item_changed_multi(self, item: QTreeWidgetItem, _column: int) -> None:
        role = item.data(0, Qt.ItemDataRole.UserRole)
        label = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if role is _HEADER or label is _HEADER:
            return
        checked = item.checkState(0) == Qt.CheckState.Checked
        if role == _SHARED_ROLE:
            bucket = self._checked_shared
        else:
            bucket = self._checked_per_sample.setdefault(role, set())
        if checked:
            bucket.add(label)
        else:
            bucket.discard(label)
        self.selectionChanged.emit()

    # ── Single-select (radio) mode: legacy flat per-sample tree ────────────────

    def _rebuild_single_select(self) -> None:
        for sid in self._checked_sample_ids:
            sample = self._samples.get(sid)
            if not sample or not sample.gate_tree:
                continue

            sample_item = QTreeWidgetItem([sample.display_name])
            sample_item.setData(0, Qt.ItemDataRole.UserRole, sid)
            sample_item.setData(0, Qt.ItemDataRole.UserRole + 1, _HEADER)
            sample_item.setFlags(Qt.ItemFlag.ItemIsEnabled)

            all_item = QTreeWidgetItem([f"⬡  {ALL_EVENTS_LABEL}"])
            all_item.setData(0, Qt.ItemDataRole.UserRole, sid)
            all_item.setData(0, Qt.ItemDataRole.UserRole + 1, None)
            all_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            all_item.setCheckState(0, Qt.CheckState.Checked)
            sample_item.addChild(all_item)

            def _add_nodes(node, parent_item, _sid=sid):
                if not node.is_root:
                    icon = "⊘ " if node.negated else "◆ "
                    row = QTreeWidgetItem([f"{icon}{node.name}"])
                    row.setData(0, Qt.ItemDataRole.UserRole, _sid)
                    row.setData(0, Qt.ItemDataRole.UserRole + 1, node.node_id)
                    row.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                    row.setCheckState(0, Qt.CheckState.Unchecked)
                    parent_item.addChild(row)
                    next_parent = row
                else:
                    next_parent = parent_item
                for child in node.children:
                    # Unwired/under-wired logic nodes have no valid population
                    # yet — not selectable, same as the gating hierarchy view.
                    if getattr(child, "is_incomplete", False):
                        continue
                    _add_nodes(child, next_parent, _sid)

            _add_nodes(sample.gate_tree, sample_item)
            self.tree.addTopLevelItem(sample_item)
            sample_item.setExpanded(True)

    def _on_pop_item_changed_single(self, item: QTreeWidgetItem, _column: int) -> None:
        """Radio-button: checking a population unchecks all others in the same sample."""
        if item.checkState(0) != Qt.CheckState.Checked:
            self.selectionChanged.emit()
            return
        sid = item.data(0, Qt.ItemDataRole.UserRole)
        self.tree.blockSignals(True)
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            other = it.value()
            if other and other is not item:
                other_sid = other.data(0, Qt.ItemDataRole.UserRole)
                other_nid = other.data(0, Qt.ItemDataRole.UserRole + 1)
                if other_sid == sid and other_nid is not _HEADER:
                    other.setCheckState(0, Qt.CheckState.Unchecked)
            it += 1
        self.tree.blockSignals(False)
        self.selectionChanged.emit()

    def _get_checked_from_tree(self) -> list[tuple[str, str | None, str]]:
        result = []
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item and item.checkState(0) == Qt.CheckState.Checked:
                sid = item.data(0, Qt.ItemDataRole.UserRole)
                node_id = item.data(0, Qt.ItemDataRole.UserRole + 1)
                if node_id is not _HEADER:
                    label = item.text(0).strip().lstrip("⬡◆⊘ ").strip()
                    result.append((sid, node_id, label))
            it += 1
        return result

    # ── Theme ────────────────────────────────────────────────────────────────

    def _apply_theme_styles(self) -> None:
        Colors, _ = _get_theme_tokens()
        self.tree.setStyleSheet(
            f"QTreeWidget {{ background: {Colors.BG_DARKEST}; border: 1px solid {Colors.BORDER};"
            f" border-radius: 4px; color: {Colors.FG_PRIMARY}; }}"
            f"QTreeWidget::item {{ color: {Colors.FG_PRIMARY}; padding: 2px 4px; }}"
            f"QTreeWidget::item:hover {{ background: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY}; }}"
            f"QTreeWidget::item:selected {{ background: {Colors.BG_MEDIUM}; color: {Colors.FG_PRIMARY}; }}"
            + checkbox_qss()
        )
        self._search_box.setStyleSheet(
            f"QLineEdit {{ background: {Colors.BG_MEDIUM}; color: {Colors.FG_PRIMARY};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 4px; padding: 4px 8px; }}"
        )

        fg_color = QColor(Colors.FG_PRIMARY)

        def _recolor(item: QTreeWidgetItem) -> None:
            item.setForeground(0, fg_color)
            for c in range(item.childCount()):
                child = item.child(c)
                if child is not None:
                    _recolor(child)

        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            if top is not None:
                _recolor(top)
