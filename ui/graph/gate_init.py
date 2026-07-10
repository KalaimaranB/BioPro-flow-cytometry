"""Initializes the gate registry with default flow cytometry gates."""

from biopro.plugins.flow_cytometry.analysis.gating import (
    EllipseGate,
    PolygonGate,
    QuadrantGate,
    RangeGate,
    RectangleGate,
)

from .gate_registry import GateRegistry


def initialize_registry():
    """Register core gate types."""
    GateRegistry.register_gate_type("rectangle", RectangleGate)
    GateRegistry.register_gate_type("polygon", PolygonGate)
    GateRegistry.register_gate_type("ellipse", EllipseGate)
    GateRegistry.register_gate_type("quadrant", QuadrantGate)
    GateRegistry.register_gate_type("range", RangeGate)
