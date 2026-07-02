"""Properties panel — context-sensitive detail view for selected items.

Shows different content depending on what's selected:
- **Sample**: file metadata, keywords, channel list, marker assignments
- **Gate**: gate type, parameters, event count, %parent, %total,
  plus computed statistics (Mean, MFI, CV)
- **No selection**: general workspace info

This is the right-side panel of the workspace.  It refreshes in
real-time when gate statistics are updated by the ``GateController``
or ``GatePropagator``.
"""

from __future__ import annotations

from typing import Any

from biopro.ui.theme import Colors, Fonts
from biopro_sdk.plugin import CentralEventBus, get_logger
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from analysis import events
from analysis.experiment import Sample
from analysis.gate_coordinator import GateCoordinator
from analysis.state import FlowState

from .group_preview import GroupPreviewPanel

logger = get_logger(__name__, "flow_cytometry")


class PropertiesPanel(QWidget):
    """Right-sidebar panel showing properties of the selected item.

    Dynamically updates when the user clicks on a sample or gate
    in the sample tree, and refreshes live when gate statistics
    are recomputed.
    """
    roleChanged = pyqtSignal()

    def __init__(
        self, state: FlowState, axis_manager: Any, population_service: Any, coordinator: GateCoordinator, parent=None
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._axis_manager = axis_manager
        self._population_service = population_service
        self._coordinator = coordinator
        self._current_sample_id: str | None = None
        self._current_node_id: str | None = None
        self.setObjectName("PropertiesPanel")
        self._setup_ui()
        self._setup_events()

    def _setup_events(self) -> None:
        CentralEventBus.subscribe(events.AXIS_PARAMS_CHANGED, lambda _: self.refresh())
        CentralEventBus.subscribe(events.STATS_COMPUTED, self._on_stats_computed)

    def _on_stats_computed(self, data: dict) -> None:
        self.refresh_gate_stats(data.get("sample_id"), data.get("node_id"))

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self._header = QLabel("Properties")
        self._header.setFixedHeight(32)
        self._header.setStyleSheet(
            f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;"
            f" font-weight: 700; text-transform: uppercase;"
            f" letter-spacing: 1px; background: {Colors.BG_DARK};"
            f" padding: 6px 12px;"
            f" border-bottom: 1px solid {Colors.BORDER};"
        )
        layout.addWidget(self._header)

        # Splitter to allow user to resize the two panels
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setHandleWidth(2)
        self._splitter.setStyleSheet(f"QSplitter::handle {{ background: {Colors.BORDER}; }}")

        # Scrollable content (Top)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {Colors.BG_DARKEST};")

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setSpacing(8)
        self._content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._content)
        self._splitter.addWidget(scroll)

        # Group Preview section (Bottom)
        self._group_preview = GroupPreviewPanel(self._state, None, self._axis_manager, self._population_service)
        self._splitter.addWidget(self._group_preview)

        # Set initial sizes (1/3 properties, 2/3 preview as requested)
        self._splitter.setSizes([300, 600])

        layout.addWidget(self._splitter)

        # Initial state
        self._show_empty()

    def show_sample_properties(self, sample_id: str, gate_id: str | None) -> None:
        """Update the panel to show properties of the selected item.

        Args:
            sample_id: The selected sample's ID.
            gate_id:   The selected gate's ID (None if sample root).
        """
        self._current_sample_id = sample_id
        self._current_node_id = gate_id

        # Update preview context
        self._group_preview.update_context(sample_id, gate_id)

        sample = self._state.data.experiment.samples.get(sample_id)
        if sample is None:
            self._show_empty()
            return

        if gate_id:
            self._show_gate_properties(sample, gate_id)
        else:
            self._show_sample_details(sample)

    def refresh(self) -> None:
        """Refresh the panel (e.g., after state restore)."""
        if self._current_sample_id and self._current_node_id:
            self.show_sample_properties(self._current_sample_id, self._current_node_id)
        elif self._current_sample_id:
            self.show_sample_properties(self._current_sample_id, None)
        else:
            self._show_empty()

    def refresh_gate_stats(self, sample_id: str, node_id: str) -> None:
        """Live-refresh if the currently displayed gate was updated.

        Called by the ``GateController`` when stats change.

        Args:
            sample_id: The sample whose gate was updated.
            node_id:   The gate that was updated.
        """
        if self._current_sample_id == sample_id and self._current_node_id == node_id:
            self.show_sample_properties(sample_id, node_id)

    # ── Private display methods ───────────────────────────────────────

    def _clear_content(self) -> None:
        """Remove all widgets from the content area."""
        # Safety check: ensure layout hasn't been deleted during widget teardown
        if not hasattr(self, "_content_layout") or self._content_layout is None:
            return

        while self._content_layout.count():
            child = self._content_layout.takeAt(0)
            if child and child.widget():
                child.widget().deleteLater()

    def _show_empty(self) -> None:
        """Show empty/default state."""
        self._clear_content()
        self._header.setText("Properties")
        self._current_sample_id = None
        self._current_node_id = None

        lbl = QLabel("Select a sample or gate\nfrom the tree to view\nits properties.")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color: {Colors.FG_DISABLED}; font-size: {Fonts.SIZE_SMALL}px;" f" background: transparent; padding: 24px;"
        )
        self._content_layout.addWidget(lbl)

    def _show_sample_details(self, sample: Sample) -> None:
        """Display sample metadata and channel info."""
        self._clear_content()
        self._header.setText(f"📄 {sample.display_name}")

        form = QFormLayout()
        form.setSpacing(10)
        form.setContentsMargins(0, 0, 0, 0)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        label_style = f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;" f" background: transparent;"
        value_style = f"color: {Colors.FG_PRIMARY}; font-size: {Fonts.SIZE_SMALL}px;" f" background: transparent;"

        from biopro_sdk.plugin.components import BioHelpButton
        from PyQt6.QtWidgets import QHBoxLayout
        def _create_label(label_text: str, help_text: str = None) -> QWidget:
            w = QWidget()
            lay = QHBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(4)
            lbl = QLabel(label_text)
            lbl.setStyleSheet(label_style)
            lay.addWidget(lbl)
            
            if help_text:
                help_btn = BioHelpButton()
                help_btn.setHelpText(help_text, title=label_text.replace(":", ""))
                lay.addWidget(help_btn)
                
            lay.addStretch()
            return w

        def _add_row(label_text: str, value_text: str, help_text: str = None) -> None:
            val = QLabel(value_text)
            val.setStyleSheet(value_style)
            val.setWordWrap(True)
            val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            form.addRow(_create_label(label_text, help_text), val)

        from PyQt6.QtWidgets import QComboBox

        from analysis.experiment import SampleRole

        role_combo = QComboBox()
        role_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        role_combo.setMinimumWidth(180)
        role_combo.setStyleSheet(f"background: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY}; border: 1px solid {Colors.BORDER}; padding: 4px;")
        
        for role in SampleRole:
            role_combo.addItem(role.value.replace("_", " ").title(), role)

        # Set current role
        for i in range(role_combo.count()):
            if role_combo.itemData(i) == sample.role:
                role_combo.setCurrentIndex(i)
                break
                
        def _on_role_changed(idx: int):
            new_role = role_combo.itemData(idx)
            sample.role = new_role
            CentralEventBus.publish(events.SAMPLE_UPDATED, {"sample_id": sample.sample_id, "stats": None, "tree": None})
            self.roleChanged.emit()

        role_combo.currentIndexChanged.connect(_on_role_changed)
        
        role_help_text = (
            "<b>Unstained</b><br>"
            "<i>What:</i> Cells with no fluorescent dyes.<br>"
            "<i>BioPro:</i> Used as the universal negative baseline for Compensation and Autofluorescence Extraction.<br><br>"
            
            "<b>Single Stain</b><br>"
            "<i>What:</i> Cells stained with exactly ONE color.<br>"
            "<i>BioPro:</i> Required by the Compensation Ribbon to mathematically calculate spectral spillover.<br><br>"
            
            "<b>FMO Control</b><br>"
            "<i>What:</i> Cells stained with all colors EXCEPT one.<br>"
            "<i>BioPro:</i> Used as a control to objectively set manual gate boundaries between positive and negative populations.<br><br>"
            
            "<b>Isotype Control</b><br>"
            "<i>What:</i> Stained with non-specific antibodies.<br>"
            "<i>BioPro:</i> Used to subtract background noise when calculating Statistics (e.g. MFI).<br><br>"
            
            "<b>Full Panel</b><br>"
            "<i>What:</i> Experimental samples with all colors.<br>"
            "<i>BioPro:</i> The primary targets for Dimensionality Reduction and Clustering engines.<br><br>"
            
            "<b>Other</b><br>"
            "<i>What:</i> Viability or biological controls.<br>"
            "<i>BioPro:</i> Ignored by automated engines."
        )

        form.addRow(_create_label("Role:", role_help_text), role_combo)
        
        _add_row("Events:", f"{sample.event_count:,}" if sample.has_data else "Not loaded")

        if sample.fcs_data:
            _add_row("File:", sample.fcs_data.file_path.name)

        if sample.markers:
            _add_row("Markers:", ", ".join(sample.markers))
        if sample.fmo_minus:
            _add_row("FMO Minus:", sample.fmo_minus)
        if sample.is_compensated:
            _add_row("Compensated:", "✅ Yes")

        # Gate count
        gate_count = self._count_gates(sample.gate_tree)
        if gate_count > 0:
            _add_row("Gates:", f"{gate_count} population{'s' if gate_count > 1 else ''}")

        # Channel list — show all, word wrap handles overflow
        if sample.fcs_data and sample.fcs_data.channels:
            _add_row("Channels:", ", ".join(sample.fcs_data.channels))

        form_widget = QWidget()
        form_widget.setLayout(form)
        self._content_layout.addWidget(form_widget)
        self._content_layout.addStretch()

    def _show_gate_properties(self, sample: Sample, node_id: str) -> None:
        """Display gate-specific properties with detailed statistics."""
        self._clear_content()

        node = sample.gate_tree.find_node_by_id(node_id)
        if node is None or node.gate is None:
            self._show_empty()
            return

        gate = node.gate
        self._header.setText(f"⊳ {node.name}")

        form = QFormLayout()
        form.setSpacing(6)
        form.setContentsMargins(0, 0, 0, 0)

        label_style = f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;" f" background: transparent;"
        value_style = f"color: {Colors.FG_PRIMARY}; font-size: {Fonts.SIZE_SMALL}px;" f" background: transparent;"
        stat_value_style = (
            f"color: {Colors.ACCENT_PRIMARY}; font-size: {Fonts.SIZE_SMALL}px;"
            f" background: transparent; font-weight: 600;"
        )

        def _add_row(label_text: str, value_text: str, highlight: bool = False) -> None:
            lbl = QLabel(label_text)
            lbl.setStyleSheet(label_style)
            val = QLabel(value_text)
            val.setStyleSheet(stat_value_style if highlight else value_style)
            val.setWordWrap(True)
            val.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            form.addRow(lbl, val)

        # Population Name
        name_edit = QLineEdit(node.name)
        name_edit.setStyleSheet(f"background: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; padding: 4px;")
        name_edit.editingFinished.connect(lambda: self._on_name_changed(name_edit.text()))
        form.addRow("Name:", name_edit)

        # Gate identity
        _add_row("Type:", type(gate).__name__)
        _add_row("X Param:", gate.x_param)
        if gate.y_param:
            _add_row("Y Param:", gate.y_param)
        _add_row("Adaptive:", "🧠 Yes" if gate.adaptive else "No")

        _add_row("Adaptive:", "🧠 Yes" if gate.adaptive else "No")

        # Population statistics — highlighted
        if node.statistics:
            count = node.statistics.get("count", 0)
            pct_parent = node.statistics.get("pct_parent", 0.0)
            pct_total = node.statistics.get("pct_total", 0.0)

            _add_row("Event Count:", f"{int(count):,}", highlight=True)
            _add_row("% Parent:", f"{pct_parent:.2f}%", highlight=True)
            _add_row("% Total:", f"{pct_total:.2f}%", highlight=True)

        # Child gate count
        child_count = len(node.children)
        if child_count > 0:
            _add_row("Sub-gates:", f"{child_count}")

        # Final Assemblage
        form_widget = QWidget()
        form_widget.setLayout(form)
        self._content_layout.addWidget(form_widget)

        self._content_layout.addStretch()

    def set_active_gate(self, node_id: str | None) -> None:
        """Update the panel to show properties for a specific population."""
        self.show_sample_properties(self._current_sample_id, node_id)

    def _on_name_changed(self, new_name: str) -> None:
        if self._current_sample_id and self._current_node_id:
            self._coordinator.rename_population(self._current_sample_id, self._current_node_id, new_name)

    def _count_gates(self, node) -> int:
        """Count total gates in a tree (excluding root)."""
        count = 0
        for child in node.children:
            if child.gate is not None:
                count += 1
            count += self._count_gates(child)
        return count
