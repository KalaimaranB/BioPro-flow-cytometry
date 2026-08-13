"""Compatibility layer for Matplotlib Qt backends."""

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: F401

    class LockedFigureCanvas(FigureCanvasQTAgg):
        """FigureCanvasQTAgg that serializes all Agg rasterization behind MPL_LOCK.

        Matplotlib's Agg/FreeType backend is not thread-safe: concurrent draws
        from different Figure objects on different threads can corrupt shared
        C-level state (glyph cache, font transforms) and crash with garbage
        arguments deep in matplotlib.ft2font. RenderTask (background QThreadPool
        worker) and FlowCanvas already serialize their drawing behind the shared
        ``MPL_LOCK`` — any *other* widget with its own FigureCanvasQTAgg must too,
        since they all share the same process-wide matplotlib backend state.
        Use this class in place of FigureCanvasQTAgg for any standalone plot
        widget instead of duplicating the lock dance by hand.
        """

        def draw(self) -> None:
            from ._mpl_lock import MPL_LOCK

            if not MPL_LOCK.acquire(blocking=False):
                from PyQt6.QtCore import QTimer

                QTimer.singleShot(50, self._retry_draw)
                return
            try:
                super().draw()
            finally:
                MPL_LOCK.release()

        def _retry_draw(self) -> None:
            # The canvas can be replaced/deleteLater()'d (e.g. the user
            # generated a new plot) while this retry was still queued —
            # touching a destroyed C++ widget here would crash natively
            # rather than raise a catchable RuntimeError, since this runs
            # from a QTimer callback rather than a normal Python call.
            from PyQt6 import sip

            if sip.isdeleted(self):
                return
            self.draw()

        def paintEvent(self, event) -> None:  # noqa: N802
            from ._mpl_lock import MPL_LOCK

            if not MPL_LOCK.acquire(blocking=False):
                from PyQt6.QtCore import QTimer

                QTimer.singleShot(50, self._retry_update)
                return
            try:
                super().paintEvent(event)
            finally:
                MPL_LOCK.release()

        def _retry_update(self) -> None:
            from PyQt6 import sip

            if sip.isdeleted(self):
                return
            self.update()

except ImportError:
    pass
