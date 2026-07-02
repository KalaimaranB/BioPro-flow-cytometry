from __future__ import annotations
from .cdf import CdfStrategy  # noqa: E402
from .contour import ContourStrategy  # noqa: E402
from .density import DensityStrategy  # noqa: E402
from .dotplot import DotPlotStrategy  # noqa: E402
from .histogram import HistogramStrategy  # noqa: E402
from .pseudocolor import PseudocolorStrategy  # noqa: E402

"""Factory and registry for UI plot renderers."""


from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    from .base import DisplayStrategy


class RenderStrategyFactory:
    """Registry and factory for data rendering strategies."""

    _strategies: dict[str, DisplayStrategy] = {}

    @classmethod
    def register(cls, mode_name: str, strategy: DisplayStrategy) -> None:
        cls._strategies[mode_name] = strategy

    @classmethod
    def get_strategy(cls, mode_name: str) -> DisplayStrategy:
        strategy = cls._strategies.get(mode_name)
        if not strategy:
            # Fallback to DotPlot if not found
            return cls._strategies.get("Dot Plot")
        return strategy


RenderStrategyFactory.register("Pseudocolor", PseudocolorStrategy())
RenderStrategyFactory.register("Dot Plot", DotPlotStrategy())
RenderStrategyFactory.register("Histogram", HistogramStrategy())
RenderStrategyFactory.register("Contour", ContourStrategy())
RenderStrategyFactory.register("CDF", CdfStrategy())
RenderStrategyFactory.register("Density", DensityStrategy())
