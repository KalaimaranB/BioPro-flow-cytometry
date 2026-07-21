"""UMAP Analysis — SDK-aligned background worker for UMAP dimensionality reduction."""

from __future__ import annotations

from typing import Any

import numpy as np
from biopro_sdk.plugin import AnalysisBase, get_logger

from .fcs_io import get_channel_marker_label, get_fluorescence_channels
from .transforms import biexponential_transform

logger = get_logger(__name__, "flow_cytometry")


class UmapAnalysis(AnalysisBase):
    """Background analyzer for running UMAP dimensionality reduction."""

    def __init__(self, plugin_id: str = "flow_cytometry"):
        super().__init__(plugin_id)
        self.target_sample_id: str = ""
        self.target_node_id: str | None = None  # None = All Events
        self.name: str = ""
        self.percentage: float = 10.0
        self.n_neighbors: int = 15
        self.min_dist: float = 0.1
        self.n_events: int = 10000
        self.metric: str = "euclidean"
        self.random_seed: int = 42
        self.run_hdbscan: bool = False
        self.hdbscan_space: str = "high_dim"
        self.min_cluster_size: int = 100
        self.channels: list[str] = []

    def validate(self, state: Any) -> tuple[bool, str]:
        """Verify sample has FCS data loaded."""
        sample_id = getattr(self, "target_sample_id", "")
        if not sample_id:
            sample_id = getattr(state, "current_sample_id", None)

        if not sample_id:
            return False, "No sample selected."

        sample = state.data.experiment.samples.get(sample_id)
        if not sample:
            return False, f"Sample '{sample_id}' not found."

        if sample.fcs_data is None or sample.fcs_data.events is None:
            return False, f"Sample '{sample.display_name}' has no loaded FCS data."

        if len(sample.fcs_data.events) < 50:
            return (
                False,
                f"Sample '{sample.display_name}' has too few events ({len(sample.fcs_data.events)}) for UMAP analysis.",
            )

        return True, ""

    def run(self, state: Any) -> dict[str, Any]:
        """Transforms FCS data with Logicle, subsamples, runs UMAP."""
        sample_id = getattr(self, "target_sample_id", "")
        if not sample_id:
            sample_id = state.view.current_sample_id

        logger.info(f"UmapAnalysis: Starting run for sample {sample_id}")

        sample = state.data.experiment.samples[sample_id]
        fcs_data = sample.fcs_data

        if fcs_data is None:
            logger.error("No FCS data found for UMAP analysis.")
            return {"error": "No FCS data loaded for this sample."}

        # 1. Get fluorescence channels
        fluo_channels = get_fluorescence_channels(fcs_data)
        if not fluo_channels:
            logger.error("No fluorescence channels found for UMAP analysis.")
            return {"error": "No fluorescence channels found in this sample."}

        selected_channels = getattr(self, "channels", None)
        if selected_channels:
            fluo_channels = [ch for ch in fluo_channels if ch in selected_channels]
            if not fluo_channels:
                return {
                    "error": "None of the selected channels are available in this sample."
                }

        logger.info(
            f"UmapAnalysis: Analyzing {len(fluo_channels)} fluorescence channels"
        )

        # 2. Extract events DataFrame — apply gate filter if requested
        events_df = fcs_data.events

        if self.target_node_id and sample.gate_tree is not None:
            gate_node = sample.gate_tree.find_node_by_id(self.target_node_id)
            if gate_node is not None:
                filtered_df = gate_node.apply_hierarchy(events_df)
                n_in_gate = len(filtered_df)
                logger.info(
                    f"UmapAnalysis: Gate '{gate_node.name}' contains "
                    f"{n_in_gate}/{len(events_df)} events"
                )
                if n_in_gate < 50:
                    return {
                        "error": f"Gate '{gate_node.name}' contains too few events ({n_in_gate}) for UMAP."
                    }
                events_df = filtered_df
            else:
                logger.warning(
                    f"UmapAnalysis: node_id '{self.target_node_id}' not found — using all events"
                )

        num_total_events = len(events_df)

        # 3. Subsample to self.n_events
        n_events = min(self.n_events, num_total_events)
        if n_events <= 0:
            return {"error": "No events available for analysis."}

        self.signals.analysis_progress.emit(5)

        # Determinstic subsampling
        np.random.seed(self.random_seed)
        subsample_idx = np.random.choice(num_total_events, size=n_events, replace=False)
        subsample_df = events_df.iloc[subsample_idx].copy()

        self.signals.analysis_progress.emit(10)
        if self.is_cancelled():
            return {"error": "Task cancelled."}

        # 4. Transform channels with Logicle
        transformed_columns = []
        for ch in fluo_channels:
            if self.is_cancelled():
                return {"error": "Task cancelled."}

            raw_vals = subsample_df[ch].values.astype(np.float64)
            scale = state.axis_manager.get_scale(ch, sample_id)

            top = getattr(scale, "logicle_t", 262144.0)
            width = getattr(scale, "logicle_w", 1.0)
            positive = getattr(scale, "logicle_m", 4.5)
            negative = getattr(scale, "logicle_a", 0.0)

            trans_vals = biexponential_transform(
                raw_vals, top=top, width=width, positive=positive, negative=negative
            )
            transformed_columns.append(trans_vals)

        X = np.column_stack(transformed_columns)

        self.signals.analysis_progress.emit(20)
        if self.is_cancelled():
            return {"error": "Task cancelled."}

        # 5. Fit UMAP
        logger.info(
            f"UmapAnalysis: Fitting UMAP on shape {X.shape} with n_neighbors={self.n_neighbors}, min_dist={self.min_dist}"
        )
        self.signals.analysis_progress.emit(30)

        try:
            import os
            import subprocess
            import sys
            import tempfile
            import time

            with tempfile.TemporaryDirectory() as tmpdir:
                in_path = os.path.join(tmpdir, "X.npy")
                out_path = os.path.join(tmpdir, "res.npy")
                np.save(in_path, X)

                script = f"""
import numpy as np
import umap
X = np.load({repr(in_path)})
reducer = umap.UMAP(
    n_neighbors={self.n_neighbors},
    min_dist={self.min_dist},
    metric={repr(self.metric)},
    random_state={self.random_seed},
    init='pca',
    low_memory=False,
    verbose=False
)
res = reducer.fit_transform(X)
np.save({repr(out_path)}, res)
"""

                clusters_path = os.path.join(tmpdir, "clusters.npy")
                if getattr(self, "run_hdbscan", False):
                    script += f"""
import hdbscan
if {repr(getattr(self, "hdbscan_space", "high_dim"))} == "high_dim":
    cluster_data = X
else:
    cluster_data = res

clusterer = hdbscan.HDBSCAN(min_cluster_size={getattr(self, "min_cluster_size", 100)})
clusters = clusterer.fit_predict(cluster_data)
np.save({repr(clusters_path)}, clusters)
"""
                sp_kwargs: dict[str, __import__("typing").Any] = {}
                if sys.platform == "win32":
                    import subprocess

                    sp_kwargs["creationflags"] = getattr(
                        subprocess, "CREATE_NO_WINDOW", 0x08000000
                    )

                proc = subprocess.Popen([sys.executable, "-c", script], **sp_kwargs)

                # Check for cancellation while waiting for the subprocess
                while proc.poll() is None:
                    if self.is_cancelled():
                        proc.terminate()
                        return {"error": "Task cancelled."}
                    time.sleep(0.5)

                if proc.returncode != 0:
                    raise RuntimeError(
                        f"UMAP subprocess failed with exit code {proc.returncode}"
                    )

                embedding = np.load(out_path)

                clusters = None
                if getattr(self, "run_hdbscan", False) and os.path.exists(
                    clusters_path
                ):
                    clusters = np.load(clusters_path)

        except Exception as e:
            logger.exception(f"UmapAnalysis: UMAP reduction failed: {e}")
            self.signals.analysis_error.emit(f"UMAP failed: {e}")
            return {"error": f"UMAP calculation failed: {e}"}

        self.signals.analysis_progress.emit(90)
        if self.is_cancelled():
            return {"error": "Task cancelled."}

        # Display names for the fluorescence channels
        channel_labels = [
            get_channel_marker_label(fcs_data, ch) for ch in fluo_channels
        ]

        logger.info("UmapAnalysis: Completed run successfully")
        self.signals.analysis_progress.emit(100)

        result_dict = {
            "name": getattr(self, "name", ""),
            "percentage": getattr(self, "percentage", 10.0),
            "n_neighbors": self.n_neighbors,
            "min_dist": self.min_dist,
            "metric": self.metric,
            "random_seed": self.random_seed,
            "run_hdbscan": getattr(self, "run_hdbscan", False),
            "hdbscan_space": getattr(self, "hdbscan_space", "high_dim"),
            "min_cluster_size": getattr(self, "min_cluster_size", 100),
            "channels": fluo_channels,
            "channel_labels": channel_labels,
            "embedding": embedding if embedding is not None else None,
            "intensities": X if X is not None else None,
            "sample_id": sample_id,
            "node_id": self.target_node_id,
            "n_events": n_events,
            "indices": np.array(subsample_df.index),
        }
        if clusters is not None:
            import pandas as pd

            result_dict["clusters"] = clusters

            # Create a DataFrame for the raw expression data and the cluster labels
            df = pd.DataFrame(X, columns=channel_labels)
            df["Cluster_ID"] = clusters

            # Compute Cluster Statistics
            counts = df["Cluster_ID"].value_counts().sort_index()
            percentages = (counts / len(df)) * 100

            stats_df = pd.DataFrame(
                {
                    "Cluster ID": counts.index,
                    "Cell Count": counts.values,
                    "% of Total": percentages.values,
                }
            )
            result_dict["cluster_stats"] = stats_df.to_dict(orient="split")

            # Compute Marker Heatmap (Median intensity per channel per cluster)
            heatmap_df = df.groupby("Cluster_ID").median()
            result_dict["marker_heatmap"] = heatmap_df.to_dict(orient="split")

        return result_dict
