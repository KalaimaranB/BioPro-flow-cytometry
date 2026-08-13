from unittest.mock import MagicMock

import pytest
from karcytics_sdk.plugin import CentralEventBus
from PyQt6.QtWidgets import QApplication

from karcytics_plugins.flow_cytometry.analysis.axis_manager import AxisManager
from karcytics_plugins.flow_cytometry.analysis.events import GATE_RENAMED, SAMPLE_UPDATED
from karcytics_plugins.flow_cytometry.analysis.experiment import Sample
from karcytics_plugins.flow_cytometry.analysis.population_service import PopulationService
from karcytics_plugins.flow_cytometry.analysis.state import FlowState
from karcytics_plugins.flow_cytometry.ui.graph.graph_window import GraphWindow


@pytest.fixture
def graph_window_for_teardown(qtbot):
    state = FlowState()
    state.axis_manager = AxisManager(state)
    state.population_service = PopulationService(state)

    sample = Sample(sample_id="s_test", display_name="Sample Test")
    sample.fcs_data = MagicMock()
    sample.fcs_data.channels = ["FSC-A", "SSC-A"]
    sample.fcs_data.markers = ["", ""]
    import pandas as pd

    sample.fcs_data.events = pd.DataFrame({"FSC-A": [1], "SSC-A": [1]})
    state.data.experiment.samples["s_test"] = sample

    pop_mock = MagicMock()
    pop_mock.get_gated_events.return_value = sample.fcs_data.events

    win = GraphWindow(
        state,
        "s_test",
        axis_manager=state.axis_manager,
        population_service=pop_mock,
        controller=MagicMock(),
    )
    return win


@pytest.mark.ui
def test_graph_window_deleted_c_object_event_handling(qtbot, graph_window_for_teardown):
    """Test that if a GraphWindow's underlying C++ object is deleted,
    pending events from the CentralEventBus do not cause a RuntimeError.
    """
    win = graph_window_for_teardown

    # 1. Verify it handles events fine when alive
    try:
        CentralEventBus.publish(SAMPLE_UPDATED, {"sample_id": "s_test"})
        CentralEventBus.publish(GATE_RENAMED, {"sample_id": "s_test"})
    except RuntimeError:
        pytest.fail("RuntimeError raised when window was ALIVE")

    # 2. Delete the underlying C++ widget to simulate closing a tab or window
    from PyQt6 import sip

    sip.delete(win)

    # Wait for the delete to propagate (in case of deferred deletes)
    QApplication.processEvents()

    # 3. Fire the events again! If our try/except block works, this will NOT raise a RuntimeError
    # and instead will cleanly unsubscribe.
    try:
        CentralEventBus.publish(SAMPLE_UPDATED, {"sample_id": "s_test"})
        CentralEventBus.publish(GATE_RENAMED, {"sample_id": "s_test"})
    except RuntimeError as e:
        pytest.fail(f"RuntimeError leaked through! {e}")
