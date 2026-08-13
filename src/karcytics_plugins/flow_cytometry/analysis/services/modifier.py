"""Service for modifying gate parameters with validation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from karcytics_sdk.plugin import get_logger

from ..constants import POLYGON_MIN_VERTICES
from ..gating.ellipse import EllipseGate
from ..gating.polygon import PolygonGate
from ..gating.quadrant import QuadrantSubGate
from ..gating.range import RangeGate
from ..gating.rectangle import RectangleGate

if TYPE_CHECKING:
    from ..experiment import Experiment
    from ..gating import Gate

logger = get_logger(__name__, "flow_cytometry")


class GateModifier:
    """Service for modifying gate parameters with validation."""

    @staticmethod
    def modify_gate(experiment: Experiment, gate_id: str, sample_id: str, **kwargs: Any) -> bool:
        """Modify a gate's physical parameters.

        Args:
            experiment: The active experiment model.
            gate_id:    ID of the gate geometry to modify.
            sample_id:  ID of the sample owning the gate.
            **kwargs:   Parameters to update.

        Returns:
            True if modification was successful.
        """
        sample = experiment.samples.get(sample_id)
        if sample is None:
            return False

        # Find all nodes that share this gate geometry
        nodes = sample.gate_tree.find_nodes_by_gate(gate_id)
        if not nodes:
            return False

        gate = nodes[0].gate
        if gate is None:
            return False

        # QuadrantGate.create_nodes() only ever creates QuadrantSubGate-
        # wrapping nodes — there is no node wrapping the bare parent
        # QuadrantGate — so the geometry that actually needs mutating
        # (x_mid/y_mid) lives on gate.parent, shared by all 4 quadrant
        # nodes. Redirecting here (rather than changing which gate_id is
        # looked up) means every quadrant sub-node's crosshair updates from
        # a single mutation, with no extra fan-out.
        if isinstance(gate, QuadrantSubGate):
            gate = gate.parent

        # Identity-level changes (negated) only apply if we want them to,
        # but usually modify_gate is for geometry.
        node_kwargs: dict[str, Any] = {}
        if "negated" in kwargs:
            node_kwargs["negated"] = kwargs.pop("negated")

        candidate = {key: value for key, value in kwargs.items() if hasattr(gate, key)}
        ok, error = GateModifier._validate(gate, candidate)
        if not ok:
            logger.warning("Gate modification rejected for %s: %s", gate_id, error)
            return False

        for key, value in candidate.items():
            setattr(gate, key, value)

        # Update identity for all linked nodes
        for node in nodes:
            for key, value in node_kwargs.items():
                setattr(node, key, value)

        return True

    @staticmethod
    def _validate(gate: Gate, candidate: dict[str, Any]) -> tuple[bool, str | None]:
        """Reject a prospective attribute update that would leave `gate` in
        an invalid geometric state. Validated against the merged (current +
        candidate) state *before* anything is mutated, so a rejected edit
        never partially applies.
        """
        merged = {**gate.__dict__, **candidate}

        if isinstance(gate, RectangleGate):
            if merged["x_min"] >= merged["x_max"]:
                return False, "x_min must be < x_max"
            if merged["y_min"] >= merged["y_max"]:
                return False, "y_min must be < y_max"
        elif isinstance(gate, RangeGate):
            if merged["low"] >= merged["high"]:
                return False, "low must be < high"
        elif isinstance(gate, EllipseGate):
            if merged["width"] <= 0 or merged["height"] <= 0:
                return False, "width/height must be > 0"
        elif isinstance(gate, PolygonGate):
            if len(merged["vertices"]) < POLYGON_MIN_VERTICES:
                return False, "polygon requires at least 3 vertices"
        # QuadrantGate: x_mid/y_mid have no invariant beyond being finite.

        return True, None
