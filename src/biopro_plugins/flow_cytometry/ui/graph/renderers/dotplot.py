"""Renderer strategy for simple subsampled scatter plots."""

from __future__ import annotations

import numpy as np
from biopro.ui.theme import Colors

from .base import DisplayStrategy


class DotPlotStrategy(DisplayStrategy):
    """Simple subsampled scatter plot renderer."""

    def render(self, ax, x, y, **kwargs) -> None:
        """Render individual events as dots."""
        max_events = kwargs.get("max_events", 100_000)
        n = len(x)

        if max_events is not None and n > max_events:
            # Fixed seed so the same gate renders the same subsample every
            # time (matches the convention used elsewhere in this plugin).
            idx = np.random.default_rng(42).choice(n, max_events, replace=False)
            x, y = x[idx], y[idx]

        ax.scatter(
            x,
            y,
            s=kwargs.get("s", kwargs.get("dot_size", 2)),
            c=kwargs.get("c", kwargs.get("dot_color", Colors.ACCENT_PRIMARY)),
            alpha=kwargs.get("alpha", kwargs.get("opacity", 0.25)),
            rasterized=True,
            edgecolors="none",
        )
