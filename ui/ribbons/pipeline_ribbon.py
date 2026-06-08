"""Pipeline ribbon — tools for the visual node-based gating canvas."""

from biopro.ui.theme import Colors, Fonts
from biopro_sdk.plugin.components import BioHelpButton
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget, QPushButton

from analysis.state import FlowState


class PipelineRibbon(QWidget):
    """Ribbon tab containing tools for the Pipeline canvas."""

    # Emitted when the user selects a new sample to view in the pipeline
    sample_selected = pyqtSignal(str)

    # Emitted when the user requests a logic node
    logic_node_requested = pyqtSignal(str, str)  # sample_id, operator (AND/OR/NOT)

    def __init__(self, state: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(16)

        # ── Sample Selector ──
        lbl = QLabel("View Sample:")
        lbl.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;")

        self._sample_combo = QComboBox()
        self._sample_combo.setFixedWidth(200)
        self._sample_combo.currentIndexChanged.connect(self._on_combo_changed)

        layout.addWidget(lbl)
        layout.addWidget(self._sample_combo)

        # ── Pipeline Help ──
        pipeline_help = BioHelpButton()
        pipeline_help.setHelpText(
            "Welcome to the Pipeline Viewer!\n\n"
            "• Double-click any node's mini-plot to quickly open it in the main Workspace.\n"
            "• Drag and drop from the output port (right side) of a node to the input port (left side) of another to connect them.\n"
            "• Move nodes around freely to organize your gating strategy.", 
            "Pipeline Canvas Instructions"
        )
        layout.addWidget(pipeline_help)

        # ── Logic Nodes ──
        # Add a separator
        sep = QLabel("|")
        sep.setStyleSheet(f"color: {Colors.BORDER}; margin: 0 10px;")
        layout.addWidget(sep)

        logic_help = BioHelpButton()
        logic_help.setHelpText(
            "Logic gates allow you to combine different gated populations:\n\n"
            "• AND: Keeps only the events present in ALL connected parent populations.\n"
            "• OR: Keeps events present in ANY of the connected parent populations.\n"
            "• NOT: Keeps events from the primary parent, EXCLUDING events from subsequent parents.",
            "Logic Gates"
        )
        layout.addWidget(logic_help)

        logic_tooltips = {
            "AND": "Intersect populations (events must be in all parents)",
            "OR": "Union of populations (events can be in any parent)",
            "NOT": "Exclude populations (events in parent A but not in parent B)"
        }

        for op in ["AND", "OR", "NOT"]:
            btn = QPushButton(f"+ {op}")
            btn.setToolTip(logic_tooltips[op])
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {Colors.BG_LIGHT};
                    color: {Colors.FG_PRIMARY};
                    border: 1px solid {Colors.BORDER};
                    border-radius: 4px;
                    padding: 4px 12px;
                }}
                QPushButton:hover {{
                    background-color: {Colors.ACCENT_PRIMARY};
                }}
            """)
            # capture op in lambda
            btn.clicked.connect(lambda checked, o=op: self._request_logic_node(o))
            layout.addWidget(btn)

        layout.addStretch()

    def _request_logic_node(self, operator: str) -> None:
        idx = self._sample_combo.currentIndex()
        if idx >= 0:
            sample_id = self._sample_combo.itemData(idx)
            self.logic_node_requested.emit(sample_id, operator)

    def refresh_samples(self) -> None:
        self._sample_combo.blockSignals(True)
        self._sample_combo.clear()

        for sample_id, sample in self.state.data.experiment.samples.items():
            self._sample_combo.addItem(sample.display_name, sample_id)

        self._sample_combo.blockSignals(False)

        # Select current sample if possible
        if self.state.view.current_sample_id:
            idx = self._sample_combo.findData(self.state.view.current_sample_id)
            if idx >= 0:
                self._sample_combo.setCurrentIndex(idx)

        # Explicitly emit for the currently selected sample to ensure it renders
        self._on_combo_changed(self._sample_combo.currentIndex())

    def _on_combo_changed(self, index: int) -> None:
        if index >= 0:
            sample_id = self._sample_combo.itemData(index)
            self.sample_selected.emit(sample_id)
