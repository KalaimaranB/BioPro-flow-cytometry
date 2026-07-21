"""Renderer strategy for 1D frequency histograms."""

from __future__ import annotations

import logging

import numpy as np
from biopro.ui.theme import Colors

from .base import DisplayStrategy

logger = logging.getLogger(__name__)


class HistogramStrategy(DisplayStrategy):
    """1D Histogram renderer with optional KDE overlay."""

    def render(self, ax, x, y=None, **kwargs) -> None:
        """Render a frequency histogram for the X-axis parameter."""
        valid_x = x[np.isfinite(x)]
        if len(valid_x) == 0:
            return

        color = kwargs.get("color", kwargs.get("bar_color", Colors.ACCENT_PRIMARY))
        filled = kwargs.get("filled", True)
        histtype = "stepfilled" if filled else "step"
        density_mode = kwargs.get("y_axis_mode", "count") == "frequency"

        # Bin count — auto uses Sturges' rule, otherwise use provided value
        auto_bins = kwargs.get("auto_bins", False)
        if auto_bins:
            bins = int(np.ceil(np.log2(len(valid_x)) + 1))
            bins = max(32, min(bins, 512))
        else:
            bins = kwargs.get("bins", 256)

        # Render FMO Overlay (drawn underneath main histogram)
        fmo_data_x = kwargs.get("fmo_data_x")
        if fmo_data_x is not None:
            fmo_valid_x = fmo_data_x[np.isfinite(fmo_data_x)]
            if len(fmo_valid_x) > 0:
                fmo_color = kwargs.get("fmo_color", "#888888")
                logger.debug(
                    "[HIST-RENDER] ax.hist FMO: n=%d bins=%d dtype=%s",
                    len(fmo_valid_x),
                    bins,
                    fmo_valid_x.dtype,
                )
                ax.hist(
                    fmo_valid_x,
                    bins=bins,
                    color=fmo_color,
                    alpha=0.5,
                    histtype="stepfilled",
                    density=density_mode,
                    zorder=0,  # Ensure it stays in the background
                )
                logger.debug("[HIST-RENDER] ax.hist FMO done")
                # Ensure the main histogram renders on top
                kwargs["zorder"] = 1
        else:
            fmo_valid_x = np.array([])

        logger.debug(
            "[HIST-RENDER] ax.hist main: n=%d bins=%d dtype=%s",
            len(valid_x),
            bins,
            valid_x.dtype,
        )
        counts, edges, patches = ax.hist(
            valid_x,
            bins=bins,
            color=color,
            alpha=kwargs.get("alpha", 0.7),
            histtype=histtype,
            density=density_mode,
            zorder=kwargs.get("zorder", 1),
        )
        logger.debug("[HIST-RENDER] ax.hist main done")

        # Draw the threshold line for FMO AFTER both histograms
        if (
            kwargs.get("show_fmo_threshold", True)
            and fmo_data_x is not None
            and len(fmo_valid_x) > 0
        ):
            perc = kwargs.get("fmo_threshold_percentile", 99.0)
            logger.debug(
                "[HIST-RENDER] np.percentile FMO threshold: n=%d perc=%s",
                len(fmo_valid_x),
                perc,
            )
            p_val = np.percentile(fmo_valid_x, perc)
            logger.debug("[HIST-RENDER] FMO threshold p_val=%s", p_val)
            t_color = kwargs.get("fmo_threshold_color", "#ff4444")
            ax.axvline(x=p_val, color=t_color, linestyle="--", linewidth=1.5, zorder=3)

            # Format the text (e.g. 99th, 95.5th, 90th)
            perc_str = f"{perc:g}"
            suffix = (
                "th"
                if perc_str.endswith("11")
                or perc_str.endswith("12")
                or perc_str.endswith("13")
                else {"1": "st", "2": "nd", "3": "rd"}.get(perc_str[-1], "th")
            )

            ax.text(
                p_val,
                ax.get_ylim()[1] * 0.95,
                f" {perc_str}{suffix} %tile (Gate Threshold)",
                color=t_color,
                fontsize=8,
                va="top",
                ha="left",
                zorder=3,
            )

        # Optional KDE smoothing overlay
        smooth_kde = kwargs.get("smooth_kde", False)
        if smooth_kde and len(valid_x) > 10:
            try:
                from scipy.stats import gaussian_kde

                logger.debug("[HIST-RENDER] gaussian_kde: n=%d", len(valid_x))
                kde = gaussian_kde(valid_x, bw_method="scott")
                x_grid = np.linspace(valid_x.min(), valid_x.max(), 512)
                kde_vals = kde(x_grid)
                logger.debug("[HIST-RENDER] gaussian_kde done")
                if not density_mode:
                    # Scale KDE to match raw count histogram
                    bin_width = (edges[-1] - edges[0]) / bins
                    kde_vals = kde_vals * len(valid_x) * bin_width
                ax.plot(x_grid, kde_vals, color=color, linewidth=1.5, alpha=0.9)
            except Exception:
                pass  # KDE silently skipped on failure

        y_label = "Frequency (%)" if density_mode else "Count"
        ax.set_ylabel(y_label, fontsize=9)
        logger.debug("[HIST-RENDER] render complete")
