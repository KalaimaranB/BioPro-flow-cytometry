"""PLOT_REGISTRY — maps plot type names to (Renderer class, OptionsPanel class).

OCP: adding a new plot type means adding one entry here and two new classes.
Zero changes to ComparisonsViewer.
"""

from __future__ import annotations

from .options.fmo_options import FmoOptionsPanel
from .options.heatmap_options import HeatmapOptionsPanel
from .options.histogram_overlay_options import HistogramOverlayOptionsPanel
from .options.radar_options import RadarOptionsPanel
from .options.violin_options import ViolinOptionsPanel
from .renderers.fmo_renderer import FmoRenderer
from .renderers.heatmap_renderer import HeatmapRenderer
from .renderers.histogram_overlay_renderer import HistogramOverlayRenderer
from .renderers.radar_renderer import RadarRenderer
from .renderers.violin_renderer import ViolinRenderer

# OCP extension point: add a new plot type by adding one entry here.
PLOT_REGISTRY: dict[str, tuple] = {
    "🎻  Violin Plot": (ViolinRenderer, ViolinOptionsPanel),
    "🗺️  Channel Heatmap": (HeatmapRenderer, HeatmapOptionsPanel),
    "🕷️  Radar Chart": (RadarRenderer, RadarOptionsPanel),
    "📈  FMO Overlay": (FmoRenderer, FmoOptionsPanel),
    "📊  Histogram Overlay": (HistogramOverlayRenderer, HistogramOverlayOptionsPanel),
}

# Help text shown in the BioHelpButton next to the plot type selector.
PLOT_HELP: dict[str, tuple[str, str]] = {
    "🎻  Violin Plot": (
        "Violin Plot",
        "<b>What it shows:</b> The distribution of one channel across multiple samples "
        "side-by-side. Wide violin = many cells at that intensity.<br><br>"
        "<b>When to use:</b> Comparing CD3 or CD19 expression to identify T-cell vs B-cell "
        "enriched samples (thymus vs bone marrow vs spleen).",
    ),
    "🗺️  Channel Heatmap": (
        "Channel Heatmap",
        "<b>What it shows:</b> A colour grid — rows = samples or populations, "
        "columns = channels. Cell colour = median expression level.<br><br>"
        "<b>When to use:</b> One-glance organ identification. Thymus rows light up for "
        "CD3/CD4/CD8; bone marrow rows light up for B220/IgM.",
    ),
    "🕷️  Radar Chart": (
        "Radar / Spider Chart",
        "<b>What it shows:</b> Each population as a coloured polygon on a wheel. "
        "Each spoke = a channel. The shape = the immunophenotype fingerprint.<br><br>"
        "<b>When to use:</b> Comparing cell identities visually. Completely different "
        "shapes immediately reveal different organs or cell types.",
    ),
    "📈  FMO Overlay": (
        "FMO Overlay",
        "<b>What it shows:</b> Two overlapping histograms — your real sample (filled) "
        "vs the FMO control (outline). The dashed line marks the 99th percentile of the FMO.<br><br>"
        "<b>When to use:</b> Setting scientifically defensible gates. Any bump in the real "
        "sample to the right of the FMO background = genuine positive cells.",
    ),
    "📊  Histogram Overlay": (
        "Histogram Overlay",
        "<b>What it shows:</b> Per-population channel distributions overlaid on a single axis "
        "or stacked as ridge panels (waterfall style).<br><br>"
        "<b>When to use:</b> Comparing how different strains, conditions, or populations distribute "
        "along one fluorescence channel. Both Overlay and Ridge modes support any mix of samples "
        "and populations simultaneously.",
    ),
}

# Plot types whose options panel does NOT use the channel list
PLOTS_WITHOUT_CHANNEL_LIST = {"📈  FMO Overlay"}

# Plot types that need multiple populations selected (vs one per sample)
PLOTS_MULTI_POPULATION = {
    "🗺️  Channel Heatmap",
    "🕷️  Radar Chart",
    "📊  Histogram Overlay",
}

# Plot types that need multiple channels (heatmap, radar) vs single (violin, fmo)
PLOTS_MULTI_CHANNEL = {"🗺️  Channel Heatmap", "🕷️  Radar Chart"}
