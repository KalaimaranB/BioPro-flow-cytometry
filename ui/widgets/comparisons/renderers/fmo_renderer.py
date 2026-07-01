"""FMO Overlay renderer — real sample histogram vs FMO control, with gate suggestion."""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure

from .base import IPlotRenderer


class FmoRenderer(IPlotRenderer):
    """SRP: renders two overlapping histograms — real sample vs FMO control."""

    def render(self, **kwargs) -> Figure:
        sample_values: np.ndarray = kwargs["sample_values"]
        fmo_values: np.ndarray = kwargs["fmo_values"]
        channel_label: str = kwargs.get("channel_label", "Channel")
        sample_label: str = kwargs.get("sample_label", "Sample")
        fmo_label: str = kwargs.get("fmo_label", "FMO Control")
        show_gate_line: bool = kwargs.get("show_gate_line", True)
        n_bins: int = kwargs.get("n_bins", 256)
        bg_color: str = kwargs.get("bg_color", "#0d1117")
        fg_color: str = kwargs.get("fg_color", "#e6edf3")
        border_color: str = kwargs.get("border_color", "#30363d")
        accent_color: str = kwargs.get("accent_color", "#00bcd4")

        fig = Figure(figsize=(8, 5), facecolor=bg_color)
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg_color)

        if len(sample_values) == 0 and len(fmo_values) == 0:
            ax.text(0.5, 0.5, "No data to display", ha="center", va="center",
                    color=fg_color, transform=ax.transAxes, fontsize=13)
            _style_axes(ax, fg_color, border_color)
            return fig

        # Shared bin range across both histograms
        all_vals = np.concatenate([v for v in [sample_values, fmo_values] if len(v) > 0])
        x_min, x_max = np.percentile(all_vals, 0.5), np.percentile(all_vals, 99.5)
        bins = np.linspace(x_min, x_max, n_bins + 1)

        # FMO — outline only (step style, grey)
        if len(fmo_values) > 0:
            ax.hist(fmo_values, bins=bins, histtype="step",
                    color="#8b949e", linewidth=1.5,
                    label=f"{fmo_label} (n={len(fmo_values):,})", density=True)

        # Real sample — filled, accent colour
        if len(sample_values) > 0:
            ax.hist(sample_values, bins=bins, histtype="stepfilled",
                    color=accent_color, alpha=0.55, linewidth=1.2,
                    edgecolor=accent_color,
                    label=f"{sample_label} (n={len(sample_values):,})", density=True)

        # Suggested gate line at FMO 99th percentile
        if show_gate_line and len(fmo_values) > 10:
            gate_pos = np.percentile(fmo_values, 99.0)
            ax.axvline(gate_pos, color="#ffa726", linewidth=1.5,
                       linestyle="--", label=f"Suggested gate ({gate_pos:.1f})")

        ax.set_xlabel(channel_label, color=fg_color, fontsize=11)
        ax.set_ylabel("Density", color=fg_color, fontsize=11)
        ax.set_title(f"FMO Overlay — {channel_label}", color=fg_color, fontsize=12, pad=10)

        legend = ax.legend(fontsize=9, facecolor=bg_color, edgecolor=border_color,
                           labelcolor=fg_color)

        _style_axes(ax, fg_color, border_color)
        fig.tight_layout(pad=1.5)
        return fig


def _style_axes(ax, fg_color: str, border_color: str) -> None:
    ax.tick_params(colors=fg_color, labelsize=9)
    for spine in ax.spines.values():
        spine.set_color(border_color)
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=border_color, linewidth=0.4, alpha=0.5)
