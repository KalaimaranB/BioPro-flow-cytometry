from __future__ import annotations

from typing import TYPE_CHECKING

from biopro_sdk.plugin.components import BioSplitter, PrimaryButton, SecondaryButton
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QStackedWidget, QTabBar, QVBoxLayout, QWidget

try:
    from biopro.ui.theme import Colors, Fonts
except ImportError:
    class Colors:
        BG_DARKEST = "#0d1117"
        BG_DARK = "#161b22"
        BORDER = "#30363d"
        ACCENT_PRIMARY = "#00bcd4"
        FG_SECONDARY = "#8b949e"
    class Fonts:
        SIZE_SMALL = 11

from ui.graph.graph_manager import GraphManager
from ui.ribbons.compensation_ribbon import CompensationRibbon
from ui.ribbons.gating_ribbon import GatingRibbon
from ui.ribbons.pipeline_ribbon import PipelineRibbon
from ui.ribbons.spectral_ribbon import SpectralRibbon
from ui.ribbons.statistics_ribbon import StatisticsRibbon
from ui.ribbons.workspace_ribbon import WorkspaceRibbon
from ui.widgets.gate_hierarchy import GateHierarchy
from ui.widgets.groups_panel import GroupsPanel
from ui.widgets.node_canvas.canvas_view import NodeCanvas
from ui.widgets.properties_panel import PropertiesPanel
from ui.widgets.sample_list import SampleList
from ui.widgets.spectral_viewer import SpectralViewer
from ui.widgets.population_analysis_viewer import PopulationAnalysisViewer

if TYPE_CHECKING:
    from ui.main_panel import FlowCytometryPanel

