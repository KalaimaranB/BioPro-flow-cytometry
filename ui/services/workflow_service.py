"""Workflow service for managing serialization and hydration of flow experiments.
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from ...analysis.state import FlowState

class WorkflowService:
    """Handles saving and loading of flow cytometry workflows."""
    
    def __init__(self, state: FlowState):
        self._state = state
        from biopro_sdk.plugin import get_logger
        self.logger = get_logger("flow.workflow_service", "flow_cytometry")

    def export_workflow(self, context=None) -> dict:
        """Serialize the current state to a workflow dictionary."""
        payload = self._state.to_workflow_dict()
        
        # Binary attachments for heavy arrays
        if context is not None and self._state.data.umap_results:
            import tempfile
            import numpy as np
            import uuid
            
            res = self._state.data.umap_results
            temp_dir = Path(tempfile.gettempdir())
            
            payload["umap_results_meta"] = {}
            for key, runs in self._state.data.umap_results.items():
                payload["umap_results_meta"][key] = []
                for res in runs:
                    run_uuid = uuid.uuid4().hex[:8]
                    
                    emb_path = temp_dir / f"umap_emb_{run_uuid}.npy"
                    np.save(emb_path, res["embedding"])
                    context.add_attachment(f"umap_emb_{run_uuid}", emb_path, "UMAP Coordinates")
                    
                    idx_path = temp_dir / f"umap_idx_{run_uuid}.npy"
                    np.save(idx_path, res["indices"])
                    context.add_attachment(f"umap_idx_{run_uuid}", idx_path, "UMAP Indices")
                    
                    meta = {
                        "sample_id": res["sample_id"],
                        "node_id": res["node_id"],
                        "channels": res["channels"],
                        "has_labels": "labels" in res,
                        "n_neighbors": res.get("n_neighbors", 15),
                        "min_dist": res.get("min_dist", 0.1),
                        "emb_key": f"umap_emb_{run_uuid}",
                        "idx_key": f"umap_idx_{run_uuid}"
                    }
                    
                    if "labels" in res:
                        lbl_path = temp_dir / f"umap_lbl_{run_uuid}.npy"
                        np.save(lbl_path, res["labels"])
                        context.add_attachment(f"umap_lbl_{run_uuid}", lbl_path, "UMAP Clusters")
                        meta["lbl_key"] = f"umap_lbl_{run_uuid}"
                        
                    payload["umap_results_meta"][key].append(meta)

        return payload

    def load_workflow(self, payload: dict, context=None) -> bool:
        """Restore the state from a workflow dictionary."""
        if not payload:
            self.logger.warning("Empty workflow payload.")
            return False

        self.logger.info("Restoring FlowState from workflow payload...")
        try:
            # Unwrap if the full BioPro envelope (metadata + payload) is passed
            actual_data = payload.get("payload", payload)
            
            # Defer to state for the actual data restoration
            self._state.from_workflow_dict(actual_data)
            
            # Restore heavy arrays from binary attachments if present
            if context is not None and "umap_results_meta" in actual_data:
                import numpy as np
                self._state.data.umap_results = {}
                meta_dict = actual_data["umap_results_meta"]
                
                if isinstance(meta_dict, dict) and any(isinstance(v, list) for v in meta_dict.values()):
                    for key, runs_meta in meta_dict.items():
                        self._state.data.umap_results[key] = []
                        for meta in runs_meta:
                            emb_path = context.get_path(meta.get("emb_key"))
                            idx_path = context.get_path(meta.get("idx_key"))
                            
                            if emb_path and emb_path.exists() and idx_path and idx_path.exists():
                                res = {
                                    "sample_id": meta["sample_id"],
                                    "node_id": meta["node_id"],
                                    "channels": meta["channels"],
                                    "n_neighbors": meta.get("n_neighbors", 15),
                                    "min_dist": meta.get("min_dist", 0.1),
                                    "embedding": np.load(emb_path),
                                    "indices": np.load(idx_path)
                                }
                                
                                if meta.get("has_labels") and meta.get("lbl_key"):
                                    lbl_path = context.get_path(meta["lbl_key"])
                                    if lbl_path and lbl_path.exists():
                                        res["labels"] = np.load(lbl_path)
                                        
                                self._state.data.umap_results[key].append(res)
                    self.logger.info("Restored UMAP binary attachments.")
                else:
                    self.logger.info("Discarded old single-run UMAP format for compatibility.")
            
            self.logger.info("Workflow loaded successfully.")
            return True
        except Exception as exc:
            self.logger.exception(f"Failed to load workflow: {exc}")
            return False

    def reload_fcs_data(self, sample_paths: dict[str, str]) -> None:
        """Reload FCS event data from disk for saved samples.
        
        This logic was moved from FlowState to satisfy SRP.
        """
        from ...analysis.fcs_io import load_fcs
        from ...analysis.compensation import apply_compensation

        for sid, path_str in sample_paths.items():
            sample = self._state.experiment.samples.get(sid)
            if sample is None:
                continue

            path = Path(path_str)
            if not path.exists():
                self.logger.warning(
                    f"FCS file no longer exists: {path} (sample: {sample.display_name})"
                )
                continue

            try:
                fcs_data = load_fcs(path)
                
                # Re-apply compensation if it was active when saved
                if sample.is_compensated and self._state.compensation:
                    if not fcs_data.is_compensated:
                        fcs_data.events = apply_compensation(fcs_data, self._state.compensation)
                        fcs_data.is_compensated = True
                        self.logger.info(f"Re-applied BioPro compensation matrix to reloaded sample '{sample.display_name}'")
                
                sample.fcs_data = fcs_data
                self.logger.info(
                    f"Reloaded FCS data for '{sample.display_name}': {fcs_data.num_events} events"
                )
            except Exception as exc:
                self.logger.warning(
                    f"Failed to reload FCS for '{sample.display_name}': {exc}"
                )
