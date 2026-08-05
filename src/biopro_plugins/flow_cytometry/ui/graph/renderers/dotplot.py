"""Renderer strategy for simple subsampled scatter plots."""

from __future__ import annotations

from biopro.ui.theme import Colors

from .base import DisplayStrategy


class DotPlotStrategy(DisplayStrategy):
    """Simple subsampled scatter plot renderer."""

    def render(self, ax, x, y, **kwargs) -> None:
        """Render individual events as dots."""
        max_events = kwargs.get("max_events", 100_000)
        n = len(x)

        if max_events is not None and n > max_events:
            # stable_subsample_mask, not Generator.choice — a gated
            # population differing by a handful of events between two
            # otherwise-identical renders must not resample ~50% of the
            # plotted points as a result (see its docstring).
            from ....analysis.rendering import stable_subsample_mask

            mask = stable_subsample_mask(n, max_events)
            x, y = x[mask], y[mask]

        ax.scatter(
            x,
            y,
            s=kwargs.get("s", kwargs.get("dot_size", 2)),
            c=kwargs.get("c", kwargs.get("dot_color", Colors.ACCENT_PRIMARY)),
            alpha=kwargs.get("alpha", kwargs.get("opacity", 0.25)),
            rasterized=True,
            edgecolors="none",
        )
