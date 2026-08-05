from __future__ import annotations

import numpy as np
from biopro_sdk.plugin import get_logger

from .base import DisplayStrategy

logger = get_logger(__name__, "flow_cytometry")


class PseudocolorStrategy(DisplayStrategy):
    """Canonical pseudocolor density renderer."""

    def render(self, ax, x, y, **kwargs) -> None:
        """Render density-colored scatter plot using unified robust math."""
        # Fix import path (rendering is in a sibling of ui, not a child)
        from ....analysis.constants import PSEUDOCOLOR_MAX_EVENTS
        from ....analysis.rendering import compute_pseudocolor_points

        # Subsample for UI performance if extremely large
        max_events = kwargs.get("max_events", PSEUDOCOLOR_MAX_EVENTS)

        if x is None or y is None:
            return

        # Ensure we use numpy arrays for positional indexing and performance
        x_np = np.asarray(x)
        y_np = np.asarray(y)

        if max_events is not None and len(x_np) > max_events:
            # Fixed seed (matches every other subsampling call site in this
            # plugin — thumbnails, UMAP, animations, comparison renderers)
            # so the same gate renders identically every time. An unseeded
            # draw here previously meant the density/threshold computation
            # below could shift enough, between any two renders of the exact
            # same data, to visually merge or split populations that sit
            # near the background-suppression cutoff.
            idx = np.random.default_rng(42).choice(len(x_np), max_events, replace=False)
            x_sub, y_sub = x_np[idx], y_np[idx]
        else:
            x_sub, y_sub = x_np, y_np

        x_lo, x_hi = ax.get_xlim()
        y_lo, y_hi = ax.get_ylim()

        # Use grid_size if provided, otherwise fall back to quality_multiplier
        grid_size = kwargs.get("grid_size")
        if grid_size:
            # Convert grid_size to quality_multiplier (base is 512)
            quality_multiplier = grid_size / 512.0
        else:
            quality_multiplier = kwargs.get("quality_multiplier", 1.0)

        x_plot, y_plot, c_plot = compute_pseudocolor_points(
            x_sub,
            y_sub,
            (x_lo, x_hi),
            (y_lo, y_hi),
            quality_multiplier=quality_multiplier,
            nbins_scaling=kwargs.get("nbins_scaling"),
            sigma_scaling=kwargs.get("sigma_scaling"),
            density_threshold=kwargs.get("density_threshold"),
            vibrancy_min=kwargs.get("vibrancy_min"),
            vibrancy_range=kwargs.get("vibrancy_range"),
        )

        # Revert to 'o' to maintain the classic thick blue cloud appearance
        # Point size 1.0 for Full, 1.5 for Optimized
        cmap_name = kwargs.get("cmap", kwargs.get("colormap", "jet"))
        alpha = kwargs.get("alpha", 0.6)
        is_full = kwargs.get("quality_multiplier", 1.0) >= 2.0  # noqa: PLR2004
        point_size = 1.0 if is_full else 1.5

        ax.scatter(
            x_plot,
            y_plot,
            s=kwargs.get("s", point_size),
            c=c_plot,
            cmap=cmap_name,
            vmin=0.0,
            vmax=1.0,
            alpha=alpha,
            marker="o",
            rasterized=True,
            edgecolors="none",
            zorder=0,
        )
