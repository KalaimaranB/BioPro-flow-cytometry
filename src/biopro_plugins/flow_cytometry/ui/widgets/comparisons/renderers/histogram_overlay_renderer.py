"""Histogram Overlay renderer — shows multiple population distributions on one channel.

Two layout modes:
  overlay: all histograms on a single shared axis, alpha-blended.
  ridge:   one horizontal row per population, vertically stacked with a shared
           X-axis (waterfall / ridge-line style, matching the reference image).
"""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure

from .base import IPlotRenderer

# How many events to sample for KDE computation (speed guard)
_KDE_MAX_EVENTS = 20_000


class HistogramOverlayRenderer(IPlotRenderer):
    """SRP: renders a histogram overlay comparison for one channel."""

    def render(self, **kwargs) -> Figure:
        data_per_label: dict[str, np.ndarray] = kwargs["data_per_label"]
        channel_label: str = kwargs.get("channel_label", "Channel")
        layout: str = kwargs.get("layout", "ridge")  # "overlay" | "ridge"
        smooth_kde: bool = kwargs.get("smooth_kde", True)
        normalize_to_peak: bool = kwargs.get("normalize_to_peak", True)
        bins: int = int(kwargs.get("bins", 256))
        ridge_overlap: float = float(kwargs.get("ridge_overlap", 0.6))
        x_transform: str = kwargs.get("x_transform", "linear")
        show_legend: bool = kwargs.get("show_legend", True)
        line_width: float = float(kwargs.get("line_width", 1.5))
        bg_color: str = kwargs.get("bg_color", "#0d1117")
        fg_color: str = kwargs.get("fg_color", "#e6edf3")
        border_color: str = kwargs.get("border_color", "#30363d")
        palette: list[str] = kwargs.get("palette", _DEFAULT_PALETTE)

        # Filter out empty / too-small arrays
        valid = {
            lbl: arr
            for lbl, arr in data_per_label.items()
            if isinstance(arr, np.ndarray) and len(arr) >= 5  # noqa: PLR2004
        }

        if not valid:
            return _empty_figure(bg_color, fg_color, border_color)

        labels = list(valid.keys())
        arrays = list(valid.values())
        colors = [palette[i % len(palette)] for i in range(len(labels))]

        if layout == "overlay":
            return _render_overlay(
                labels,
                arrays,
                colors,
                channel_label,
                smooth_kde,
                normalize_to_peak,
                bins,
                x_transform,
                show_legend,
                line_width,
                bg_color,
                fg_color,
                border_color,
            )
        else:
            return _render_ridge(
                labels,
                arrays,
                colors,
                channel_label,
                smooth_kde,
                normalize_to_peak,
                bins,
                ridge_overlap,
                x_transform,
                line_width,
                bg_color,
                fg_color,
                border_color,
            )


# ── Default colour palette (same as existing comparison renderers) ─────────────

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


# ── Shared helpers ─────────────────────────────────────────────────────────────


def _compute_kde_curve(
    arr: np.ndarray, x_min: float, x_max: float, n_pts: int = 512
) -> tuple[np.ndarray, np.ndarray] | None:
    """Return (x_grid, y_kde) or None on failure."""
    try:
        from scipy.stats import gaussian_kde

        if len(arr) > _KDE_MAX_EVENTS:
            rng = np.random.default_rng(42)
            arr = rng.choice(arr, _KDE_MAX_EVENTS, replace=False)

        kde = gaussian_kde(arr, bw_method="scott")
        x_grid = np.linspace(x_min, x_max, n_pts)
        return x_grid, kde(x_grid)
    except Exception:
        return None


def _compute_histogram(
    arr: np.ndarray, bins: int, x_min: float, x_max: float
) -> tuple[np.ndarray, np.ndarray]:
    """Return (bin_centers, counts) for a clipped histogram."""
    arr_clipped = arr[(arr >= x_min) & (arr <= x_max)]
    if len(arr_clipped) == 0:
        arr_clipped = arr
    counts, edges = np.histogram(arr_clipped, bins=bins, range=(x_min, x_max))
    centers = 0.5 * (edges[:-1] + edges[1:])
    return centers, counts.astype(float)


