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
                        "has_clusters": "clusters" in res,
                        "n_neighbors": res.get("n_neighbors", 15),
                        "min_dist": res.get("min_dist", 0.1),
                        "emb_key": f"umap_emb_{run_uuid}",
                        "idx_key": f"umap_idx_{run_uuid}"
                    }
                    
                    if "clusters" in res:
                        cls_path = temp_dir / f"umap_cls_{run_uuid}.npy"
                        np.save(cls_path, res["clusters"])
                        context.add_attachment(f"umap_cls_{run_uuid}", cls_path, "UMAP Clusters")
                        meta["cls_key"] = f"umap_cls_{run_uuid}"
                        
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
                                
                                # Dynamically reconstruct intensities
                                sample_id = meta["sample_id"]
                                sample = self._state.experiment.samples.get(sample_id)
                                if sample and sample.fcs_data is not None:
                                    from ...analysis.transforms import biexponential_transform
                                    events_arr = sample.fcs_data.events.values if hasattr(sample.fcs_data.events, "values") else sample.fcs_data.events
                                    channels = list(sample.fcs_data.channels)
                                    
                                    sub_events = events_arr[res["indices"]]
                                    
                                    transformed_cols = []
                                    for ch in meta["channels"]:
                                        raw_ch = ch.split("(")[-1].strip(")") if "(" in ch else ch
                                        if raw_ch in channels:
                                            col_idx = channels.index(raw_ch)
                                            raw_vals = sub_events[:, col_idx].astype(np.float64)
                                            scale = self._state.axis_manager.get_scale(raw_ch, sample_id)
                                            
                                            top = getattr(scale, "logicle_t", 262144.0)
                                            width = getattr(scale, "logicle_w", 1.0)
                                            positive = getattr(scale, "logicle_m", 4.5)
                                            negative = getattr(scale, "logicle_a", 0.0)
                                            
                                            trans_vals = biexponential_transform(
                                                raw_vals, top=top, width=width, positive=positive, negative=negative
                                            )
                                            transformed_cols.append(trans_vals)
                                        else:
                                            transformed_cols.append(np.zeros(len(sub_events)))
                                            
                                    res["intensities"] = np.column_stack(transformed_cols)
                                else:
                                    self.logger.warning(f"Could not reconstruct intensities for sample {sample_id} because FCS data is missing.")
                                    res["intensities"] = np.zeros((len(res["embedding"]), len(meta["channels"])))
                                    
                                if meta.get("has_clusters") and meta.get("cls_key"):
                                    cls_path = context.get_path(meta["cls_key"])
                                    if cls_path and cls_path.exists():
                                        res["clusters"] = np.load(cls_path)
                                        
                                        import pandas as pd
                                        df_cluster = pd.DataFrame(res["intensities"], columns=res["channels"])
                                        df_cluster['Cluster_ID'] = res["clusters"]
                                        
                                        counts = df_cluster['Cluster_ID'].value_counts().sort_index()
                                        percentages = (counts / len(df_cluster)) * 100
                                        res["cluster_stats"] = pd.DataFrame({
                                            'Cluster ID': counts.index,
                                            'Cell Count': counts.values,
                                            '% of Total': percentages.values
                                        })
                                        res["marker_heatmap"] = df_cluster.groupby('Cluster_ID').median()
                                        
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