class WorkspaceBuilder:
    """Builds the primary workspace layout for the flow cytometry plugin."""
    
    @staticmethod
    def build(panel: FlowCytometryPanel) -> None:
        root = QVBoxLayout(panel)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar Tab Bar ───────────────────────────────────────────
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 16, 0)

        panel._tab_bar = QTabBar()
        panel._tab_bar.setExpanding(False)
        panel._tab_bar.setDocumentMode(True)
        # Add tabs
        tab_names = ["Workspace", "Compensation", "Gating", "Pipeline", "Statistics", "Spectral", "Population Analysis"]
        for i, name in enumerate(tab_names):
            panel._tab_bar.addTab(name)

        top_bar_layout.addWidget(panel._tab_bar)
        top_bar_layout.addStretch()

        panel._save_state_label = QLabel("")
        panel._save_state_label.setContentsMargins(0, 0, 10, 0)
        top_bar_layout.addWidget(panel._save_state_label)

        panel._btn_update = SecondaryButton("🔄 Update Workflow")
        panel._btn_update.setToolTip("Overwrite the currently loaded workflow")
        panel._btn_update.clicked.connect(panel._handle_update)
        top_bar_layout.addWidget(panel._btn_update)

        panel._btn_save = PrimaryButton("💾 Save New Workflow")
        panel._btn_save.setToolTip("Save all gates, axes, and loaded files as a complete new session")
        panel._btn_save.clicked.connect(panel._handle_save)
        top_bar_layout.addWidget(panel._btn_save)

        panel.set_dirty(False)

        root.addLayout(top_bar_layout)

        # ── Ribbon Stack ──────────────────────────────────────────────
        panel._ribbon_stack = QStackedWidget()
        panel._ribbon_stack.setFixedHeight(64)
        panel._ribbon_stack.setStyleSheet(f"background: {Colors.BG_DARK}; border-bottom: 1px solid {Colors.BORDER};")

        panel._workspace_ribbon = WorkspaceRibbon(panel.state, parent=panel)
        panel._compensation_ribbon = CompensationRibbon(panel.state)
        panel._gating_ribbon = GatingRibbon(panel.state)
        panel._pipeline_ribbon = PipelineRibbon(panel.state)
        panel._stats_ribbon = StatisticsRibbon(panel.state)
        panel._spectral_ribbon = SpectralRibbon(panel.state)

        panel._ribbon_stack.addWidget(panel._workspace_ribbon)
        panel._ribbon_stack.addWidget(panel._compensation_ribbon)
        panel._ribbon_stack.addWidget(panel._gating_ribbon)
        panel._ribbon_stack.addWidget(panel._pipeline_ribbon)
        panel._ribbon_stack.addWidget(panel._stats_ribbon)
        panel._ribbon_stack.addWidget(panel._spectral_ribbon)

        panel._tab_bar.currentChanged.connect(panel._on_tab_changed)
        root.addWidget(panel._ribbon_stack)

        # ── Main Content Splitter ─────────────────────────────────────
        panel._main_splitter = BioSplitter(Qt.Orientation.Horizontal)
        panel._main_splitter.setObjectName("mainSplitter")
        panel._main_splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Left sidebar: groups + sample tree
        panel._left_sidebar = QWidget()
        panel._left_sidebar.setObjectName("leftSidebar")
        left_layout = QVBoxLayout(panel._left_sidebar)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        panel._groups_panel = GroupsPanel(panel.state)

        # Vertical Splitter for Samples & Gates
        panel._left_splitter = BioSplitter(Qt.Orientation.Vertical)
        panel._left_splitter.setObjectName("leftSplitter")

        panel._sample_list = SampleList(panel.state)
        panel._gate_hierarchy = GateHierarchy(panel.state)

        panel._left_splitter.addWidget(panel._sample_list)
        panel._left_splitter.addWidget(panel._gate_hierarchy)
        panel._left_splitter.setSizes([300, 300])

        left_layout.addWidget(panel._groups_panel)

        # Separator
        panel._left_sep = QWidget()
        panel._left_sep.setFixedHeight(1)
        left_layout.addWidget(panel._left_sep)

        left_layout.addWidget(panel._left_splitter, stretch=1)

        # Center: stack for graph canvas area OR node canvas area OR biology views
        panel._center_stack = QStackedWidget()
        panel._graph_manager = GraphManager(
            panel.state,
            panel._factory.get("axis_manager"),
            panel._factory.get("population_service"),
            controller=panel._gate_controller,
        )
        panel._node_canvas = NodeCanvas(panel.state)
        panel._spectral_viewer = SpectralViewer(panel.state, panel._fluor_service, panel)
        panel._population_analysis_viewer = PopulationAnalysisViewer(
            panel.state, panel._umap_service, gate_coordinator=panel._gate_coordinator, parent=panel
        )

        panel._center_stack.addWidget(panel._graph_manager)  # index 0
        panel._center_stack.addWidget(panel._node_canvas)  # index 1
        panel._center_stack.addWidget(panel._spectral_viewer)  # index 2
        panel._center_stack.addWidget(panel._population_analysis_viewer)  # index 3

        # Right: properties panel
        panel._properties_panel = PropertiesPanel(
            panel.state, 
            panel._factory.get("axis_manager"), 
            panel._factory.get("population_service"), 
            panel._gate_coordinator
        )

        panel._main_splitter.addWidget(panel._left_sidebar)
        panel._main_splitter.addWidget(panel._center_stack)
        panel._main_splitter.addWidget(panel._properties_panel)
        panel._main_splitter.setSizes([300, 800, 300])

        # Bottom: status bar + theme toggle
        panel._bottom_bar = QWidget()
        panel._bottom_bar.setFixedHeight(28)
        panel._bottom_bar.setStyleSheet(f"background: {Colors.BG_DARK}; border-top: 1px solid {Colors.BORDER};")
        bb_layout = QHBoxLayout(panel._bottom_bar)
        bb_layout.setContentsMargins(8, 0, 8, 0)
        
        panel._status_label = QLabel("Ready")
        panel._status_label.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;")
        bb_layout.addWidget(panel._status_label)
        
        root.addWidget(panel._main_splitter, stretch=1)
        root.addWidget(panel._bottom_bar)
