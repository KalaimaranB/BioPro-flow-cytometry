"""Back-gating overlay renderer — parent events in grey, child in colour."""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure

from .base import IPlotRenderer


class BackgatingRenderer(IPlotRenderer):
    """SRP: renders a 2D scatter showing parent (grey) vs child (coloured) population."""

    def render(self, **kwargs) -> Figure:
        parent_x: np.ndarray = kwargs["parent_x"]
        parent_y: np.ndarray = kwargs["parent_y"]
        child_x: np.ndarray = kwargs["child_x"]
        child_y: np.ndarray = kwargs["child_y"]
        x_label: str = kwargs.get("x_label", "X")
        y_label: str = kwargs.get("y_label", "Y")
        child_label: str = kwargs.get("child_label", "Gated population")
        child_colour: str = kwargs.get("child_colour", "#00bcd4")
        child_opacity: float = kwargs.get("child_opacity", 0.65)
        bg_color: str = kwargs.get("bg_color", "#0d1117")
        fg_color: str = kwargs.get("fg_color", "#e6edf3")
        border_color: str = kwargs.get("border_color", "#30363d")

        fig = Figure(figsize=(7, 6), facecolor=bg_color)
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg_color)

        # Subsample parent to max 10 000 pts for performance
        MAX_PARENT = 10_000
        if len(parent_x) > MAX_PARENT:
            idx = np.random.choice(len(parent_x), MAX_PARENT, replace=False)
            px, py = parent_x[idx], parent_y[idx]
        else:
            px, py = parent_x, parent_y

        # Layer 1: parent population (grey, low alpha)
        ax.scatter(
            px,
            py,
            s=1.5,
            alpha=0.12,
            color="#8b949e",
            rasterized=True,
            label=f"Parent ({len(parent_x):,} events)",
        )

        # Layer 2: child (gated) population
        MAX_CHILD = 5_000
        if len(child_x) > MAX_CHILD:
            idx2 = np.random.choice(len(child_x), MAX_CHILD, replace=False)
            cx, cy = child_x[idx2], child_y[idx2]
        else:
            cx, cy = child_x, child_y

        ax.scatter(
            cx,
            cy,
            s=3,
            alpha=child_opacity,
            color=child_colour,
            rasterized=True,
            label=f"{child_label} ({len(child_x):,} events)",
        )

        ax.set_xlabel(x_label, color=fg_color, fontsize=11)
        ax.set_ylabel(y_label, color=fg_color, fontsize=11)
        ax.set_title(f"Back-gating: {child_label}", color=fg_color, fontsize=12, pad=10)

        ax.legend(
            fontsize=9, facecolor=bg_color, edgecolor=border_color, labelcolor=fg_color
        )

        _style_axes(ax, fg_color, border_color)
        fig.tight_layout(pad=1.5)
        return fig


def _style_axes(ax, fg_color: str, border_color: str) -> None:
    ax.tick_params(colors=fg_color, labelsize=9)
    for spine in ax.spines.values():
        spine.set_color(border_color)
    ax.set_axisbelow(True)
    ax.xaxis.grid(True, color=border_color, linewidth=0.4, alpha=0.5)
    ax.yaxis.grid(True, color=border_color, linewidth=0.4, alpha=0.5)
