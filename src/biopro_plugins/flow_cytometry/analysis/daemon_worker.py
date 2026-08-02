"""Flow Cytometry Plugin Daemon Worker.

Long-lived worker process running in the plugin environment. Imports heavy dependencies
(FlowKit, Numba, UMAP, HDBSCAN, fcsparser) once on startup and processes length-prefixed
msgpack IPC requests over stdin/stdout.
"""

from __future__ import annotations

import base64
import io
import os
import struct
import sys
import traceback
from typing import Any

# Pre-set thread environment variables before heavy C extension imports
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import msgpack  # noqa: E402
import numpy as np  # noqa: E402

# Optional pre-warm imports
try:
    import flowkit
except ImportError:
    flowkit = None

try:
    import fcsparser
except ImportError:
    fcsparser = None

try:
    import umap
except ImportError:
    umap = None

try:
    import hdbscan
except ImportError:
    hdbscan = None


def write_frame(data: dict[str, Any]) -> None:
    """Write length-prefixed msgpack frame to stdout."""
    payload = msgpack.packb(data, use_bin_type=True)
    header = struct.pack(">I", len(payload))
    sys.stdout.buffer.write(header + payload)
    sys.stdout.buffer.flush()


def read_frame() -> dict[str, Any] | None:
    """Read length-prefixed msgpack frame from stdin."""
    header = sys.stdin.buffer.read(4)
    if not header or len(header) < 4:  # noqa: PLR2004
        return None
    length = struct.unpack(">I", header)[0]
    payload = sys.stdin.buffer.read(length)
    if not payload or len(payload) < length:
        return None
    return msgpack.unpackb(payload, raw=False)


def _encode_array(arr: np.ndarray) -> str:
    """Encode numpy array into base64 string using np.save."""
    buf = io.BytesIO()
    np.save(buf, arr, allow_pickle=False)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _decode_array(b64_str: str) -> np.ndarray:
    """Decode base64 string back into numpy array."""
    raw = base64.b64decode(b64_str.encode("ascii"))
    buf = io.BytesIO(raw)
    return np.load(buf, allow_pickle=False)


def handle_load_fcs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Load FCS file using pre-imported FlowKit or fcsparser."""
    path_str = kwargs.get("path", "")
    if not path_str or not os.path.exists(path_str):
        return {"error": f"FCS file not found: {path_str}"}

    # 1. Try FlowKit first
    if flowkit is not None:
        try:
            sample = flowkit.Sample(path_str)
            raw_events = sample.as_dataframe(source="raw")
            channels = [
                ch[0] if isinstance(ch, tuple) else ch for ch in raw_events.columns
            ]

            markers = []
            for i, ch in enumerate(channels):
                try:
                    # In FlowKit MultiIndex, the original channel name might be what we need for get_channel_marker
                    raw_events.columns[i] if hasattr(raw_events, "columns") else ch
                    pns = sample.get_channel_marker(ch) or ""
                except Exception:
                    pns = ""
                markers.append(pns)

            # Metadata extraction
            metadata = {}
            for k, v in getattr(sample, "meta", {}).items():
                if isinstance(v, (str, int, float, bool)):
                    metadata[str(k)] = str(v)

            events_arr = raw_events.values.astype(np.float64)

            return {
                "status": "ok",
                "channels": channels,
                "markers": markers,
                "metadata": metadata,
                "events_b64": _encode_array(events_arr),
                "loader": "flowkit",
            }
        except Exception as fk_err:
            sys.stderr.write(f"FlowKit worker load failed for {path_str}: {fk_err}\n")

    # 2. Fallback to fcsparser
    if fcsparser is not None:
        try:
            meta, data = fcsparser.parse(
                path_str, reformat_meta=True, channel_naming="$PnN"
            )
            channels = list(data.columns)
            markers = [
                str(meta.get(f"$P{i}S", "")) for i in range(1, len(channels) + 1)
            ]
            metadata = {
                str(k).lstrip("$"): str(v)
                for k, v in meta.items()
                if isinstance(v, (str, int, float, bool))
            }
            events_arr = data.values.astype(np.float64)

            return {
                "status": "ok",
                "channels": channels,
                "markers": markers,
                "metadata": metadata,
                "events_b64": _encode_array(events_arr),
                "loader": "fcsparser",
            }
        except Exception as fcs_err:
            return {"error": f"fcsparser load failed for {path_str}: {fcs_err}"}

    return {"error": "Neither FlowKit nor fcsparser is available in worker process."}


def handle_run_umap(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Fit UMAP and optional HDBSCAN clustering."""
    if umap is None:
        return {"error": "umap-learn is not installed in worker process."}

    X_b64 = kwargs.get("X_b64", "")
    params = kwargs.get("params", {})

    if not X_b64:
        return {"error": "No input matrix X_b64 provided."}

    X = _decode_array(X_b64)

    n_neighbors = params.get("n_neighbors", 15)
    min_dist = params.get("min_dist", 0.1)
    metric = params.get("metric", "euclidean")
    random_seed = params.get("random_seed", 42)

    reducer = umap.UMAP(
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        metric=metric,
        random_state=random_seed,
        init="pca",
        low_memory=False,
        verbose=False,
    )
    embedding = reducer.fit_transform(X)

    clusters_b64 = None
    if params.get("run_hdbscan", False):
        if hdbscan is None:
            return {"error": "hdbscan is not installed in worker process."}

        hdbscan_space = params.get("hdbscan_space", "high_dim")
        cluster_data = X if hdbscan_space == "high_dim" else embedding
        min_cluster_size = params.get("min_cluster_size", 100)

        clusterer = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size)
        clusters = clusterer.fit_predict(cluster_data)
        clusters_b64 = _encode_array(clusters)

    res = {
        "status": "ok",
        "embedding_b64": _encode_array(embedding),
    }
    if clusters_b64:
        res["clusters_b64"] = clusters_b64

    return res


def main() -> None:
    """Worker daemon main loop."""
    sys.stderr.write("BIOPRO_WORKER_READY\n")
    write_frame({"status": "ready"})

    while True:
        try:
            frame = read_frame()
            if not frame:
                break

            method = frame.get("method", "")
            kwargs = frame.get("kwargs", {})

            if method == "exit":
                break
            elif method == "ping":
                write_frame({"status": "pong"})
            elif method == "load_fcs":
                res = handle_load_fcs(kwargs)
                write_frame(res)
            elif method == "run_umap":
                res = handle_run_umap(kwargs)
                write_frame(res)
            elif method == "cancel":
                write_frame({"status": "cancelled"})
            else:
                write_frame({"error": f"Unknown method '{method}'"})

        except Exception as exc:
            err_msg = f"Daemon worker exception: {exc}\n{traceback.format_exc()}"
            sys.stderr.write(err_msg + "\n")
            write_frame({"error": str(exc)})


if __name__ == "__main__":
    main()
