import pytest

from biopro.plugins.flow_cytometry.analysis.experiment import Sample
from biopro.plugins.flow_cytometry.analysis.gating import RectangleGate
from biopro.plugins.flow_cytometry.analysis.state import FlowState
from biopro.plugins.flow_cytometry.ui.widgets.gate_hierarchy import GateHierarchy


@pytest.fixture
def flow_state_hierarchy():
    state = FlowState()

    # Mock Sample 1
    sample1 = Sample(sample_id="s1", display_name="Sample 1")

    # Add a gate
    gate = RectangleGate("FSC-A", "SSC-A", x_min=10, x_max=100, y_min=10, y_max=100)
    gate.gate_id = "g1"

    node = sample1.gate_tree.add_child(gate, name="Singlets")
    node.statistics = {"count": 1000, "pct_parent": 50.0, "pct_total": 50.0}

    state.data.experiment.samples["s1"] = sample1
    return state


@pytest.mark.ui
def test_gate_hierarchy_init(qtbot, flow_state_hierarchy):
    widget = GateHierarchy(flow_state_hierarchy)
    qtbot.addWidget(widget)
    assert widget._state == flow_state_hierarchy
    assert widget._active_sample_id is None
