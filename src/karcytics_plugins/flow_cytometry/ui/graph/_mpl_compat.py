"""Compatibility layer for Matplotlib Qt backends."""

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: F401

    class LockedFigureCanvas(FigureCanvasQTAgg):
        """FigureCanvasQTAgg that serializes all Agg rasterization behind MPL_RASTER_LOCK.

        Matplotlib's Agg/FreeType backend is not thread-safe: concurrent draws
        from different Figure objects on different threads can corrupt shared
        C-level state (glyph cache, font transforms) and crash with garbage
        arguments deep in matplotlib.ft2font. RenderTask (background QThreadPool
        worker) and FlowCanvas already serialize their drawing behind the shared
        ``MPL_RASTER_LOCK`` — any *other* widget with its own FigureCanvasQTAgg
        must too, since they all share the same process-wide matplotlib backend
        state. Use this class in place of FigureCanvasQTAgg for any standalone
        plot widget instead of duplicating the lock dance by hand.

        The acquire/retry/release dance itself is `RasterLock.try_run()` —
        the same primitive `rendering.LayeredMatplotlibCanvas`'s own
        `paintEvent()`/`draw()` overrides use, generalized from this exact
        pattern.
        """

        def draw(self) -> None:
            from karcytics_sdk.plugin.rendering.lock import MPL_RASTER_LOCK

            MPL_RASTER_LOCK.try_run(super().draw, self._retry_draw)

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
            from karcytics_sdk.plugin.rendering.lock import MPL_RASTER_LOCK

            MPL_RASTER_LOCK.try_run(
                lambda: super(LockedFigureCanvas, self).paintEvent(event), self._retry_update
            )

        def _retry_update(self) -> None:
            from PyQt6 import sip

            if sip.isdeleted(self):
                return
            self.update()

except ImportError:
    pass
