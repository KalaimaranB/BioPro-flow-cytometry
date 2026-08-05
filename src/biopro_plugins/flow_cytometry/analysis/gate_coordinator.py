"""Gate Coordinator — facade for gating operations.

Orchestrates the GateMutationService (analysis logic) and GatePropagator
(background synchronization) to provide a unified API for the UI.
"""

from biopro_sdk.plugin import CentralEventBus, get_logger

from . import events
from .gate_propagator import GatePropagator
from .gating import Gate, GateNode
from .services.gate_mutation_service import GateMutationService
from .services.gate_selection_service import GateSelectionService
from .state import FlowState

logger = get_logger(__name__, "flow_cytometry")


class GateCoordinator:
    """Facade for all gating operations in the flow module."""

    def __init__(self, state: FlowState, axis_manager, population_service, task_scheduler=None):
        self._state = state
        self._axis_manager = axis_manager
        self._population_service = population_service
        self._scheduler = task_scheduler

        # Sub-services
        self._propagator = GatePropagator(state, task_scheduler, _parent=self)  # type: ignore
        self._selection_service = GateSelectionService(state, self)

        # Instantiate mutation service once
        self._mutation_service = GateMutationService(
            state, self, self._selection_service, axis_manager, population_service
        )

    @property
    def propagator(self):
        return self._propagator

    def set_propagation_enabled(self, enabled: bool) -> None:
        """Enable or disable auto-propagation across samples."""
        self._propagation_enabled = enabled
        logger.info("Propagation %s", "enabled" if enabled else "disabled")

    def request_propagation(self, gate_id: str, source_sample_id: str) -> None:
        """Route propagation request, respecting the enabled flag."""
        if getattr(self, "_propagation_enabled", True):
            self._propagator.request_propagation(gate_id, source_sample_id)

    def propagate_to_all_groups(self, sample_id: str, node_id: str) -> None:
        """Route explicit cross-group propagation request."""
        self._propagator.request_cross_group_propagation(node_id, sample_id)

    # ── Facade API (Mapping to Mutation Service) ────────────────────────────

    def add_gate(
        self,
        gate: Gate,
        sample_id: str,
        name: str | None = None,
        parent_node_id: str | None = None,
    ) -> str | None:
        return self._mutation_service.add_gate(gate, sample_id, name, parent_node_id)

    def remove_population(self, sample_id: str, node_id: str) -> bool:
        return self._mutation_service.remove_population(sample_id, node_id)

    def select_gate(self, sample_id: str, node_id: str | None) -> None:
        self._selection_service.select_gate(sample_id, node_id)

    def add_logic_node(self, sample_id: str, operator: str, name: str | None = None) -> str | None:
        return self._mutation_service.add_logic_node(sample_id, operator, name)

    def add_connection(self, sample_id: str, source_node_id: str, target_node_id: str) -> bool:
        return self._mutation_service.add_connection(sample_id, source_node_id, target_node_id)

    def remove_connection(self, sample_id: str, source_node_id: str, target_node_id: str) -> bool:
        return self._mutation_service.remove_connection(sample_id, source_node_id, target_node_id)

    def rename_population(self, sample_id: str, node_id: str, new_name: str) -> bool:
        return self._mutation_service.rename_population(sample_id, node_id, new_name)

    def modify_gate(self, gate_id: str, sample_id: str, **kwargs) -> bool:
        return self._mutation_service.modify_gate(gate_id, sample_id, **kwargs)

    def split_population(self, sample_id: str, node_id: str) -> str | None:
        return self._mutation_service.split_population(sample_id, node_id)

    def copy_gates_to_group(self, source_sample_id: str) -> int:
        return self._mutation_service.copy_gates_to_group(source_sample_id)

    def get_gates_for_display(
        self, sample_id: str, parent_node_id: str | None = None
    ) -> tuple[list[Gate], list[GateNode]]:
        return self._mutation_service.get_gates_for_display(sample_id, parent_node_id)

    # ── Stats Orchestration ────────────────────────────────────────────────

    def recompute_all_stats(self, sample_id: str, sync: bool = False):
        from .services.stats_service import StatsService
        from .statistics_analysis import StatisticsAnalysis

        if sync or getattr(self, "sync_stats", False):
            analyzer = StatisticsAnalysis()
            analyzer.target_sample_id = sample_id
            results = analyzer.run(self._state)
            self._on_stats_finished(results)
            return

        task_id = StatsService.recompute_all_stats(self._state, sample_id, self._on_stats_finished)
        if task_id:
            logger.info(
                "Submitted StatisticsAnalysis for sample %s (task_id: %s)",
                sample_id,
                task_id,
            )

    def _on_stats_finished(self, results: dict) -> None:
        sample_id = results.get("sample_id")
        stats_map = results.get("stats", {})

        if not sample_id:
            return

        sample = self._state.data.experiment.samples.get(sample_id)
        if not sample:
            return

        from .services.gate_event_publisher import GateEventPublisher

        for node_id, stats in stats_map.items():
            node = sample.gate_tree.find_node_by_id(node_id)
            if node:
                node.statistics = stats
                CentralEventBus.publish(
                    events.GATE_STATS_UPDATED,
                    {"sample_id": sample_id, "node_id": node_id},
                )
                GateEventPublisher.publish_stats_computed(sample_id, node_id, stats)
            else:
                logger.warning(
                    f"_on_stats_finished: node_id {node_id} not found in tree for sample {sample_id}"
                )

        CentralEventBus.publish(events.ALL_STATS_UPDATED, {"sample_id": sample_id})
        logger.info(f"Applied background stats for sample {sample_id}")

    def cleanup(self):
        self._propagator.cleanup()
        logger.info("GateCoordinator cleaned up")
