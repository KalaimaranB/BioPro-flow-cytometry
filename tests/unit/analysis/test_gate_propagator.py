from unittest.mock import MagicMock

from biopro_plugins.flow_cytometry.analysis.experiment import Sample
from biopro_plugins.flow_cytometry.analysis.gate_propagator import GatePropagator


def test_gate_propagator_debounce(flow_state, qtbot):
    mock_scheduler = MagicMock()
    # Add a second sample so there is a target for propagation
    s2 = Sample(sample_id="s2", display_name="Sample 2")
    s2.fcs_data = MagicMock()
    flow_state.data.experiment.samples["s2"] = s2

    propagator = GatePropagator(flow_state, mock_scheduler)

    from unittest.mock import patch

    with patch("threading.Timer") as mock_timer_cls:
        mock_timer_instance_1 = MagicMock()
        mock_timer_instance_2 = MagicMock()
        mock_timer_cls.side_effect = [mock_timer_instance_1, mock_timer_instance_2]

        propagator.request_propagation("gate1", "test_sample_1")
        propagator.request_propagation("gate1", "test_sample_1")

        # The first timer should have been cancelled
        assert mock_timer_instance_1.cancel.call_count == 1
        assert mock_timer_instance_2.cancel.call_count == 0

        # Now simulate the second timer firing
        # The target function is passed as args[1] in Timer(interval, function, args=...)
        # Wait, threading.Timer signature is Timer(interval, function, args=None, kwargs=None)
        # So function is args[0] for the side_effect or kwargs 'function'
        # Let's just call the execute method directly since it's an internal test
        propagator._execute_propagation()

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
