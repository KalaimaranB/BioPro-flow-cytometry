"""Abstract base for all comparison plot renderers.

ISP: narrow interface — only render() is required.
DIP: ComparisonsViewer depends on this, not on concrete renderer classes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from matplotlib.figure import Figure


class IPlotRenderer(ABC):
    """Single-responsibility: produce a matplotlib Figure from data kwargs.

    Subclasses must not import Qt, BioPro theme, or FlowState — all
    necessary values are passed in as plain Python primitives via kwargs.
    This makes renderers independently testable without a Qt application.
    """

    @abstractmethod
    def render(self, **kwargs) -> Figure:
        """Render the plot and return a matplotlib Figure.

        The caller (ComparisonsWorker) is responsible for running this
        on a background thread.  Implementations must be thread-safe.
        """
