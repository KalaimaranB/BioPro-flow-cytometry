"""Renderer strategy for 1D Cumulative Distribution Function (CDF) plots."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from karcytics_sdk.plugin.theme_fallback import Colors

from .base import DisplayStrategy


@dataclass
class CdfRenderData:
    """Precomputed sorted CDF curve, ready to draw."""

    sorted_x: np.ndarray
    y_vals: np.ndarray


class CdfStrategy(DisplayStrategy):
    """1D Cumulative Distribution Function (CDF) renderer."""

    def compute(
        self, x: np.ndarray, y: np.ndarray | None = None, *, xlim=None, ylim=None, **kwargs
    ) -> CdfRenderData | None:
        """Compute the sorted CDF curve for the X-axis parameter."""
        valid_x = x[np.isfinite(x)]
        if len(valid_x) == 0:
            return None

        sorted_x = np.sort(valid_x)
        y_vals = np.arange(len(sorted_x)) / float(len(sorted_x))
        return CdfRenderData(sorted_x=sorted_x, y_vals=y_vals)

    def draw(self, ax, data: CdfRenderData | None, **kwargs) -> None:
        """Draw the precomputed CDF curve for the X-axis parameter."""
        if data is None:
            return

        ax.plot(
            data.sorted_x,
            data.y_vals,
            color=kwargs.get("color", Colors.ACCENT_PRIMARY),
            linewidth=kwargs.get("linewidth", 1.5),
            alpha=kwargs.get("alpha", 0.9),
        )
        ax.set_ylabel("Probability", fontsize=9)
        ax.set_ylim(0, 1.05)
