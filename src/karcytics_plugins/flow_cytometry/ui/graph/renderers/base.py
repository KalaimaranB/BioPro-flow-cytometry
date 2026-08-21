from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np
    from matplotlib.axes import Axes


class DisplayStrategy(ABC):
    """Abstract base class for all data rendering strategies.

    Split into a ``compute()`` step (pure numpy/scipy, safe to run off the Qt
    main thread) and a ``draw()`` step (matplotlib Axes calls, which must run
    under MPL_RASTER_LOCK on the thread that owns the Figure). ``compute()``
    must never touch a matplotlib Axes/Figure.
    """

    @abstractmethod
    def compute(
        self,
        x: np.ndarray,
        y: np.ndarray | None = None,
        *,
        xlim: tuple[float, float] | None = None,
        ylim: tuple[float, float] | None = None,
        **kwargs,
    ) -> Any:
        """Compute the data needed to draw this strategy's plot.

        Args:
            x:      X-axis data (transformed).
            y:      Y-axis data (transformed), or None for 1-D strategies.
            xlim:   Current X-axis limits, needed by density-based strategies.
            ylim:   Current Y-axis limits, needed by density-based strategies.
            **kwargs: Additional parameters (e.g., color, alpha, grid size).

        Returns:
            An opaque, strategy-specific object holding everything ``draw()``
            needs. Must not hold a matplotlib Artist/Axes/Figure.
        """

    @abstractmethod
    def draw(self, ax: Axes, data: Any, **kwargs) -> None:
        """Draw the precomputed ``data`` (from ``compute()``) onto ``ax``.

        Args:
            ax:     Matplotlib axes to draw on.
            data:   The return value of a prior ``compute()`` call.
            **kwargs: Additional parameters (e.g., color, alpha, grid size).
        """
