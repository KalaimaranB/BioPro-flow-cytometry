"""Data loader service for handling FCS file loading and compensation.

Encapsulates data ingestion to adhere to SRP and DIP, preventing
high-level services like WorkflowService from depending directly
on concrete io functions.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from biopro_sdk.plugin import get_logger

from ..compensation import apply_compensation
from ..fcs_io import load_fcs
from ..fcs_loader_analysis import FCSLoaderAnalysis

logger = get_logger(__name__, "flow_cytometry")


class DataLoaderService:
    """Service responsible for loading Flow Cytometry Standard data."""

    def __init__(self, scheduler: Any | None = None, plugin_id: str = "flow_cytometry"):
        self._scheduler = scheduler
        self._current_worker = None
        self._current_task_id = None
        self._plugin_id = plugin_id

    def reload_sample(self, sample, path: Path, compensation_matrix=None) -> bool:
        """Reload FCS event data for a given sample.

        Args:
            sample: The sample object to reload data into.
            path: Path to the FCS file.
            compensation_matrix: Optional compensation matrix to re-apply.

        Returns:
            bool: True if reload was successful, False otherwise.
        """
        if not path.exists():
            logger.warning(f"FCS file no longer exists: {path} (sample: {sample.display_name})")
            return False

        try:
            fcs_data = load_fcs(path)

            # Re-apply compensation if it was active when saved
            if (
                sample.is_compensated
                and compensation_matrix is not None
                and not fcs_data.is_compensated
            ):
                fcs_data.events = apply_compensation(fcs_data, compensation_matrix)
                fcs_data.is_compensated = True
                logger.info(
                    f"Re-applied BioPro compensation matrix to reloaded sample '{sample.display_name}'"
                )

            sample.fcs_data = fcs_data
            logger.info(
                f"Reloaded FCS data for '{sample.display_name}': {fcs_data.num_events} events"
            )
            return True
        except Exception as exc:
            logger.warning(f"Failed to reload FCS for '{sample.display_name}': {exc}")
            return False

    def load_samples_async(  # noqa: PLR0913
        self,
        paths: list[str | Path],
        state: Any,
        on_done: Callable[[dict], None],
        on_error_cb: Callable[[str], None],
        on_progress: Callable[[int], None] | None = None,
        project_manager: Any | None = None,
        copy_all: bool = False,
    ) -> None:
        """Submit a background task to load multiple FCS files."""
        if not self._scheduler:
            on_error_cb("No TaskScheduler available.")
            return

        analyzer = FCSLoaderAnalysis()
        analyzer.file_paths = paths
        analyzer.project_manager = project_manager
        analyzer.copy_all = copy_all

        try:
            worker = self._scheduler.submit(analyzer, state)
            self._current_worker = worker
            self._current_task_id = worker.task_id

            logger.info(f"DataLoaderService: Submitted load task {self._current_task_id}")

            if on_progress:
                worker.progress.connect(on_progress)

            def _on_finished(finished_task_id: str, results: dict):
                if finished_task_id == self._current_task_id:
                    self._current_worker = None
                    self._current_task_id = None
                    try:
                        self._scheduler.task_finished.disconnect(_on_finished)
                        self._scheduler.task_error.disconnect(_on_error)
                    except (TypeError, RuntimeError):
                        pass
                    on_done(results)

            def _on_error(error_task_id: str, error_msg: str):
                if error_task_id == self._current_task_id:
                    self._current_worker = None
                    self._current_task_id = None
                    try:
                        self._scheduler.task_finished.disconnect(_on_finished)
                        self._scheduler.task_error.disconnect(_on_error)
                    except (TypeError, RuntimeError):
                        pass
                    on_error_cb(error_msg)

            self._scheduler.task_finished.connect(_on_finished)
            self._scheduler.task_error.connect(_on_error)

        except Exception as e:
            logger.exception(f"DataLoaderService: Failed to submit task: {e}")
            on_error_cb(str(e))
