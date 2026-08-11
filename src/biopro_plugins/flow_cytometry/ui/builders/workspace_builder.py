from __future__ import annotations

from typing import TYPE_CHECKING

from biopro_sdk.plugin.components import BioSplitter, SecondaryButton
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

try:
    from biopro.ui.theme import Colors
except ImportError:
    from biopro_sdk.plugin.theme_fallback import Colors
from biopro_plugins.flow_cytometry.ui.graph.graph_manager import GraphManager
from biopro_plugins.flow_cytometry.ui.ribbons.comparisons_ribbon import (
    ComparisonsRibbon,
)
from biopro_plugins.flow_cytometry.ui.ribbons.compensation_ribbon import (
    CompensationRibbon,
)
from biopro_plugins.flow_cytometry.ui.ribbons.gating_ribbon import GatingRibbon
from biopro_plugins.flow_cytometry.ui.ribbons.pipeline_ribbon import PipelineRibbon
from biopro_plugins.flow_cytometry.ui.ribbons.spectral_ribbon import SpectralRibbon
from biopro_plugins.flow_cytometry.ui.ribbons.statistics_ribbon import StatisticsRibbon
from biopro_plugins.flow_cytometry.ui.ribbons.workspace_ribbon import WorkspaceRibbon
from biopro_plugins.flow_cytometry.ui.widgets.comparisons_viewer import (
    ComparisonsViewer,
)
from biopro_plugins.flow_cytometry.ui.widgets.gate_hierarchy import GateHierarchy
from biopro_plugins.flow_cytometry.ui.widgets.groups_panel import GroupsPanel
from biopro_plugins.flow_cytometry.ui.widgets.node_canvas.canvas_view import NodeCanvas
from biopro_plugins.flow_cytometry.ui.widgets.population_analysis_viewer import (
    PopulationAnalysisViewer,
)
from biopro_plugins.flow_cytometry.ui.widgets.properties_panel import PropertiesPanel
from biopro_plugins.flow_cytometry.ui.widgets.sample_list import SampleList
from biopro_plugins.flow_cytometry.ui.widgets.spectral_viewer import SpectralViewer
from biopro_plugins.flow_cytometry.ui.widgets.statistics_explorer import (
    StatisticsExplorer,
)

if TYPE_CHECKING:
    from ...ui.main_panel import FlowCytometryPanel


