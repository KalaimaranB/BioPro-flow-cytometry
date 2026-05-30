from __future__ import annotations

from typing import TYPE_CHECKING

from biopro_sdk.plugin import CentralEventBus

from analysis import events

if TYPE_CHECKING:
    from ui.main_panel import FlowCytometryPanel

class MainPanelController:
    """Manages the signal routing and event bus subscriptions for the Flow Cytometry workspace."""
    
    @staticmethod
    def wire(panel: FlowCytometryPanel) -> None:
        """Connect internal widget signals and CentralEventBus subscriptions."""
        # ── Any structural change → BioPro history manager & Node Canvas ────────────
        def _on_structural_change(payload):
            if not getattr(panel, "_loading", False):
                panel.push_state()
            panel._refresh_node_canvas()

        CentralEventBus.subscribe(events.GATE_CREATED, _on_structural_change)
        CentralEventBus.subscribe(events.GATE_DELETED, _on_structural_change)
        CentralEventBus.subscribe(events.GATE_RENAMED, _on_structural_change)
        CentralEventBus.subscribe("flow.pipeline.connection_added", _on_structural_change)
        CentralEventBus.subscribe("flow.pipeline.connection_removed", _on_structural_change)

        # ── Workspace ribbon: samples loaded → refresh tree + groups ──
        panel._workspace_ribbon.samples_loaded.connect(panel._on_samples_loaded)

        # ── Pipeline Ribbon & Node Canvas ─────────────────────────────
        panel._pipeline_ribbon.sample_selected.connect(panel._node_canvas.set_sample)
        panel._pipeline_ribbon.logic_node_requested.connect(panel._gate_coordinator.add_logic_node)
        panel._node_canvas.node_double_clicked.connect(panel._on_gate_double_clicked)
        panel._node_canvas.node_removed.connect(
            lambda node_id: panel._gate_coordinator.remove_population(panel._node_canvas.current_sample_id, node_id)
            if panel._node_canvas.current_sample_id
            else None
        )
        panel._node_canvas.connection_requested.connect(panel._gate_coordinator.add_connection)
        panel._node_canvas.connection_removed.connect(panel._gate_coordinator.remove_connection)

        # ── Workspace ribbon: template loaded → refresh everything ────
        panel._workspace_ribbon.template_load_requested.connect(panel._refresh_all)

        # ── Compensation ribbon: matrix changed → refresh ─────────────
        panel._compensation_ribbon.compensation_changed.connect(panel._on_compensation_changed)

        # ── Gating ribbon → drawing tool selection ────────────────────
        panel._gating_ribbon.tool_selected.connect(panel._graph_manager.set_drawing_mode)
        panel._gating_ribbon.delete_gate_requested.connect(panel._on_delete_selected_gate)
        panel._gating_ribbon.copy_gates_requested.connect(panel._on_copy_gates_from_active)

        # ── Graph manager → gate controller ───────────────────────────
        panel._graph_manager.gate_drawn.connect(panel._on_gate_drawn)
        panel._graph_manager.gate_selection_changed.connect(panel._on_gate_selected_on_canvas)

        # ── Gate controller → UI updates ──────────────────────────────
        CentralEventBus.subscribe(events.GATE_CREATED, lambda p: panel._on_gate_added(p.get("sample_id"), p.get("node_id")))
        CentralEventBus.subscribe(events.GATE_DELETED, lambda p: panel._on_gate_removed(p.get("sample_id"), p.get("node_id")))
        CentralEventBus.subscribe(events.GATE_SELECTED, lambda p: panel._on_gate_selected_from_controller(p.get("sample_id"), p.get("node_id")))
        
        def _on_stats_updated(payload):
            sid = payload.get("sample_id")
            nid = payload.get("node_id")
            panel._on_gate_stats_updated(sid, nid)
            panel._refresh_node_canvas()
        CentralEventBus.subscribe("flow.gate.stats_updated", _on_stats_updated)

        def _on_all_stats(payload):
            sid = payload.get("sample_id")
            panel._on_all_stats_updated(sid)
            panel._refresh_node_canvas()
        CentralEventBus.subscribe("flow.gate.all_stats_updated", _on_all_stats)

        # ── Propagator → live UI updates ──────────────────────────────
        CentralEventBus.subscribe(events.SAMPLE_UPDATED, lambda p: panel._on_propagated_sample_updated(p.get("sample_id"), p.get("stats"), p.get("new_tree")))
        
        def _on_prop_complete(payload):
            panel._on_propagation_complete()
            panel._refresh_node_canvas()
        CentralEventBus.subscribe(events.PROPAGATION_COMPLETE, _on_prop_complete)

        # ── UMAP Ribbon & Viewer ──────────────────────────────────────
        panel._umap_ribbon.run_requested.connect(
            lambda sid, nid: panel._umap_viewer.start_analysis(sid, node_id=nid, ribbon=panel._umap_ribbon)
        )
        panel._umap_ribbon.cancel_requested.connect(panel._umap_service.cancel)
        panel._umap_ribbon.sample_changed.connect(panel._umap_viewer.on_sample_changed)
        panel._umap_ribbon.gate_changed.connect(panel._umap_viewer.on_gate_changed)
        panel._umap_ribbon.history_run_selected.connect(panel._umap_viewer.on_history_run_selected)
        panel._umap_ribbon.delete_run_requested.connect(
            lambda run: panel._umap_viewer.on_delete_run_requested(run, panel._umap_ribbon)
        )

        # ── Sample list → graph + properties ──────────────────────────
        panel._sample_list.sample_double_clicked.connect(panel._graph_manager.open_graph_with_context)
        panel._sample_list.selection_changed.connect(
            lambda sid: panel._properties_panel.show_sample_properties(sid, None)
        )
        panel._sample_list.selection_changed.connect(panel._on_sample_selection_changed)

        # ── Gate Hierarchy → graph + properties ───────────────────────
        panel._gate_hierarchy.gate_double_clicked.connect(panel._on_gate_double_clicked)
        panel._gate_hierarchy.selection_changed.connect(panel._on_gate_selection_changed)
        panel._gate_hierarchy.gate_rename_requested.connect(panel._gate_coordinator.rename_population)
        panel._gate_hierarchy.gate_delete_requested.connect(panel._gate_coordinator.remove_population)
        panel._gate_hierarchy.copy_gates_requested.connect(panel._on_copy_gates)
        panel._gate_hierarchy.propagation_mode_changed.connect(panel._on_propagation_mode_changed)

        # ── Groups panel selection → filter sample list ───────────────
        panel._groups_panel.group_selected.connect(panel._sample_list.filter_by_group)
