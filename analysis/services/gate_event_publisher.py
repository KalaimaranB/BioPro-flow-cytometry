"""Gate Event Publisher.

Centralizes all SDK EventBus publishing to decouple domain mutation
from external system messaging.
"""

from biopro_sdk.plugin import CentralEventBus

from .. import events


class GateEventPublisher:
    """Publishes gating events to the SDK's central event bus."""
    
    @staticmethod
    def publish_gate_created(sample_id: str, node_id: str, gate_id: str, name: str, is_split: bool = False) -> None:
        CentralEventBus.publish(events.GATE_CREATED, {
            "sample_id": sample_id,
            "node_id": node_id,
            "gate_id": gate_id,
            "name": name,
            "is_split": is_split
        })

    @staticmethod
    def publish_gate_deleted(sample_id: str, node_id: str, gate_id: str) -> None:
        CentralEventBus.publish(events.GATE_DELETED, {
            "sample_id": sample_id,
            "node_id": node_id,
            "gate_id": gate_id
        })

    @staticmethod
    def publish_gate_renamed(sample_id: str, node_id: str, new_name: str) -> None:
        CentralEventBus.publish(events.GATE_RENAMED, {
            "sample_id": sample_id,
            "node_id": node_id,
            "new_name": new_name
        })

    @staticmethod
    def publish_gate_modified(sample_id: str, gate_id: str) -> None:
        CentralEventBus.publish(events.GATE_MODIFIED, {
            "sample_id": sample_id,
            "gate_id": gate_id
        })

    @staticmethod
    def publish_gate_selected(sample_id: str, node_id: str | None) -> None:
        CentralEventBus.publish(events.GATE_SELECTED, {
            "sample_id": sample_id,
            "node_id": node_id
        })

    @staticmethod
    def publish_stats_computed(sample_id: str, node_id: str, stats: dict) -> None:
        CentralEventBus.publish(events.STATS_COMPUTED, {
            "sample_id": sample_id,
            "node_id": node_id,
            "stats": stats
        })
