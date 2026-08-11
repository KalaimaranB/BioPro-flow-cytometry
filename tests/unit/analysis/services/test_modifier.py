import pytest

from biopro_plugins.flow_cytometry.analysis.experiment import Experiment, Sample
from biopro_plugins.flow_cytometry.analysis.gating import (
    EllipseGate,
    PolygonGate,
    QuadrantGate,
    RangeGate,
    RectangleGate,
)
from biopro_plugins.flow_cytometry.analysis.services.modifier import GateModifier


@pytest.fixture
def experiment_with_sample():
    exp = Experiment()
    sample = Sample(sample_id="test_sample", display_name="Test Sample")
    exp.samples["test_sample"] = sample

    # Add a gate to the tree
    gate = RectangleGate("FSC-A", "SSC-A", x_min=10, x_max=100, gate_id="gate_123")
    node = sample.gate_tree.add_child(gate, name="Population A")
    return exp, sample, node, gate


def test_modify_gate_geometry(experiment_with_sample):
    exp, sample, node, gate = experiment_with_sample

    # Modify the gate geometry
    success = GateModifier.modify_gate(
        exp, gate_id="gate_123", sample_id="test_sample", x_min=20, x_max=200
    )

    assert success is True
    assert gate.x_min == 20
    assert gate.x_max == 200
    # Unchanged parameters should remain intact
    assert getattr(gate, "y_min", None) is None or gate.y_min == float("-inf")


def test_modify_gate_identity_negated(experiment_with_sample):
    exp, sample, node, gate = experiment_with_sample

    assert node.negated is False

    # Modify the gate node identity
    success = GateModifier.modify_gate(
        exp, gate_id="gate_123", sample_id="test_sample", negated=True
    )

    assert success is True
    assert node.negated is True


def test_modify_gate_invalid_sample():
    exp = Experiment()
    success = GateModifier.modify_gate(exp, "gate_123", "invalid_sample", x_min=0)
    assert success is False


def test_modify_gate_invalid_gate(experiment_with_sample):
    exp, sample, node, gate = experiment_with_sample
    success = GateModifier.modify_gate(exp, "invalid_gate", "test_sample", x_min=0)
    assert success is False


def test_modify_gate_multiple_linked_nodes(experiment_with_sample):
    exp, sample, node1, gate = experiment_with_sample

    # Add a sibling node linked to the exact same gate instance
    node2 = sample.gate_tree.add_child(gate, name="Population B")

    # Modify both geometry and negated state
    success = GateModifier.modify_gate(
        exp, gate_id="gate_123", sample_id="test_sample", x_max=500, negated=True
    )

    assert success is True
    assert gate.x_max == 500

    # BOTH nodes should have the identity change applied if passed
    assert node1.negated is True
    assert node2.negated is True


def test_modify_gate_rejects_inverted_rectangle_bounds(experiment_with_sample):
    """x_min >= x_max must be rejected — and rejected atomically, not
    partially applied (x_max in this call would otherwise have succeeded).
    """
    exp, sample, node, gate = experiment_with_sample
    original_x_max = gate.x_max

    success = GateModifier.modify_gate(
        exp, gate_id="gate_123", sample_id="test_sample", x_min=500, x_max=50
    )

    assert success is False
    assert gate.x_min == 10  # unchanged
    assert gate.x_max == original_x_max  # unchanged — no partial apply


def test_modify_gate_rejects_inverted_range_bounds():
    exp = Experiment()
    sample = Sample(sample_id="s1", display_name="S1")
    exp.samples["s1"] = sample
    gate = RangeGate("FSC-A", low=10, high=100, gate_id="range_1")
    sample.gate_tree.add_child(gate, name="Range Pop")

    success = GateModifier.modify_gate(exp, gate_id="range_1", sample_id="s1", low=200)

    assert success is False
    assert gate.low == 10


def test_modify_gate_rejects_non_positive_ellipse_axes():
    exp = Experiment()
    sample = Sample(sample_id="s1", display_name="S1")
    exp.samples["s1"] = sample
    gate = EllipseGate("FSC-A", "SSC-A", center=(50, 50), width=10, height=10, gate_id="ell_1")
    sample.gate_tree.add_child(gate, name="Ellipse Pop")

    success = GateModifier.modify_gate(exp, gate_id="ell_1", sample_id="s1", width=0)

    assert success is False
    assert gate.width == 10


def test_modify_gate_rejects_degenerate_polygon():
    exp = Experiment()
    sample = Sample(sample_id="s1", display_name="S1")
    exp.samples["s1"] = sample
    gate = PolygonGate("FSC-A", "SSC-A", vertices=[(0, 0), (10, 0), (10, 10)], gate_id="poly_1")
    sample.gate_tree.add_child(gate, name="Polygon Pop")

    success = GateModifier.modify_gate(
        exp, gate_id="poly_1", sample_id="s1", vertices=[(0, 0), (10, 0)]
    )

    assert success is False
    assert len(gate.vertices) == 3


def test_modify_quadrant_subgate_resolves_to_parent():
    """QuadrantGate.create_nodes() only ever creates QuadrantSubGate-wrapping
    nodes — modify_gate() must redirect the mutation to the shared parent
    gate, since the subgate itself has no x_mid/y_mid of its own (and would
    otherwise silently no-op via the hasattr() filter).
    """
    exp = Experiment()
    sample = Sample(sample_id="s1", display_name="S1")
    exp.samples["s1"] = sample
    quadrant = QuadrantGate("FSC-A", "SSC-A", x_mid=50, y_mid=50, gate_id="quad_1")
    nodes = quadrant.create_nodes(sample.gate_tree)
    sample.gate_tree.children.extend(nodes)
    q1_subgate_id = nodes[0].gate.gate_id  # e.g. "quad_1_Q1"

    success = GateModifier.modify_gate(
        exp, gate_id=q1_subgate_id, sample_id="s1", x_mid=75, y_mid=25
    )

    assert success is True
    assert quadrant.x_mid == 75
    assert quadrant.y_mid == 25
    # All 4 subgates share the same parent object — one mutation updates them all.
    for node in nodes:
        assert node.gate.parent is quadrant
