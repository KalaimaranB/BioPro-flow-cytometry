"""Shared threading lock for matplotlib rendering.

Matplotlib's Agg C backend shares internal state and is NOT thread-safe on
macOS ARM (Apple Silicon).  Concurrent figure/axes operations from any
combination of threads (QThreadPool render tasks *or* the Qt main-thread
DataLayerRenderer) corrupt that shared state → SIGBUS.

Both RenderTask and DataLayerRenderer must acquire this lock around all
matplotlib drawing operations. Data preparation (gating, transforms) is
unaffected and stays fully parallel.

This is an RLock, not a plain Lock, on purpose: every canvas that uses this
lock (FlowCanvas, LockedFigureCanvas) acquires it around both `paintEvent()`
and `draw()`, but matplotlib's own Qt backend has `paintEvent()` call
`self.draw()` internally (via `_draw_idle()`) on a canvas that hasn't been
drawn yet — i.e. the SAME thread re-enters this lock while it already holds
it. With a plain `Lock`, that inner `acquire(blocking=False)` correctly
returns `False` instead of deadlocking, but `draw()` then bails out and
defers to a `QTimer.singleShot` retry — silently dropping the first real
paint. Under heavy background lock contention (e.g. many concurrent
GroupPreview thumbnail RenderTasks) that retry can get starved for a long
time, which is exactly the "Generate Plot completed but nothing appears
until Export" bug: the figure was never actually drawn onto the canvas, only
rendered for `savefig()` (a separate, canvas-independent code path). An RLock
lets the same thread re-enter freely (only a different thread ever blocks),
so the inner `draw()` call succeeds immediately instead of deferring.
"""

import threading

MPL_LOCK = threading.RLock()
