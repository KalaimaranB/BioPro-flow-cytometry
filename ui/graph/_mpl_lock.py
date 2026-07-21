"""Shared threading lock for matplotlib rendering.

Matplotlib's Agg C backend shares internal state and is NOT thread-safe on
macOS ARM (Apple Silicon).  Concurrent figure/axes operations from any
combination of threads (QThreadPool render tasks *or* the Qt main-thread
DataLayerRenderer) corrupt that shared state → SIGBUS.

Both RenderTask and DataLayerRenderer must acquire this lock around all
matplotlib drawing operations. Data preparation (gating, transforms) is
unaffected and stays fully parallel.
"""

import threading

MPL_LOCK = threading.Lock()