def _global_range(arrays: list[np.ndarray], x_transform: str) -> tuple[float, float]:
    """Compute a shared x-axis range across all arrays."""
    all_vals = np.concatenate([a[np.isfinite(a)] for a in arrays])
    if len(all_vals) == 0:
        return 0.0, 1.0

    if x_transform == "log":
        pos = all_vals[all_vals > 0]
        if len(pos) == 0:
            return 1.0, 1e6
        p1, p99 = np.percentile(pos, [1, 99])
        return max(1.0, p1 * 0.5), p99 * 2.0
    else:
        p1, p99 = np.percentile(all_vals, [0.5, 99.5])
        span = p99 - p1
        return p1 - span * 0.02, p99 + span * 0.02


def _apply_x_transform(ax, x_transform: str) -> None:
    if x_transform == "log":
        ax.set_xscale("log")
    # biex approximation: just symlog with a small linear threshold
    elif x_transform == "biex":
        ax.set_xscale("symlog", linthresh=100, linscale=0.5)


def _style_spine(ax, fg_color: str, border_color: str) -> None:
    ax.tick_params(colors=fg_color, labelsize=8, length=3)
    for side, spine in ax.spines.items():
        if side in ("top", "right"):
            spine.set_visible(False)
        else:
            spine.set_color(border_color)


def _empty_figure(bg_color: str, fg_color: str, border_color: str) -> Figure:
    fig = Figure(figsize=(8, 5), facecolor=bg_color)
    ax = fig.add_subplot(111)
    ax.set_facecolor(bg_color)
    ax.text(
        0.5,
        0.5,
        "No data to display.\nSelect samples and a channel, then Generate.",
        ha="center",
        va="center",
        color=fg_color,
        fontsize=12,
        transform=ax.transAxes,
    )
    _style_spine(ax, fg_color, border_color)
    return fig


# ── Overlay layout ─────────────────────────────────────────────────────────────


def _render_overlay(  # noqa: PLR0913
    labels,
    arrays,
    colors,
    channel_label,
    smooth_kde,
    normalize_to_peak,
    bins,
    x_transform,
    show_legend,
    line_width,
    bg_color,
    fg_color,
    border_color,
) -> Figure:
    fig = Figure(figsize=(9, 5), facecolor=bg_color)
    ax = fig.add_subplot(111)
    ax.set_facecolor(bg_color)

    x_min, x_max = _global_range(arrays, x_transform)

    for arr, color, label in zip(arrays, colors, labels, strict=False):
        arr_f = arr[np.isfinite(arr)]

        if smooth_kde:
            result = _compute_kde_curve(arr_f, x_min, x_max)
        else:
            result = None

        if result is not None:
            x_vals, y_vals = result
        else:
            x_vals, y_vals = _compute_histogram(arr_f, bins, x_min, x_max)

        if normalize_to_peak and y_vals.max() > 0:
            y_vals = y_vals / y_vals.max()

        ax.fill_between(x_vals, y_vals, alpha=0.45, color=color, linewidth=0)
        ax.plot(
            x_vals, y_vals, color=color, linewidth=line_width, alpha=0.9, label=label
        )

    _apply_x_transform(ax, x_transform)
    ax.set_xlabel(channel_label, color=fg_color, fontsize=11)
    y_label = "Normalised Density" if normalize_to_peak else "Density"
    ax.set_ylabel(y_label, color=fg_color, fontsize=10)
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(bottom=0)

    if show_legend and labels:
        leg = ax.legend(
            fontsize=9,
            framealpha=0.15,
            facecolor=bg_color,
            edgecolor=border_color,
            labelcolor=fg_color,
            loc="upper right",
        )
        for text in leg.get_texts():
            text.set_color(fg_color)

    _style_spine(ax, fg_color, border_color)
    ax.set_title(
        f"Histogram Overlay — {channel_label}", color=fg_color, fontsize=12, pad=10
    )
    fig.tight_layout(pad=1.5)
    return fig


# ── Ridge (waterfall) layout ───────────────────────────────────────────────────


