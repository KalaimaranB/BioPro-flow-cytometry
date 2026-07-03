"""render_panels package."""

from .contour_panel import ContourSettingsPanel
from .dotplot_panel import DotPlotSettingsPanel
from .histogram_panel import HistogramSettingsPanel
from .pseudocolor_panel import PseudocolorSettingsPanel

__all__ = [
    "PseudocolorSettingsPanel",
    "DotPlotSettingsPanel",
    "HistogramSettingsPanel",
    "ContourSettingsPanel",
]
