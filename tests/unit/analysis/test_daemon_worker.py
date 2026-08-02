"""Unit tests for daemon_worker.py in BioPro-flow-cytometry."""

from pathlib import Path

import numpy as np
import pytest
from biopro_plugins.flow_cytometry.analysis.daemon_worker import (
    _decode_array,
    _encode_array,
    handle_run_umap,
)
from biopro_sdk.plugin import PluginDaemon


def test_array_serialization():
    arr = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    b64 = _encode_array(arr)
    decoded = _decode_array(b64)
    np.testing.assert_array_equal(arr, decoded)


def test_handle_run_umap():
    np.random.seed(42)
    X = np.random.randn(100, 5).astype(np.float64)
    X_b64 = _encode_array(X)

    kwargs = {
        "X_b64": X_b64,
        "params": {
            "n_neighbors": 5,
            "min_dist": 0.1,
            "random_seed": 42,
        },
    }
    res = handle_run_umap(kwargs)
    assert res.get("status") == "ok"
    assert "embedding_b64" in res

    embedding = _decode_array(res["embedding_b64"])
    assert embedding.shape == (100, 2)


def test_daemon_worker_end_to_end(tmp_path):
    daemon_script = (
        Path(__file__).resolve().parents[3]
        / "src"
        / "biopro_plugins"
        / "flow_cytometry"
        / "analysis"
        / "daemon_worker.py"
    )
    if not daemon_script.exists():
        pytest.skip(f"daemon_worker.py not found at {daemon_script}")

    daemon = PluginDaemon.get_instance(
        "flow_cytometry_test", daemon_script_path=daemon_script
    )

    # Ping test
    res = daemon.call("ping", {})
    assert res == {"status": "pong"}

    # UMAP test
    X = np.random.randn(50, 4).astype(np.float64)
    X_b64 = _encode_array(X)
    res_umap = daemon.call(
        "run_umap",
        {
            "X_b64": X_b64,
            "params": {"n_neighbors": 5, "min_dist": 0.1, "random_seed": 42},
        },
    )
    assert res_umap.get("status") == "ok"
    assert "embedding_b64" in res_umap

    PluginDaemon.stop_instance("flow_cytometry_test")
