"""Numba JIT warm-up utility for the Flow Cytometry plugin.

Running a tiny UMAP on dummy data pre-compiles all numba kernels so that the
real UMAP analysis starts with a warm JIT cache and doesn't freeze the UI.
"""

from __future__ import annotations
import threading
import os

_warmup_done = False
_warmup_lock = threading.Lock()


def warmup_numba_jit() -> None:
    """
    Pre-compile numba-compiled UMAP kernels on a background thread.

    Call this once at plugin load time (before the user clicks Run UMAP).
    Subsequent UMAP calls will reuse the compiled code and won't JIT stall.
    """
    global _warmup_done
    with _warmup_lock:
        if _warmup_done:
            return
        _warmup_done = True

    t = threading.Thread(target=_do_warmup, name="numba-jit-warmup", daemon=True)
    t.start()


def _do_warmup() -> None:
    """Runs a tiny UMAP on random dummy data to trigger JIT compilation."""
    try:
        import numpy as np
        import umap as umap_lib

        # 80 points, 10 epochs — enough to compile all internal numba kernels,
        # fast enough to finish in ~3-5s even on a slow machine.
        rng = np.random.default_rng(0)
        X = rng.standard_normal((80, 6)).astype(np.float32)

        umap_lib.UMAP(
            n_neighbors=5,
            min_dist=0.1,
            n_epochs=10,
            random_state=0,
            low_memory=False,
            verbose=False,
        ).fit_transform(X)

    except Exception:
        pass  # Warm-up failure is non-fatal — the real run will JIT on demand