class WorkspaceBuilder:
    """Builds the primary workspace layout for the flow cytometry plugin.

    The build is split into two phases to support the BioPro Ready Gate protocol:

    Phase 1 – ``build_skeleton``  (called from ``__init__``)
        Creates the structural scaffold: tab bar, ribbon stack, sidebar widgets,
        and an empty ``_center_stack`` placeholder.  Fast (<50 ms).

    Phase 2 – individual ``build_step_*`` methods  (chained via QTimer in ``begin_async_init``)
        Each step builds exactly one heavy analysis view, then yields to the event loop so
        the GalacticLoader animation remains smooth.  After all steps, ``finalize_center_stack``
        and ``connect_tab_bar`` complete the wiring.

    The ``build_heavy`` / ``build`` convenience wrappers run all steps synchronously for
    testing and backward compatibility.
    """

    # ── Phase 1 ───────────────────────────────────────────────────────

    @staticmethod
    def build_skeleton(panel: FlowCytometryPanel) -> None:  # noqa: PLR0915
        """Build the lightweight structural scaffold (Phase 1).

        Creates the tab bar, ribbons, sidebar, and a placeholder center stack.
        Heavy analysis views are deferred to the ``build_step_*`` methods.
        """
        root = QVBoxLayout(panel)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar Tab Bar ───────────────────────────────────────────
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 16, 0)

        panel._tab_bar = QTabBar()
        panel._tab_bar.setObjectName("MainTabBar")
        panel._tab_bar.setExpanding(False)
        panel._tab_bar.setDocumentMode(True)
        tab_names = [
            "Workspace",
            "Compensation",
            "Gating",
            "Pipeline",
            "Statistics",
            "Spectral",
            "Population Analysis",
            "Comparisons",
        ]
        for name in tab_names:
            panel._tab_bar.addTab(name)

        top_bar_layout.addWidget(panel._tab_bar)
        top_bar_layout.addStretch()

        panel._save_state_label = QLabel("")
        panel._save_state_label.setContentsMargins(0, 0, 10, 0)
        top_bar_layout.addWidget(panel._save_state_label)

        panel._btn_update = SecondaryButton("🔄 Update Workflow")
        panel._btn_update.setObjectName("UpdateWorkflowButton")
        panel._btn_update.setToolTip("Overwrite the currently loaded workflow")
        panel._btn_update.clicked.connect(panel._handle_update)
        top_bar_layout.addWidget(panel._btn_update)

        panel._btn_save = SecondaryButton("💾 Save New Workflow")
        panel._btn_save.setObjectName("SaveNewWorkflowButton")
        panel._btn_save.setToolTip(
            "Save all gates, axes, and loaded files as a complete new session"
        )
        panel._btn_save.clicked.connect(panel._handle_save)
        top_bar_layout.addWidget(panel._btn_save)

        panel.set_dirty(False)
        root.addLayout(top_bar_layout)

        # ── Ribbon Stack ──────────────────────────────────────────────
        panel._ribbon_stack = QStackedWidget()
        panel._ribbon_stack.setFixedHeight(64)
        panel._ribbon_stack.setStyleSheet(
            f"background: {Colors.BG_DARK}; border-bottom: 1px solid {Colors.BORDER};"
        )

        panel._workspace_ribbon = WorkspaceRibbon(
            panel.state, panel._factory.get("data_loader_service"), parent=panel
        )
        panel._compensation_ribbon = CompensationRibbon(panel.state)
        panel._gating_ribbon = GatingRibbon(panel.state)
        panel._pipeline_ribbon = PipelineRibbon(panel.state)
        panel.state.view._pipeline_ribbon = panel._pipeline_ribbon
        panel._stats_ribbon = StatisticsRibbon(panel.state)
        panel._spectral_ribbon = SpectralRibbon(panel.state)
        panel._comparisons_ribbon = ComparisonsRibbon()

        panel._ribbon_stack.addWidget(panel._workspace_ribbon)
        panel._ribbon_stack.addWidget(panel._compensation_ribbon)
        panel._ribbon_stack.addWidget(panel._gating_ribbon)
        panel._ribbon_stack.addWidget(panel._pipeline_ribbon)
        panel._ribbon_stack.addWidget(panel._stats_ribbon)
        panel._ribbon_stack.addWidget(panel._spectral_ribbon)
        panel._ribbon_stack.addWidget(panel._comparisons_ribbon)

        # NOTE: _tab_bar.currentChanged is wired in connect_tab_bar(), called at the
        # end of Phase 2 once all center-stack views are guaranteed to exist.
        root.addWidget(panel._ribbon_stack)

        # ── Main Content Splitter ─────────────────────────────────────
        panel._main_splitter = BioSplitter(Qt.Orientation.Horizontal)
        panel._main_splitter.setObjectName("mainSplitter")
        panel._main_splitter.setHandleWidth(1)
        panel._main_splitter.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Left sidebar: groups + sample tree (lightweight, no data until files loaded)
        panel._left_sidebar = QWidget()
        panel._left_sidebar.setObjectName("leftSidebar")
        left_layout = QVBoxLayout(panel._left_sidebar)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        panel._groups_panel = GroupsPanel(panel.state)

        panel._left_splitter = BioSplitter(Qt.Orientation.Vertical)
        panel._left_splitter.setObjectName("leftSplitter")
        panel._left_splitter.setHandleWidth(1)

        panel._sample_list = SampleList(panel.state)
        panel._gate_hierarchy = GateHierarchy(panel.state)

        panel._left_splitter.addWidget(panel._sample_list)
        panel._left_splitter.addWidget(panel._gate_hierarchy)
        panel._left_splitter.setSizes([300, 300])

        left_layout.addWidget(panel._groups_panel)

        panel._left_sep = QWidget()
        panel._left_sep.setFixedHeight(1)
        left_layout.addWidget(panel._left_sep)

        left_layout.addWidget(panel._left_splitter, stretch=1)

        # Center: QStackedWidget with a placeholder; real views added in Phase 2.
        panel._center_stack = QStackedWidget()
        panel._center_placeholder = QWidget()
        panel._center_placeholder.setObjectName("_CenterLoadingPlaceholder")
        panel._center_stack.addWidget(panel._center_placeholder)

        # Right: properties panel (lightweight, no data until gate selected)
        panel._properties_panel = PropertiesPanel(
            panel.state,
            panel._factory.get("axis_manager"),
            panel._factory.get("population_service"),
            panel._gate_coordinator,
        )

        panel._main_splitter.addWidget(panel._left_sidebar)
        panel._main_splitter.addWidget(panel._center_stack)
        panel._main_splitter.addWidget(panel._properties_panel)
        panel._main_splitter.setSizes([300, 800, 300])

        root.addWidget(panel._main_splitter, stretch=1)

    # ── Phase 2 — individual steps (one heavy view each) ──────────────
    #
    # Each ``build_step_*`` method builds exactly one widget so that
    # ``begin_async_init`` can chain them via ``QTimer.singleShot(0)``,
    # yielding to the Qt event loop between each construction.  The QML
    # GalacticLoader animation therefore stays smooth throughout Phase 2.
    #
    # Index contract for ``_center_stack``:
    #   0 → GraphManager           (Workspace / Gating / Compensation tabs)
    #   1 → NodeCanvas             (Pipeline tab)
    #   2 → SpectralViewer         (Spectral tab)
    #   3 → PopulationAnalysisViewer (Population Analysis tab)
    #   4 → StatisticsExplorer     (Statistics tab)
    #   5 → ComparisonsViewer      (Comparisons tab)

    @staticmethod
    def build_step_graph_manager(panel: FlowCytometryPanel) -> None:
        """Phase 2 step 1/6 — build the main graph canvas."""
        panel._graph_manager = GraphManager(
            panel.state,
            panel._factory.get("axis_manager"),
            panel._factory.get("population_service"),
            controller=panel._gate_controller,
        )
        panel._graph_manager.setObjectName("GraphManager")
        panel.state.view._graph_manager = panel._graph_manager

    @staticmethod
    def build_step_node_canvas(panel: FlowCytometryPanel) -> None:
        """Phase 2 step 2/6 — build the pipeline node canvas."""
        panel._node_canvas = NodeCanvas(panel.state)

    @staticmethod
    def build_step_spectral(panel: FlowCytometryPanel) -> None:
        """Phase 2 step 3/6 — build the spectral viewer."""
        panel._spectral_viewer = SpectralViewer(panel.state, panel._fluor_service, panel)
        panel.state.view._spectral_viewer = panel._spectral_viewer

    @staticmethod
    def build_step_population(panel: FlowCytometryPanel) -> None:
        """Phase 2 step 4/6 — build the population analysis viewer."""
        panel._population_analysis_viewer = PopulationAnalysisViewer(
            panel.state,
            panel._umap_service,
            gate_coordinator=panel._gate_coordinator,
            parent=panel,
        )

    @staticmethod
    def build_step_statistics(panel: FlowCytometryPanel) -> None:
        """Phase 2 step 5/6 — build the statistics explorer."""
        panel._statistics_explorer = StatisticsExplorer(
            panel.state, gate_coordinator=panel._gate_coordinator, parent=panel
        )
        panel.state.view._statistics_explorer = panel._statistics_explorer

    @staticmethod
    def build_step_comparisons(panel: FlowCytometryPanel) -> None:
        """Phase 2 step 6/6 — build the comparisons viewer."""
        panel._comparisons_viewer = ComparisonsViewer(
            panel.state, gate_coordinator=panel._gate_coordinator, parent=panel
        )
        panel.state.view._comparisons_viewer = panel._comparisons_viewer

    @staticmethod
    def finalize_center_stack(panel: FlowCytometryPanel) -> None:
        """Replace the skeleton placeholder with all 6 real views at correct indices."""
        # Remove placeholder (only widget currently in the stack at index 0)
        placeholder = panel._center_stack.widget(0)
        panel._center_stack.removeWidget(placeholder)
        placeholder.deleteLater()
        panel._center_placeholder = None

        panel._center_stack.addWidget(panel._graph_manager)  # 0
        panel._center_stack.addWidget(panel._node_canvas)  # 1
        panel._center_stack.addWidget(panel._spectral_viewer)  # 2
        panel._center_stack.addWidget(panel._population_analysis_viewer)  # 3
        panel._center_stack.addWidget(panel._statistics_explorer)  # 4
        panel._center_stack.addWidget(panel._comparisons_viewer)  # 5

        panel._center_stack.setCurrentIndex(0)

    @staticmethod
    def connect_tab_bar(panel: FlowCytometryPanel) -> None:
        """Connect the tab bar and mark the workspace as ready."""
        panel._tab_bar.currentChanged.connect(panel._on_tab_changed)
        panel.status_message.emit("Ready")

    # ── Convenience wrappers (sync, for tests / legacy callers) ───────

    @staticmethod
    def build_heavy(panel: FlowCytometryPanel) -> None:
        """Run all Phase 2 steps synchronously (backward-compat / test helper).

        In production, prefer the chained ``begin_async_init`` path which builds
        one widget per event-loop tick, keeping the GalacticLoader animated.
        """
        WorkspaceBuilder.build_step_graph_manager(panel)
        WorkspaceBuilder.build_step_node_canvas(panel)
        WorkspaceBuilder.build_step_spectral(panel)
        WorkspaceBuilder.build_step_population(panel)
        WorkspaceBuilder.build_step_statistics(panel)
        WorkspaceBuilder.build_step_comparisons(panel)
        WorkspaceBuilder.finalize_center_stack(panel)
        WorkspaceBuilder.connect_tab_bar(panel)

    @staticmethod
    def build(panel: FlowCytometryPanel) -> None:
        """Deprecated: run both phases synchronously.

        Prefer calling ``build_skeleton`` then ``build_heavy`` separately via
        the two-phase async-init protocol.
        """
        WorkspaceBuilder.build_skeleton(panel)
        WorkspaceBuilder.build_heavy(panel)
