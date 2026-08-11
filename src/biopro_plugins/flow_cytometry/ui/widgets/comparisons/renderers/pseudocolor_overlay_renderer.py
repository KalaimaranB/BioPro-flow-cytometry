"""Pseudocolor multi-population overlay renderer — one sample, many populations
plotted on a single 2D axis.

Generalizes the previous BackgatingRenderer (grey parent / single coloured
child, never registered in PLOT_REGISTRY) into an arbitrary-length stack of
population layers, with the base/context layer optionally density-shaded
(pseudocolor) instead of a flat grey scatter — reusing the same density math
(`compute_pseudocolor_points`) the single-sample gating canvas already uses
via `PseudocolorStrategy` (ui/graph/renderers/pseudocolor.py).
"""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure

from biopro_plugins.flow_cytometry.analysis.rendering import stable_subsample_mask

from .base import IPlotRenderer

# Cap points actually drawn per layer — the underlying event arrays can be
# gate-sized (hundreds of thousands); rasterized scatter still needs a visual cap.
_MAX_BASE_EVENTS = 20_000
_MAX_LAYER_EVENTS = 8_000

# Default colour palette (same as the other comparison renderers) — used only
# if the caller doesn't inject the shared BioPro gate palette via kwargs.
_DEFAULT_PALETTE = [
    "#00bcd4",
    "#ef5350",
    "#66bb6a",
    "#ffa726",
    "#ab47bc",
    "#26c6da",
    "#ff7043",
    "#9ccc65",
    "#29b6f6",
    "#ec407a",
    "#d4e157",
    "#8d6e63",
]


_UNSET = object()


class PseudocolorOverlayRenderer(IPlotRenderer):
    """SRP: renders a base population (optionally density-shaded) plus N
    coloured population overlays on one 2D scatter axis.

    Pure drawing only — no heavy numpy/scipy density computation. That work
    (`compute_pseudocolor_points`, which can take seconds over a real gated
    population) is expected to happen in the kwargs builder *before*
    ComparisonsWorker acquires MPL_LOCK to call this method, since that lock
    exists to serialize matplotlib's C-level drawing calls, not to guard
    plain data prep — see kwargs_builders.build_pseudocolor_overlay_kwargs.
    Pass ``base_density`` as that pre-computed ``(x_plot, y_plot, c_plot)``
    triple (or ``None`` to force the flat fallback). If the kwarg is omitted
    entirely, this method computes it itself — kept only so the renderer
    stays usable/testable standalone, e.g. in unit tests.
    """

    def render(self, **kwargs) -> Figure:  # noqa: PLR0913
        base_x: np.ndarray = kwargs["base_x"]
        base_y: np.ndarray = kwargs["base_y"]
        base_label: str = kwargs.get("base_label", "All Events")
        layers: list[dict] = kwargs.get("layers", [])
        palette: list[str] = kwargs.get("palette", _DEFAULT_PALETTE)
        default_opacity: float = kwargs.get("layer_opacity", 0.7)
        x_label: str = kwargs.get("x_label", "X")
        y_label: str = kwargs.get("y_label", "Y")
        sample_label: str = kwargs.get("sample_label", "")
        show_density_base: bool = kwargs.get("show_density_base", True)
        bg_color: str = kwargs.get("bg_color", "#0d1117")
        fg_color: str = kwargs.get("fg_color", "#e6edf3")
        border_color: str = kwargs.get("border_color", "#30363d")

        base_density = kwargs.get("base_density", _UNSET)
        if base_density is _UNSET:
            base_density = self._compute_base_density(base_x, base_y, show_density_base)

        fig = Figure(figsize=(7, 6), facecolor=bg_color)
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg_color)

        if len(base_x) and len(base_y):
            ax.set_xlim(float(np.nanmin(base_x)), float(np.nanmax(base_x)))
            ax.set_ylim(float(np.nanmin(base_y)), float(np.nanmax(base_y)))

        if base_density is not None:
            x_plot, y_plot, c_plot = base_density
            ax.scatter(
                x_plot,
                y_plot,
                s=1.0,
                c=c_plot,
                cmap="Greys",
                vmin=0.0,
                vmax=1.0,
                alpha=0.55,
                marker="o",
                rasterized=True,
                edgecolors="none",
                zorder=0,
                label=f"{base_label} ({len(base_x):,} events)",
            )
        elif len(base_x) and len(base_y):
            bx, by = base_x, base_y
            if len(bx) > _MAX_BASE_EVENTS:
                mask = stable_subsample_mask(len(bx), _MAX_BASE_EVENTS)
                bx, by = bx[mask], by[mask]
            ax.scatter(
                bx,
                by,
                s=1.5,
                alpha=0.12,
                color="#8b949e",
                rasterized=True,
                zorder=0,
                label=f"{base_label} ({len(base_x):,} events)",
            )

        for i, layer in enumerate(layers):
            lx, ly = layer["x"], layer["y"]
            if len(lx) == 0:
                continue
            if len(lx) > _MAX_LAYER_EVENTS:
                mask = stable_subsample_mask(len(lx), _MAX_LAYER_EVENTS)
                lx, ly = lx[mask], ly[mask]
            color = layer.get("color") or palette[i % len(palette)]
            ax.scatter(
                lx,
                ly,
                s=3,
                alpha=layer.get("opacity", default_opacity),
                color=color,
                rasterized=True,
                zorder=1,
                label=f"{layer['label']} ({len(layer['x']):,} events)",
            )

        ax.set_xlabel(x_label, color=fg_color, fontsize=11)
        ax.set_ylabel(y_label, color=fg_color, fontsize=11)
        title = f"Pseudocolor Overlay: {sample_label}" if sample_label else "Pseudocolor Overlay"
        ax.set_title(title, color=fg_color, fontsize=12, pad=10)
        if ax.get_legend_handles_labels()[1]:
            ax.legend(
                fontsize=8,
                facecolor=bg_color,
                edgecolor=border_color,
                labelcolor=fg_color,
                loc="best",
            )

        _style_axes(ax, fg_color, border_color)
        fig.tight_layout(pad=1.5)
        return fig

    @staticmethod
    def _compute_base_density(base_x: np.ndarray, base_y: np.ndarray, show_density_base: bool):
        """Fallback for standalone/test use only — production callers should
        pass a pre-computed ``base_density`` kwarg (see class docstring).
        """
        from biopro_plugins.flow_cytometry.analysis.constants import PSEUDOCOLOR_MAX_EVENTS
        from biopro_plugins.flow_cytometry.analysis.rendering import (
            compute_pseudocolor_base_density,
        )

        return compute_pseudocolor_base_density(
            base_x, base_y, PSEUDOCOLOR_MAX_EVENTS, enabled=show_density_base
        )


def _style_axes(ax, fg_color: str, border_color: str) -> None:
    ax.tick_params(colors=fg_color, labelsize=9)
    for spine in ax.spines.values():
        spine.set_color(border_color)
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color=border_color, linewidth=0.4, alpha=0.5)
    ax.yaxis.grid(True, color=border_color, linewidth=0.4, alpha=0.5)
