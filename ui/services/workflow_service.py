"""Workflow service for managing serialization and hydration of flow experiments."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from analysis.state import FlowState


class WorkflowService:
    """Handles saving and loading of flow cytometry workflows."""

    def __init__(self, state: FlowState, data_loader_service, attachment_manager):
        self._state = state
        self._data_loader = data_loader_service
        self._attachment_manager = attachment_manager
        from biopro_sdk.plugin import get_logger

        self.logger = get_logger("flow.workflow_service", "flow_cytometry")

    def export_workflow(self, context=None) -> dict:
        """Serialize the current state to a workflow dictionary."""
        sample_paths = {}
        for sid, sample in self._state.data.experiment.samples.items():
            if sample.fcs_data and sample.fcs_data.file_path:
                sample_paths[sid] = str(sample.fcs_data.file_path)

        from analysis.experiment_io import ExperimentSerializer
        payload = {
            "experiment": ExperimentSerializer.serialize_experiment(self._state.data.experiment),
            "sample_paths": sample_paths,
            "compensation": (self._state.data.compensation.to_dict() if self._state.data.compensation else None),
            "view": {
                "current_sample_id": self._state.view.current_sample_id,
                "current_gate_id": self._state.view.current_gate_id,
                "active_x_param": self._state.view.active_x_param,
                "active_y_param": self._state.view.active_y_param,
                "active_transform_x": self._state.view.active_transform_x,
                "active_transform_y": self._state.view.active_transform_y,
                "active_plot_type": self._state.view.active_plot_type,
                "render_config": self._state.view.render_config.to_dict(),
                "auto_range_on_quality": self._state.view.auto_range_on_quality,
            },
        }

        if context is not None:
            attachments_meta = self._attachment_manager.serialize_attachments(self._state, context)
            if attachments_meta:
                payload["attachments"] = attachments_meta

        return payload

    def load_workflow(self, payload: dict, context=None) -> bool:
        """Restore the state from a workflow dictionary."""
        from analysis.compensation import CompensationMatrix
        from analysis.config import RenderConfig
        from analysis.experiment import Experiment

        if not payload:
            self.logger.warning("Empty workflow payload.")
            return False

        self.logger.info("Restoring FlowState from workflow payload...")
        try:
            actual_data = payload.get("payload", payload)

            # Compensation
            comp_data = actual_data.get("compensation")
            if comp_data:
                self._state.data.compensation = CompensationMatrix.from_dict(comp_data)
            else:
                self._state.data.compensation = None

            # View state
            view = actual_data.get("view", {})
            self._state.view.current_sample_id = view.get("current_sample_id")
            self._state.view.current_gate_id = view.get("current_gate_id")
            self._state.view.active_x_param = view.get("active_x_param", "FSC-A")
            self._state.view.active_y_param = view.get("active_y_param", "SSC-A")
            self._state.view.active_transform_x = view.get("active_transform_x", "linear")
            self._state.view.active_transform_y = view.get("active_transform_y", "linear")
            self._state.view.active_plot_type = view.get("active_plot_type", "pseudocolor")
            self._state.view.render_config = RenderConfig.from_dict(view.get("render_config", {}))
            self._state.view.auto_range_on_quality = view.get("auto_range_on_quality", True)

            # Experiment reconstruction
            exp_data = actual_data.get("experiment", {})
            if exp_data:
                from analysis.experiment_io import ExperimentSerializer
                self._state.data.experiment = ExperimentSerializer.deserialize_experiment(exp_data)
                sample_paths = actual_data.get("sample_paths", {})
                if sample_paths:
                    self.reload_fcs_data(sample_paths)

            if context is not None:
                # Legacy format compatibility
                if "umap_results_meta" in actual_data:
                    meta_dict = actual_data["umap_results_meta"]
                    if isinstance(meta_dict, dict) and any(isinstance(v, list) for v in meta_dict.values()):
                        results = self._attachment_manager.hydrate_umap_results(meta_dict, self._state, context)
                        if results:
                            self._state.data.umap_results = results
                            self.logger.info("Restored legacy UMAP binary attachments.")
                    else:
                        self.logger.info("Discarded old single-run UMAP format for compatibility.")

                # New generic format
                if "attachments" in actual_data:
                    self._attachment_manager.hydrate_attachments(actual_data["attachments"], self._state, context)
                    self.logger.info("Restored binary attachments.")

            self.logger.info("Workflow loaded successfully.")
            return True
        except Exception as exc:
            self._last_error = str(exc)
            self.logger.exception(f"Failed to load workflow: {exc}")
            return False

    def reload_fcs_data(self, sample_paths: dict[str, str]) -> None:
        """Reload FCS event data from disk for saved samples."""
        for sid, path_str in sample_paths.items():
            sample = self._state.data.experiment.samples.get(sid)
            if sample is None:
                continue

            path = Path(path_str)
            self._data_loader.reload_sample(sample, path, self._state.data.compensation)
