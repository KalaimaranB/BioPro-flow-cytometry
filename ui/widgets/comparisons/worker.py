"""ComparisonsWorker — runs one renderer off the main thread.

SRP: only responsibility is running renderer.render(**kwargs) on a QThread
and emitting the result Figure or an error string.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from .renderers.base import IPlotRenderer


class ComparisonsWorker(QThread):
    """Background thread for comparison plot rendering.

    DIP: depends on IPlotRenderer, not on any concrete renderer class.
    The caller injects the concrete renderer instance at construction time.
    """

    finished_ok = pyqtSignal(object)  # emits matplotlib.figure.Figure
    finished_err = pyqtSignal(str)  # emits error message string

    def __init__(self, renderer: IPlotRenderer, kwargs: dict) -> None:
        super().__init__()
        self._renderer = renderer
        self._kwargs = kwargs

    def run(self) -> None:
        """SRP: call renderer.render() and emit result or error."""
        try:
            fig = self._renderer.render(**self._kwargs)
            self.finished_ok.emit(fig)
        except Exception as exc:
            self.finished_err.emit(str(exc))
