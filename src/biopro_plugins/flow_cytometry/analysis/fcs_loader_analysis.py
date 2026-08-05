"""FCS Loader Analysis — Background worker for loading FCS files asynchronously."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from biopro_sdk.plugin import AnalysisBase, PluginState, get_logger

from .fcs_io import load_fcs

logger = get_logger(__name__, "flow_cytometry")


class FCSLoaderAnalysis(AnalysisBase):
    """Background analyzer for parallel loading of FCS files."""

    def __init__(self, plugin_id: str = "flow_cytometry"):
        super().__init__(plugin_id)
        self.file_paths: list[str | Path] = []
        self.project_manager: Any = None
        self.copy_all: bool = False

    def validate(self, _state: Any) -> tuple[bool, str]:
        """Verify that there are files to load and that they exist."""
        if not getattr(self, "file_paths", []):
            return False, "No files selected for loading."
        for path in self.file_paths:
            if not Path(path).exists():
                return False, f"File not found: {path}"
        return True, ""

    def run(self, _state: PluginState | None = None) -> dict[str, Any]:
        """Loads FCS files in parallel and emits progress."""
        logger.info(f"FCSLoaderAnalysis: Starting load for {len(self.file_paths)} files")

        results = {}
        total_files = len(self.file_paths)
        completed = 0

        self.signals.analysis_progress.emit(0)

        pm_lock = threading.Lock()

        def load_and_register(path: Path) -> tuple[Path, Any]:
            final_path = path
            pm = getattr(self, "project_manager", None)
            if pm:
                with pm_lock:
                    is_in_workspace = pm.assets_dir.resolve() in path.resolve().parents
                    should_copy = getattr(self, "copy_all", False) and not is_in_workspace
                    try:
                        file_hash = pm.add_image(path, should_copy)
                        resolved = pm.get_asset_path(file_hash)
                        if resolved:
                            final_path = resolved
                    except Exception as e:
                        logger.exception(f"Asset registration error for {path}: {e}")

            fcs_data = load_fcs(final_path)
            return final_path, fcs_data

        # ThreadPoolExecutor is safe for pandas/numpy parsing since it releases GIL
        with ThreadPoolExecutor() as executor:
            # Map file paths to futures
            future_to_path = {
                executor.submit(load_and_register, Path(path)): Path(path)
                for path in self.file_paths
            }

            for future in as_completed(future_to_path):
                if self.is_cancelled():
                    # Executor cannot be cleanly interrupted without cancelling futures
                    for f in future_to_path:
                        f.cancel()
                    return {"error": "Task cancelled."}

                path = future_to_path[future]
                try:
                    final_path, fcs_data = future.result()
                    results[str(final_path)] = fcs_data
                except Exception as exc:
                    logger.exception(f"FCSLoaderAnalysis: Failed to load {path}: {exc}")
                    results[str(path)] = {"error": str(exc)}

                completed += 1
                progress = int((completed / total_files) * 100)
                self.signals.analysis_progress.emit(progress)

        self.signals.analysis_progress.emit(100)
        logger.info(f"FCSLoaderAnalysis: Completed loading {completed} files")
        return {"loaded_data": results}
