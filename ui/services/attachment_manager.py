"""Attachment Manager for handling binary data persistence.

Manages serialization and hydration of heavy binary payloads
(like UMAP numpy arrays) separate from the core workflow JSON logic.
"""

import tempfile
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from biopro_sdk.plugin import get_logger

logger = get_logger(__name__, "flow_cytometry")

class AttachmentManager:
    """Handles persistence of binary data attachments."""

    def __init__(self, axis_manager):
        self._axis_manager = axis_manager
        self.temp_dir = Path(tempfile.gettempdir())

    def serialize_attachments(self, state: Any, context: Any) -> dict:
        """Serialize all known binary attachments from the state."""
        meta = {}
        if getattr(state.data, "umap_results", None):
            meta["umap_results"] = self.serialize_umap_results(state.data.umap_results, context)
        # Register future attachment types here
        return meta

    def hydrate_attachments(self, meta_dict: dict, state: Any, context: Any) -> None:
        """Hydrate all binary attachments into the state."""
        if "umap_results" in meta_dict:
            res = self.hydrate_umap_results(meta_dict["umap_results"], state, context)
            if res:
                state.data.umap_results = res
        # Hydrate future attachment types here

    def serialize_umap_results(self, umap_results: dict, context: Any) -> dict:
        """Serialize UMAP embeddings and indices to binary attachments."""
        meta_dict = {}
        
        if not context:
            return meta_dict
            
        for key, runs in umap_results.items():
            meta_dict[key] = []
            for res in runs:
                run_uuid = uuid.uuid4().hex[:8]
                
                emb_path = self.temp_dir / f"umap_emb_{run_uuid}.npy"
                np.save(emb_path, res["embedding"])
                context.add_attachment(f"umap_emb_{run_uuid}", emb_path, "UMAP Coordinates")
                
                idx_path = self.temp_dir / f"umap_idx_{run_uuid}.npy"
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
                    cls_path = self.temp_dir / f"umap_cls_{run_uuid}.npy"
                    np.save(cls_path, res["clusters"])
                    context.add_attachment(f"umap_cls_{run_uuid}", cls_path, "UMAP Clusters")
                    meta["cls_key"] = f"umap_cls_{run_uuid}"
                    
                meta_dict[key].append(meta)
                
        return meta_dict

    def hydrate_umap_results(self, meta_dict: dict, state: Any, context: Any) -> dict:
        """Hydrate UMAP embeddings from binary attachments."""
        results = {}
        
        if not context or not isinstance(meta_dict, dict):
            return results
            
        for key, runs_meta in meta_dict.items():
            results[key] = []
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
                    
                    self._reconstruct_intensities(res, meta, state)
                    
                    if meta.get("has_clusters") and meta.get("cls_key"):
                        cls_path = context.get_path(meta["cls_key"])
                        if cls_path and cls_path.exists():
                            res["clusters"] = np.load(cls_path)
                            self._reconstruct_cluster_stats(res)
                            
                    results[key].append(res)
                    
        return results

    def _reconstruct_intensities(self, res: dict, meta: dict, state: Any):
        """Dynamically reconstruct transformed intensities."""
        sample_id = meta["sample_id"]
        sample = state.data.experiment.samples.get(sample_id)
        if sample and sample.fcs_data is not None:
            from analysis.transforms import biexponential_transform
            events_arr = sample.fcs_data.events.values if hasattr(sample.fcs_data.events, "values") else sample.fcs_data.events
            channels = list(sample.fcs_data.channels)
            
            sub_events = events_arr[res["indices"]]
            
            transformed_cols = []
            for ch in meta["channels"]:
                raw_ch = ch.split("(")[-1].strip(")") if "(" in ch else ch
                if raw_ch in channels:
                    col_idx = channels.index(raw_ch)
                    raw_vals = sub_events[:, col_idx].astype(np.float64)
                    scale = self._axis_manager.get_scale(raw_ch, sample_id)
                    
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
            logger.warning(f"Could not reconstruct intensities for sample {sample_id} because FCS data is missing.")
            res["intensities"] = np.zeros((len(res["embedding"]), len(meta["channels"])))

    def _reconstruct_cluster_stats(self, res: dict):
        """Reconstruct the cluster statistical properties."""
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
