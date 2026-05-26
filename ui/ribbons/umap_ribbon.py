"""UMAP Ribbon — Toolbar for controlling UMAP dimensionality reduction.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal

from ...analysis.state import FlowState
from biopro.ui.theme import Colors, Fonts


_COMBO_STYLE = f"""
    QComboBox {{
        background-color: {Colors.BG_LIGHT};
        color: {Colors.FG_PRIMARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 4px;
        padding: 4px 8px;
    }}
    QComboBox::drop-down {{ border: none; }}
    QComboBox QAbstractItemView {{
        background-color: {Colors.BG_DARK};
        color: {Colors.FG_PRIMARY};
        selection-background-color: {Colors.ACCENT_PRIMARY};
        outline: 0px;
    }}
"""


class UmapRibbon(QWidget):
    """Ribbon tab containing control buttons and sample/gate pickers for UMAP."""
    
    # Emitted when the user clicks 'Run UMAP' — carries (sample_id, node_id | None)
    run_requested = pyqtSignal(str, object)  # sample_id, node_id (None = all events)
    
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
        lbl_sample = QLabel("Sample:")
        lbl_sample.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;")
        
        self._sample_combo = QComboBox()
        self._sample_combo.setFixedWidth(200)
        self._sample_combo.setStyleSheet(_COMBO_STYLE)
        self._sample_combo.currentIndexChanged.connect(self._on_sample_changed)
        
        layout.addWidget(lbl_sample)
        layout.addWidget(self._sample_combo)

        # ── Gate / Population Selector ───────────────────────────────────
        sep1 = QLabel("|")
        sep1.setStyleSheet(f"color: {Colors.BORDER}; margin: 0 4px;")
        layout.addWidget(sep1)

        lbl_gate = QLabel("Gate:")
        lbl_gate.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;")

        self._gate_combo = QComboBox()
        self._gate_combo.setFixedWidth(220)
        self._gate_combo.setStyleSheet(_COMBO_STYLE)
        # Pre-populate with placeholder
        self._gate_combo.addItem("⬡  All Events (no gate)", None)

        layout.addWidget(lbl_gate)
        layout.addWidget(self._gate_combo)

        # ── Separator ────────────────────────────────────────────────────
        sep2 = QLabel("|")
        sep2.setStyleSheet(f"color: {Colors.BORDER}; margin: 0 4px;")
        layout.addWidget(sep2)
        
        # ── Run UMAP Button ──────────────────────────────────────────────
        self._run_btn = QPushButton("🧬 Run UMAP")
        self._run_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.FG_PRIMARY};
                border: 1px solid {Colors.BORDER_FOCUS};
                border-radius: 4px;
                padding: 5px 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Colors.ACCENT_PRIMARY};
                border: 1px solid #ffffff;
            }}
            QPushButton:disabled {{
                background-color: {Colors.BG_LIGHT};
                color: {Colors.FG_DISABLED};
                border: 1px solid {Colors.BORDER};
            }}
        """)
        self._run_btn.clicked.connect(self._on_run_clicked)
        layout.addWidget(self._run_btn)
        
        # ── Cancel Button ────────────────────────────────────────────────
        self._cancel_btn = QPushButton("⏹ Cancel")
        self._cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG_LIGHT};
                color: {Colors.FG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 5px 14px;
            }}
            QPushButton:hover {{
                background-color: {Colors.BORDER_LIGHT};
            }}
            QPushButton:disabled {{
                color: {Colors.FG_DISABLED};
            }}
        """)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(self._cancel_btn)
        
        # ── Separator ────────────────────────────────────────────────────
        sep3 = QLabel("|")
        sep3.setStyleSheet(f"color: {Colors.BORDER}; margin: 0 4px;")
        layout.addWidget(sep3)
        
        # ── Status Label ─────────────────────────────────────────────────
        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(
            f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px; font-style: italic;"
        )
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

    def set_status(self, msg: str) -> None:
        """Update the status label in the ribbon."""
        self._status_lbl.setText(msg)
        
    def set_running(self, running: bool) -> None:
        """Toggle button enabled states during running tasks."""
        self._run_btn.setEnabled(not running)
        self._cancel_btn.setEnabled(running)
        self._sample_combo.setEnabled(not running)
        self._gate_combo.setEnabled(not running)

    # ── Private ───────────────────────────────────────────────────────────

    def _on_sample_changed(self, _index: int) -> None:
        """When the user picks a different sample, repopulate the gate list."""
        self._refresh_gates()

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
