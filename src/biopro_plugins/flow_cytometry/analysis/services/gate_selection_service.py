"""Gate Selection Service.

Handles UI selection state tracking for gates.
"""

from biopro_sdk.plugin import CentralEventBus, get_logger

from .. import events
from ..state import FlowState
from .gate_event_publisher import GateEventPublisher

logger = get_logger(__name__, "flow_cytometry")


class GateSelectionService:
    """Manages the currently selected gate in the workspace."""

    def __init__(self, state: FlowState, coordinator):
        self._state = state
        self._coordinator = coordinator

    def select_gate(self, sample_id: str, node_id: str | None) -> None:
        """Update the selected gate and notify listeners.

        Args:
            sample_id: The sample context.
            node_id:   The population node to select (None to deselect).
        """
        old_id = self._state.view.current_gate_id
        if old_id == node_id:
            return

        self._state.view.current_gate_id = node_id
        CentralEventBus.publish(
            events.GATE_SELECTED, {"sample_id": sample_id, "node_id": node_id or ""}
        )

        GateEventPublisher.publish_gate_selected(sample_id, node_id)
        logger.debug(f"Selection changed: {old_id} -> {node_id}")
