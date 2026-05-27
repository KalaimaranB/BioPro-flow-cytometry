"""UMAP Ribbon — Toolbar for controlling UMAP dimensionality reduction.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal

from ...analysis.state import FlowState
from biopro.ui.theme import Colors, Fonts
from biopro_sdk.plugin.components import (
    BioComboBox,
    BioRunButton,
    BioCancelButton,
    BioCaptionLabel,
    BioStatusLabel,
)


class UmapRibbon(QWidget):
    """Ribbon tab containing control buttons and sample/gate pickers for UMAP."""
    
    # Emitted when the user clicks 'Run UMAP' — carries (sample_id, node_id | None)
    run_requested = pyqtSignal(str, object)  # sample_id, node_id (None = all events)
    
    # Emitted when the user picks a past run from history
    history_run_selected = pyqtSignal(dict)
    
    # Emitted when the user changes the selected gate
    gate_changed = pyqtSignal(str, object)
    
    # Emitted when the user clicks to delete the currently selected run
    delete_run_requested = pyqtSignal(dict)
    
    # Emitted when the sample selection changes
    sample_changed = pyqtSignal(str)
    
    # Emitted when the user clicks 'Cancel'
    cancel_requested = pyqtSignal()

    def __init__(self, state: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        # ── Sample Selector ──────────────────────────────────────────────
        lbl_sample = BioCaptionLabel("Sample:")
        
        self._sample_combo = BioComboBox()
        self._sample_combo.setFixedWidth(200)
        self._sample_combo.currentIndexChanged.connect(self._on_sample_changed)
        
        layout.addWidget(lbl_sample)
        layout.addWidget(self._sample_combo)

        # ── Gate / Population Selector ───────────────────────────────────
        sep1 = QLabel("|")
        sep1.setStyleSheet(f"color: {Colors.BORDER}; margin: 0 4px;")
        layout.addWidget(sep1)

        lbl_gate = BioCaptionLabel("Gate:")

        self._gate_combo = BioComboBox()
        self._gate_combo.setFixedWidth(220)
        # Pre-populate with placeholder
        self._gate_combo.addItem("⬡  All Events (no gate)", None)
        self._gate_combo.currentIndexChanged.connect(self._on_gate_changed)

        layout.addWidget(lbl_gate)
        layout.addWidget(self._gate_combo)

        # ── Separator ────────────────────────────────────────────────────
        sep2 = QLabel("|")
        sep2.setStyleSheet(f"color: {Colors.BORDER}; margin: 0 4px;")
        layout.addWidget(sep2)
        
        # ── Run History Selector ─────────────────────────────────────────
        lbl_history = BioCaptionLabel("History:")

        self._history_combo = BioComboBox()
        self._history_combo.setFixedWidth(180)
        self._history_combo.addItem("[ New Run ]", None)
        self._history_combo.currentIndexChanged.connect(self._on_history_changed)

        layout.addWidget(lbl_history)
        layout.addWidget(self._history_combo)
        
        # Delete Run Button
        from biopro_sdk.plugin.components import SecondaryButton
        self._delete_run_btn = SecondaryButton("🗑️")
        self._delete_run_btn.setToolTip("Delete this run")
        self._delete_run_btn.setFixedWidth(32)
        self._delete_run_btn.setEnabled(False) # Only enabled when an actual run is selected
        self._delete_run_btn.clicked.connect(self._on_delete_run_clicked)
        layout.addWidget(self._delete_run_btn)

        # ── Separator ────────────────────────────────────────────────────
        sep_hist = QLabel("|")
        sep_hist.setStyleSheet(f"color: {Colors.BORDER}; margin: 0 4px;")
        layout.addWidget(sep_hist)
        
        # ── Run UMAP Button ──────────────────────────────────────────────
        self._run_btn = BioRunButton("🧬 Run UMAP")
        self._run_btn.clicked.connect(self._on_run_clicked)
        layout.addWidget(self._run_btn)
        
        # ── Cancel Button ────────────────────────────────────────────────
        self._cancel_btn = BioCancelButton("⏹ Cancel")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(self._cancel_btn)
        
        # ── Separator ────────────────────────────────────────────────────
        sep3 = QLabel("|")
        sep3.setStyleSheet(f"color: {Colors.BORDER}; margin: 0 4px;")
        layout.addWidget(sep3)
        
        # ── Status Label ─────────────────────────────────────────────────
        self._status_lbl = BioStatusLabel("Ready")
        layout.addWidget(self._status_lbl)
        
        layout.addStretch()
        
    # ── Public API ────────────────────────────────────────────────────────

    def refresh_samples(self) -> None:
        """Populate the sample combobox with active experiment samples."""
        self._sample_combo.blockSignals(True)
        self._sample_combo.clear()
        
        for sample_id, sample in self.state.experiment.samples.items():
            self._sample_combo.addItem(sample.display_name, sample_id)
            
        self._sample_combo.blockSignals(False)
        
        # Select current sample and refresh gate list
        if self.state.current_sample_id:
            idx = self._sample_combo.findData(self.state.current_sample_id)
            if idx >= 0:
                self._sample_combo.setCurrentIndex(idx)
                
        self._refresh_gates()
        self.refresh_history()
        
        # Initial emit if we have a sample
        current_id = self._sample_combo.currentData()
        if current_id:
            self.sample_changed.emit(current_id)
            gate_id = self._gate_combo.currentData()
            self.gate_changed.emit(current_id, gate_id)

    def set_status(self, msg: str) -> None:
        """Update the status label in the ribbon."""
        self._status_lbl.setText(msg)
        
    def set_running(self, running: bool) -> None:
        """Toggle button enabled states during running tasks."""
        self._run_btn.setEnabled(not running)
        self._cancel_btn.setEnabled(running)
        self._sample_combo.setEnabled(not running)
        self._gate_combo.setEnabled(not running)
        self._history_combo.setEnabled(not running)
        
        if running:
            self._delete_run_btn.setEnabled(False)
        else:
            self._update_delete_button_state()

    def select_last_run(self) -> None:
        """Select the most recently added run in the history combo."""
        if self._history_combo.count() > 1:
            self._history_combo.setCurrentIndex(self._history_combo.count() - 1)

    # ── Private ───────────────────────────────────────────────────────────

    def _on_sample_changed(self, _index: int) -> None:
        """When the user picks a different sample, repopulate the gate list."""
        self._refresh_gates()
        self.refresh_history()
        sample_id = self._sample_combo.currentData()
        if sample_id:
            self.sample_changed.emit(sample_id)
            gate_id = self._gate_combo.currentData()
            self.gate_changed.emit(sample_id, gate_id)

    def _on_gate_changed(self, _index: int) -> None:
        self.refresh_history()
        sample_id = self._sample_combo.currentData()
        if sample_id:
            gate_id = self._gate_combo.currentData()
            self.gate_changed.emit(sample_id, gate_id)

    def refresh_history(self) -> None:
        """Populate the history combo with past runs for current sample and gate."""
        self._history_combo.blockSignals(True)
        self._history_combo.clear()
        self._history_combo.addItem("[ New Run ]", None)
        
        sample_id = self._sample_combo.currentData()
        if not sample_id:
            self._history_combo.blockSignals(False)
            return
            
        node_id = self._gate_combo.currentData()
        key = f"{sample_id}::{node_id or 'root'}"
        runs = self.state.data.umap_results.get(key, [])
        
        for i, run in enumerate(runs, 1):
            n = run.get('n_neighbors', 15)
            md = run.get('min_dist', 0.1)
            label = f"Run {i} (n={n}, md={md})"
            self._history_combo.addItem(label, run)
            
        self._history_combo.blockSignals(False)
        self._update_delete_button_state()
        
    def _update_delete_button_state(self) -> None:
        has_run = self._history_combo.itemData(self._history_combo.currentIndex()) is not None
        self._delete_run_btn.setEnabled(has_run)
        
    def _on_history_changed(self, index: int) -> None:
        self._update_delete_button_state()
        run_data = self._history_combo.itemData(index)
        self.history_run_selected.emit(run_data) # emit None if New Run selected

    def _on_delete_run_clicked(self) -> None:
        run_data = self._history_combo.currentData()
        if run_data is not None:
            self.delete_run_requested.emit(run_data)

    def _refresh_gates(self) -> None:
        """Populate the gate combo with all named nodes in the selected sample's gate tree."""
        self._gate_combo.blockSignals(True)
        self._gate_combo.clear()
        self._gate_combo.addItem("⬡  All Events (no gate)", None)

        sample_id = self._sample_combo.currentData()
        if not sample_id:
            self._gate_combo.blockSignals(False)
            return

        sample = self.state.experiment.samples.get(sample_id)
        if not sample or sample.gate_tree is None:
            self._gate_combo.blockSignals(False)
            return

        # Walk the gate tree recursively and add every non-root node
        def _add_nodes(node, depth: int = 0) -> None:
            if not node.is_root:
                indent = "  " * depth
                icon = "⊘ " if node.negated else "◆ "
                label = f"{indent}{icon}{node.name}"
                self._gate_combo.addItem(label, node.node_id)
            for child in node.children:
                _add_nodes(child, depth + (0 if node.is_root else 1))

        _add_nodes(sample.gate_tree)
        self._gate_combo.blockSignals(False)
                
    def _on_run_clicked(self) -> None:
        idx = self._sample_combo.currentIndex()
        if idx >= 0:
            sample_id = self._sample_combo.itemData(idx)
            node_id = self._gate_combo.currentData()  # None = all events
            self.run_requested.emit(sample_id, node_id)
