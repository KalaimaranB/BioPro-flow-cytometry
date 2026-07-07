"""Service for managing background statistics computation."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from biopro.core.task_scheduler import task_scheduler
from biopro_sdk.plugin import get_logger

from ..statistics_analysis import StatisticsAnalysis

if TYPE_CHECKING:
    from ..state import FlowState

logger = get_logger(__name__, "flow_cytometry")


class StatsService:
    """Handles submission and application of population statistics."""

    @staticmethod
    def recompute_all_stats(
        state: FlowState, sample_id: str, callback: Callable | None = None
    ) -> str | None:
        """Submit a background task to recompute all gate statistics for a sample."""
        sample = state.data.experiment.samples.get(sample_id)
        if sample is None:
            logger.warning(f"StatsService: sample {sample_id} not found")
            return None
        if sample.fcs_data is None:
            logger.warning(f"StatsService: sample {sample_id} has no FCS data")
            return None

        analyzer = StatisticsAnalysis()
        analyzer.target_sample_id = sample_id

        worker = task_scheduler.submit(analyzer, state)
        task_id = worker.task_id
        logger.info(f"StatsService: submitted task {task_id} for sample {sample_id}")

        if callback:
            # Use task_scheduler.task_finished so we get the callback AFTER
            # the scheduler's own _on_task_finished fires and before cleanup
            # disconnects worker.finished.
            def _on_finished(finished_task_id: str, results: dict):
                if finished_task_id == task_id:
                    try:
                        task_scheduler.task_finished.disconnect(_on_finished)
                    except (TypeError, RuntimeError):
                        pass
                    callback(results)

            task_scheduler.task_finished.connect(_on_finished)

        return task_id
