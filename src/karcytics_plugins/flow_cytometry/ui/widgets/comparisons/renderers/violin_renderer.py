"""Violin plot renderer — shows distribution shape per sample for one channel."""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure

from .base import IPlotRenderer

# Palette consistent with Karcytics gate colours (hex, no Qt dependency)
_DEFAULT_PALETTE = [
    "#00bcd4",
    "#ef5350",
    "#66bb6a",
    "#ffa726",
    "#ab47bc",
    "#26c6da",
    "#ff7043",
    "#9ccc65",
]


class ViolinRenderer(IPlotRenderer):
    """SRP: renders a violin plot comparing channel distributions across samples."""

    def render(self, **kwargs) -> Figure:
        data_per_label: dict[str, np.ndarray] = kwargs["data_per_label"]
        channel_label: str = kwargs.get("channel_label", "Channel")
        show_box: bool = kwargs.get("show_box", True)
        show_points: bool = kwargs.get("show_points", False)
        orientation: str = kwargs.get("orientation", "vertical")
        bg_color: str = kwargs.get("bg_color", "#0d1117")
        fg_color: str = kwargs.get("fg_color", "#e6edf3")
        border_color: str = kwargs.get("border_color", "#30363d")
        palette: list[str] = kwargs.get("palette", _DEFAULT_PALETTE)

        labels = list(data_per_label.keys())
        arrays = [data_per_label[k] for k in labels]

        fig = Figure(figsize=(max(6, len(labels) * 1.5), 6), facecolor=bg_color)
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg_color)

        # Filter out empty arrays
        valid = [
            (lbl, arr)
            for lbl, arr in zip(labels, arrays, strict=False)
            if len(arr) >= 5  # noqa: PLR2004
        ]
        if not valid:
            ax.text(
                0.5,
                0.5,
                "Insufficient data",
                ha="center",
                va="center",
                color=fg_color,
                transform=ax.transAxes,
                fontsize=13,
            )
            _style_axes(ax, fg_color, border_color)
            return fig

        valid_labels, valid_arrays = zip(*valid, strict=False)
        positions = list(range(1, len(valid_labels) + 1))

        vert = orientation == "vertical"
        parts = ax.violinplot(
            valid_arrays,
            positions=positions,
            vert=vert,
            showmeans=False,
            showmedians=True,
            showextrema=True,
        )

        # Colour each violin body from the palette
        for _i, (body, colour) in enumerate(
            zip(parts["bodies"], palette * 10, strict=False)  # type: ignore
        ):
            body.set_facecolor(colour)
            body.set_alpha(0.75)
            body.set_edgecolor(border_color)

        for part_key in ("cmedians", "cmaxes", "cmins", "cbars"):
            if part_key in parts:
                parts[part_key].set_color(fg_color)
                parts[part_key].set_linewidth(1.0)

        # Optional box plot overlay
        if show_box:
            ax.boxplot(
                valid_arrays,
                positions=positions,
                vert=vert,
                widths=0.08,
                patch_artist=True,
                medianprops=dict(color=fg_color, linewidth=1.5),
                boxprops=dict(facecolor=bg_color, edgecolor=fg_color, linewidth=0.8),
                whiskerprops=dict(color=fg_color, linewidth=0.8),
                capprops=dict(color=fg_color, linewidth=0.8),
                flierprops=dict(marker="o", markersize=2, color=fg_color, alpha=0.4),
            )

        # Optional strip (individual points) — pure numpy jitter, no extra axes
        if show_points:
            rng = np.random.default_rng(42)
            for _i, (pos, arr) in enumerate(zip(positions, valid_arrays, strict=False)):
                pts = arr[:500]  # cap at 500 per sample
                jitter = rng.uniform(-0.08, 0.08, size=len(pts))
                if vert:
                    ax.scatter(
                        pos + jitter,
                        pts,
                        s=3,
                        alpha=0.30,
                        color=fg_color,
                        linewidths=0,
                        zorder=3,
                    )
                else:
                    ax.scatter(
                        pts,
                        pos + jitter,
                        s=3,
                        alpha=0.30,
                        color=fg_color,
                        linewidths=0,
                        zorder=3,
                    )

        if vert:
            ax.set_xticks(positions)
            ax.set_xticklabels(valid_labels, color=fg_color, fontsize=10)
            ax.set_ylabel(channel_label, color=fg_color, fontsize=11)
        else:
            ax.set_yticks(positions)
            ax.set_yticklabels(valid_labels, color=fg_color, fontsize=10)
            ax.set_xlabel(channel_label, color=fg_color, fontsize=11)

        ax.set_title(f"Distribution of {channel_label}", color=fg_color, fontsize=12, pad=10)
        _style_axes(ax, fg_color, border_color)
        fig.tight_layout(pad=1.5)
        return fig


def _style_axes(ax, fg_color: str, border_color: str) -> None:
    ax.tick_params(colors=fg_color, labelsize=9)
    for spine in ax.spines.values():
        spine.set_color(border_color)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=border_color, linewidth=0.5, alpha=0.6)
