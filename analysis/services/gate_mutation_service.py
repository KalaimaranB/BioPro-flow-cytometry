"""Gate Mutation Service.

Handles pure domain model edits for the gating tree (GateNode).
"""

from typing import Any

from biopro_sdk.plugin import CentralEventBus, get_logger

from .. import events
from ..gating import Gate, GateNode
from ..state import FlowState
from .gate_event_publisher import GateEventPublisher
from .gating_service import GatingService
from .modifier import GateModifier
from .naming import NamingService
from .splitter import PopulationSplitter

logger = get_logger(__name__, "flow_cytometry")


class GateMutationService:
    """Modifies the gating tree and triggers re-computation via the coordinator."""

    def __init__(
        self,
        state: FlowState,
        coordinator: Any,
        selection_service: Any,
        axis_manager: Any,
        population_service: Any,
    ):
        self._state = state
        self._coordinator = coordinator
        self._selection_service = selection_service
        self._axis_manager = axis_manager
        self._population_service = population_service

    def generate_unique_name(self, sample_id: str, prefix: str = "Gate") -> str:
        return NamingService.generate_unique_name(
            self._state.data.experiment, sample_id, prefix
        )

    def add_gate(
        self,
        gate: Gate,
        sample_id: str,
        name: str | None = None,
        parent_node_id: str | None = None,
    ) -> str | None:
        sample = self._state.data.experiment.samples.get(sample_id)
        if sample is None:
            logger.warning("Cannot add gate — sample %s not found.", sample_id)
            return None

        if not name:
            name = self.generate_unique_name(sample_id)

        child_nodes = self._population_service.add_population(
            sample_id, gate, parent_node_id, name
        )
        if not child_nodes:
            return None

        if not isinstance(child_nodes, list):
            child_nodes = [child_nodes]

        self._coordinator.recompute_all_stats(sample_id)

        source_node = (
            sample.gate_tree.find_node_by_id(parent_node_id)
            if parent_node_id
            else sample.gate_tree
        )
        if source_node and not source_node.creation_view:
            x_scale = self._axis_manager.get_scale(gate.x_param, sample_id)
            y_scale = (
                self._axis_manager.get_scale(gate.y_param, sample_id)
                if gate.y_param
                else None
            )

            # For range gates (y_param=None) drawn while in pseudocolor mode, the user
            # was looking at a 2D scatter. Record the view's current Y-axis so the
            # pipeline thumbnail can reconstruct that scatter with vertical range lines.
            view_y_param = None
            view_y_scale = None
            if (
                gate.y_param is None
                and self._state.view.active_plot_type == "pseudocolor"
            ):
                view_y_param = self._state.view.active_y_param or None
                if view_y_param:
                    vy_scale = self._axis_manager.get_scale(view_y_param, sample_id)
                    view_y_scale = vy_scale.to_dict() if vy_scale else None

            source_node.creation_view = {
                "x_param": gate.x_param,
                "y_param": gate.y_param,
                "view_y_param": view_y_param,
                "x_scale": x_scale.to_dict(),
                "y_scale": y_scale.to_dict() if y_scale else None,
                "view_y_scale": view_y_scale,
                "plot_type": self._state.view.active_plot_type,
            }

        for node in child_nodes:
            CentralEventBus.publish(
                events.GATE_CREATED, {"sample_id": sample_id, "node_id": node.node_id}
            )
            GateEventPublisher.publish_gate_created(
                sample_id, node.node_id, gate.gate_id, node.name
            )
            logger.info(
                "Population '%s' added to sample '%s' using %s.",
                node.name,
                sample.display_name,
                type(gate).__name__,
            )

        self._coordinator.request_propagation(gate.gate_id, sample_id)
        first_node = child_nodes[0]
        self._selection_service.select_gate(sample_id, first_node.node_id)
        return first_node.node_id

    def add_logic_node(
        self, sample_id: str, operator: str, name: str | None = None
    ) -> str | None:
        sample = self._state.data.experiment.samples.get(sample_id)
        if sample is None:
            return None

        name = name or f"{operator} Logic"
        # Create logic node with NO parents and NOT in root's children.
        # The user must manually wire gate nodes into it via drag-drop.
        # This avoids the "root visual replacement" bug where the AND node
        # was placed as a child of root and then the root→AND edge was
        # hidden after wiring, leaving an orphaned visual.
        node = GateNode(name=name, logic_operator=operator, parents=[])
        # We still need the node reachable from the tree for find_node_by_id.
        # Attaching to root.children is the right way, but we suppress the
        # default root→logic edge in _build_edges_recursive by checking parents.
        sample.gate_tree.children.append(node)

        self._coordinator.recompute_all_stats(sample_id)
        CentralEventBus.publish(
            events.GATE_CREATED, {"sample_id": sample_id, "node_id": node.node_id}
        )
        return node.node_id

    def add_connection(
        self, sample_id: str, source_node_id: str, target_node_id: str
    ) -> bool:
        sample = self._state.data.experiment.samples.get(sample_id)
        if sample is None:
            return False

        source = sample.gate_tree.find_node_by_id(source_node_id)
        target = sample.gate_tree.find_node_by_id(target_node_id)

        if not source or not target:
            return False

        if target is sample.gate_tree:
            logger.warning("Cannot wire nodes: target is the root 'All Events' node")
            return False

        if target.find_node_by_id(source_node_id):
            logger.warning("Cannot wire nodes: creates a cycle")
            return False

        if source not in target.parents:
            target.parents.append(source)
        if target not in source.children:
            source.children.append(target)

        # Remove the root sentinel from the logic node's parent list once it has
        # real parents wired in. This ensures apply_hierarchy does NOT include
        # root in the AND/OR logic. However, we KEEP the logic node in
        # root.children so the stats walker can still discover and process it.
        if sample.gate_tree in target.parents and len(target.parents) > 1:
            target.parents.remove(sample.gate_tree)
            # NOTE: intentionally NOT removing target from sample.gate_tree.children
            # — root.children is used by _walk_and_compute to discover logic nodes.
            # The canvas already suppresses the root→logic visual edge separately.

        self._coordinator.recompute_all_stats(sample_id)
        CentralEventBus.publish(
            events.GATE_STATS_UPDATED,
            {"sample_id": sample_id, "node_id": target_node_id},
        )
        return True

    def remove_connection(
        self, sample_id: str, source_node_id: str, target_node_id: str
    ) -> bool:
        sample = self._state.data.experiment.samples.get(sample_id)
        if sample is None:
            return False

        source = sample.gate_tree.find_node_by_id(source_node_id)
        target = sample.gate_tree.find_node_by_id(target_node_id)

        if not source or not target:
            return False

        if source in target.parents:
            target.parents.remove(source)
        if target in source.children:
            source.children.remove(target)

        if not target.parents:
            target.parents.append(sample.gate_tree)
            sample.gate_tree.children.append(target)

        self._coordinator.recompute_all_stats(sample_id)
        CentralEventBus.publish(
            events.GATE_STATS_UPDATED,
            {"sample_id": sample_id, "node_id": target_node_id},
        )
        return True

    def modify_gate(self, gate_id: str, sample_id: str, **kwargs: Any) -> bool:
        success = GateModifier.modify_gate(
            self._state.data.experiment, gate_id, sample_id, **kwargs
        )
        if not success:
            return False

        self._coordinator.recompute_all_stats(sample_id)

        sample = self._state.data.experiment.samples.get(sample_id)
        if sample:
            nodes = sample.gate_tree.find_nodes_by_gate(gate_id)
            for node in nodes:
                CentralEventBus.publish(
                    events.GATE_STATS_UPDATED,
                    {"sample_id": sample_id, "node_id": node.node_id},
                )

        GateEventPublisher.publish_gate_modified(sample_id, gate_id)

        CentralEventBus.publish(
            events.GATE_MODIFIED, {"sample_id": sample_id, "gate_id": gate_id}
        )
        self._coordinator.request_propagation(gate_id, sample_id)
        return True

    def split_population(self, sample_id: str, node_id: str) -> str | None:
        result = PopulationSplitter.split_population(
            self._state.data.experiment, sample_id, node_id
        )
        if result is None:
            return None

        new_node_id, new_name, gate_id = result

        self._coordinator.recompute_all_stats(sample_id)

        CentralEventBus.publish(
            events.GATE_CREATED, {"sample_id": sample_id, "node_id": new_node_id}
        )
        CentralEventBus.publish(
            events.GATE_STATS_UPDATED, {"sample_id": sample_id, "node_id": new_node_id}
        )

        GateEventPublisher.publish_gate_created(
            sample_id, new_node_id, gate_id, new_name, is_split=True
        )

        logger.info("Split population created: '%s'", new_name)
        return new_node_id

    def remove_population(self, sample_id: str, node_id: str) -> bool:
        sample = self._state.data.experiment.samples.get(sample_id)
        if sample is None:
            return False

        node = self._population_service.find_node(sample_id, node_id)
        if node is None:
            return False

        old_gate_id = node.gate.gate_id if node.gate else None

        success = self._population_service.remove_population(sample_id, node_id)
        if not success:
            return False

        CentralEventBus.publish(
            events.GATE_DELETED, {"sample_id": sample_id, "node_id": node_id}
        )

        GateEventPublisher.publish_gate_deleted(sample_id, node_id, old_gate_id)
        logger.info("Population %s removed from sample %s.", node_id, sample_id)
        return True

    def rename_population(self, sample_id: str, node_id: str, new_name: str) -> bool:
        sample = self._state.data.experiment.samples.get(sample_id)
        if sample is None:
            return False

        node = sample.gate_tree.find_node_by_id(node_id)
        if node is None:
            return False

        node.name = new_name
        CentralEventBus.publish(
            events.GATE_RENAMED, {"sample_id": sample_id, "node_id": node_id}
        )
        CentralEventBus.publish(
            events.GATE_STATS_UPDATED, {"sample_id": sample_id, "node_id": node_id}
        )

        GateEventPublisher.publish_gate_renamed(sample_id, node_id, new_name)

        gate_id = self._find_root_gate_id(node)
        if gate_id:
            self._coordinator.request_propagation(gate_id, sample_id)
        return True

    def _find_root_gate_id(self, node: GateNode) -> str | None:
        """Traverse upwards to find the first physical gate. Useful for UI selection syncing."""
        queue = [node]
        visited = set()
        while queue:
            current = queue.pop(0)
            if current.node_id in visited:
                continue
            visited.add(current.node_id)
            if current.gate is not None:
                return current.gate.gate_id
            queue.extend(current.parents)
        return None

    def copy_gates_to_group(self, source_sample_id: str) -> int:
        count = GatingService.copy_gates_to_group(
            self._state.data.experiment, source_sample_id
        )

        source = self._state.data.experiment.samples.get(source_sample_id)
        if source:
            for target_id in self._get_target_sample_ids(source_sample_id):
                self._coordinator.recompute_all_stats(target_id)

        logger.info("Copied gate tree from source to %d samples.", count)
        return count

    def _get_target_sample_ids(self, source_sample_id: str) -> list[str]:
        experiment = self._state.data.experiment
        targets = set()
        for group in experiment.groups.values():
            if source_sample_id in group.sample_ids:
                for sid in group.sample_ids:
                    if sid != source_sample_id:
                        targets.add(sid)
        if not targets:
            for sid in experiment.samples:
                if sid != source_sample_id:
                    targets.add(sid)
        return list(targets)

    def get_gates_for_display(
        self, sample_id: str, parent_node_id: str | None = None
    ) -> tuple[list[Gate], list[GateNode]]:
        sample = self._state.data.experiment.samples.get(sample_id)
        if sample is None:
            return ([], [])
        return GatingService.get_gates_for_display(sample, parent_node_id)
