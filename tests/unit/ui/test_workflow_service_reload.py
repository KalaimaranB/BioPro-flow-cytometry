"""Regression tests for WorkflowService.reload_fcs_data().

Confirms reload_fcs_data() delegates all samples to a single
DataLoaderService.reload_samples_batch() call (see the batching fix in
DataLoaderService) instead of fanning out per-sample calls, and that the
resulting {"loaded": [...], "failed": [...]} dict actually reaches the
on_complete callback in every code path — the scheduler path (via
_on_task_done_handler) and the synchronous fallback path.
"""

from unittest.mock import MagicMock

import pytest

from karcytics_plugins.flow_cytometry.analysis.experiment import Sample
from karcytics_plugins.flow_cytometry.analysis.state import FlowState
from karcytics_plugins.flow_cytometry.ui.services.workflow_service import WorkflowService


@pytest.fixture
def two_sample_state() -> FlowState:
    state = FlowState()
    state.data.experiment.samples["s1"] = Sample(sample_id="s1", display_name="Sample 1")
    state.data.experiment.samples["s2"] = Sample(sample_id="s2", display_name="Sample 2")
    return state


def test_reload_fcs_data_via_scheduler_batches_and_propagates_result(two_sample_state):
    data_loader = MagicMock()
    data_loader.reload_samples_batch.return_value = {
        "loaded": ["Sample 1", "Sample 2"],
        "failed": [],
    }

    scheduler = MagicMock()
    worker = MagicMock()
    worker.task_id = "task-123"
    scheduler.submit.return_value = worker
    data_loader._scheduler = scheduler

    service = WorkflowService(two_sample_state, data_loader, attachment_manager=MagicMock())

    on_complete = MagicMock()
    service.reload_fcs_data(
        {"s1": "a.fcs", "s2": "b.fcs"}, project_dir=None, on_complete=on_complete
    )

    # One task submitted for the whole reload — not one submission per sample.
    scheduler.submit.assert_called_once()
    submitted_task = scheduler.submit.call_args[0][0]

    # Run the task body the way the real scheduler would.
    task_result = submitted_task.func()

    # The critical regression check: a single batched call covering every
    # sample, not N serialized single-file load_fcs() calls.
    data_loader.reload_samples_batch.assert_called_once()
    samples_with_paths = data_loader.reload_samples_batch.call_args[0][0]
    assert {s.sample_id for s, _path in samples_with_paths} == {"s1", "s2"}

    # on_complete must not fire until the scheduler reports the task done.
    on_complete.assert_not_called()
    service._on_task_done_handler("task-123", task_result)
    on_complete.assert_called_once_with(task_result)
    assert task_result == {"loaded": ["Sample 1", "Sample 2"], "failed": []}


def test_reload_fcs_data_ignores_unrelated_task_completion(two_sample_state):
    """A different task finishing must not trigger this reload's on_complete."""
    data_loader = MagicMock()
    scheduler = MagicMock()
    worker = MagicMock()
    worker.task_id = "task-123"
    scheduler.submit.return_value = worker
    data_loader._scheduler = scheduler

    service = WorkflowService(two_sample_state, data_loader, attachment_manager=MagicMock())

    on_complete = MagicMock()
    service.reload_fcs_data({"s1": "a.fcs"}, project_dir=None, on_complete=on_complete)

    service._on_task_done_handler("some-other-task", {"loaded": [], "failed": []})
    on_complete.assert_not_called()


def test_reload_fcs_data_sync_fallback_passes_result_to_on_complete(two_sample_state):
    """Without a TaskScheduler, the batch call still runs inline and on_complete gets it."""
    data_loader = MagicMock()
    data_loader._scheduler = None
    data_loader.reload_samples_batch.return_value = {
        "loaded": ["Sample 1"],
        "failed": ["Sample 2"],
    }

    service = WorkflowService(two_sample_state, data_loader, attachment_manager=MagicMock())

    on_complete = MagicMock()
    service.reload_fcs_data(
        {"s1": "a.fcs", "s2": "b.fcs"}, project_dir=None, on_complete=on_complete
    )

    data_loader.reload_samples_batch.assert_called_once()
    on_complete.assert_called_once_with({"loaded": ["Sample 1"], "failed": ["Sample 2"]})


def test_reload_fcs_data_skips_unknown_sample_ids(two_sample_state):
    """A sample_id no longer present in the experiment must be silently skipped."""
    data_loader = MagicMock()
    data_loader._scheduler = None
    data_loader.reload_samples_batch.return_value = {"loaded": [], "failed": []}

    service = WorkflowService(two_sample_state, data_loader, attachment_manager=MagicMock())

    service.reload_fcs_data({"s1": "a.fcs", "ghost": "c.fcs"}, project_dir=None)

    samples_with_paths = data_loader.reload_samples_batch.call_args[0][0]
    assert {s.sample_id for s, _path in samples_with_paths} == {"s1"}