def _render_ridge(  # noqa: PLR0913, PLR0915
    labels,
    arrays,
    colors,
    channel_label,
    smooth_kde,
    normalize_to_peak,
    bins,
    ridge_overlap,
    x_transform,
    line_width,
    bg_color,
    fg_color,
    border_color,
) -> Figure:
    n = len(labels)
    # Height per row; overlap shrinks the effective row height
    row_h = 1.4
    fig_h = max(4.0, n * row_h * (1.0 - ridge_overlap * 0.5) + 1.5)
    fig = Figure(figsize=(8, fig_h), facecolor=bg_color)

    x_min, x_max = _global_range(arrays, x_transform)

    # Build one axes per row using manual positioning so they can overlap
    # Margins (figure-fraction)
    left_margin = 0.08
    right_margin = 0.05
    bottom_margin = 0.10
    top_margin = 0.08

    usable_h = 1.0 - bottom_margin - top_margin
    # Each panel occupies `panel_h` in figure fraction; panels are spaced
    # by `step` so they overlap by (panel_h - step).
    panel_h = usable_h / (n - ridge_overlap * (n - 1) / n) if n > 1 else usable_h
    # Cap panel_h so it never exceeds the full usable height
    panel_h = min(panel_h, usable_h * 0.75 + usable_h * 0.25 / max(n, 1))
    step = (usable_h - panel_h) / max(n - 1, 1) if n > 1 else 0

    axes = []
    for i, (_label, arr, color) in enumerate(
        zip(reversed(labels), reversed(arrays), reversed(colors), strict=False)
    ):
        # Panels are laid out bottom→top; i=0 is the bottommost visible row.
        bottom = bottom_margin + i * step
        rect = [left_margin, bottom, 1.0 - left_margin - right_margin, panel_h]
        ax = fig.add_axes(rect)
        ax.set_facecolor(bg_color)
        ax.patch.set_alpha(0.0)  # transparent so lower panels show through

        arr_f = arr[np.isfinite(arr)]

        if smooth_kde:
            result = _compute_kde_curve(arr_f, x_min, x_max)
        else:
            result = None

        if result is not None:
            x_vals, y_vals = result
        else:
            x_vals, y_vals = _compute_histogram(arr_f, bins, x_min, x_max)

        if normalize_to_peak and y_vals.max() > 0:
            y_vals = y_vals / y_vals.max()

        # Filled area — use a slightly lighter/more opaque fill
        ax.fill_between(
            x_vals,
            y_vals,
            alpha=0.65,
            color=color,
            linewidth=0,
        )
        # Solid top-edge line
        ax.plot(x_vals, y_vals, color=color, linewidth=line_width, alpha=0.95)
        # Flat baseline
        ax.axhline(0, color=color, linewidth=0.8, alpha=0.4)

        # Clip y so the fill from THIS panel doesn't spill into the panel above
        ax.set_ylim(0, y_vals.max() * 1.25 if y_vals.max() > 0 else 1.0)
        ax.set_xlim(x_min, x_max)

        _apply_x_transform(ax, x_transform)

        # Label — right-aligned text inside the panel (like reference image)
        original_label = list(reversed(labels))[i]
        ax.text(
            0.97,
            0.72,
            original_label,
            transform=ax.transAxes,
            ha="right",
            va="center",
            fontsize=9.5,
            fontweight="bold",
            color=fg_color,
        )

        # Spines and ticks — only bottom panel shows X ticks
        is_bottom = i == 0
        for side, spine in ax.spines.items():
            if side == "bottom":
                spine.set_color(border_color)
                spine.set_linewidth(0.8)
            else:
                spine.set_visible(False)

        if is_bottom:
            ax.tick_params(
                axis="x",
                which="both",
                colors=fg_color,
                labelsize=8,
                length=3,
                bottom=True,
                labelbottom=True,
            )
            ax.set_xlabel(channel_label, color=fg_color, fontsize=11, labelpad=4)
        else:
            ax.tick_params(
                axis="x",
                which="both",
                bottom=True,
                labelbottom=False,
                length=2,
                colors=border_color,
            )

        ax.tick_params(axis="y", left=False, labelleft=False)
        axes.append(ax)

    # Shared title above the topmost panel
    top_ax = axes[-1]
    top_ax.set_title(
        f"{channel_label}",
        color=fg_color,
        fontsize=12,
        pad=6,
        loc="left",
    )

    return fig
