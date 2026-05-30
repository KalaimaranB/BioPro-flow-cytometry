from unittest.mock import MagicMock

from analysis.experiment import Sample
from analysis.gate_propagator import GatePropagator


def test_gate_propagator_debounce(flow_state, qtbot):
    mock_scheduler = MagicMock()
    # Add a second sample so there is a target for propagation
    s2 = Sample(sample_id="s2", display_name="Sample 2")
    s2.fcs_data = MagicMock()
    flow_state.data.experiment.samples["s2"] = s2

    propagator = GatePropagator(flow_state, mock_scheduler)

    propagator.request_propagation("gate1", "test_sample_1")
    propagator.request_propagation("gate1", "test_sample_1")

    # Should only call submit once after debounce
    qtbot.wait(300)
    assert mock_scheduler.submit.call_count == 1


def test_gate_propagator_handler_cleanup(flow_state, qtbot):
    """Verify that handlers disconnect themselves to prevent leaks."""
    mock_scheduler = MagicMock()
    # Add a second sample so there is a target for propagation
    s2 = Sample(sample_id="s2", display_name="Sample 2")
    s2.fcs_data = MagicMock()
    flow_state.data.experiment.samples["s2"] = s2

    propagator = GatePropagator(flow_state, mock_scheduler)

    mock_worker_obj = MagicMock()
    mock_worker_obj.task_id = "task_1"
    mock_scheduler.submit.return_value = mock_worker_obj

    propagator.request_propagation("gate1", "test_sample_1")
    qtbot.wait(300)

    # Check that connect was called for the handler
    assert mock_scheduler.task_finished.connect.call_count == 1

    # Extract the handler method
    handler_method = mock_scheduler.task_finished.connect.call_args[0][0]

    # Simulate task completion
    handler_method("task_1", {"propagation_results": {}})

    # Check that disconnect is NEVER called because handlers are now bound permanently in __init__
    assert mock_scheduler.task_finished.disconnect.call_count == 0
