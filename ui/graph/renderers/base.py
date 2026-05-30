from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np
    from matplotlib.axes import Axes


class DisplayStrategy(ABC):
    """Abstract base class for all data rendering strategies."""

    @abstractmethod
    def render(self, ax: Axes, x: np.ndarray, y: np.ndarray, **kwargs) -> None:
        """Render data onto the provided axes.

        Args:
            ax:     Matplotlib axes to draw on.
            x:      X-axis data (transformed).
            y:      Y-axis data (transformed).
            **kwargs: Additional parameters (e.g., color, alpha, grid size).
        """
        pass
