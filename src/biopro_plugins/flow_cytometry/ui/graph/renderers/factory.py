"""Factory and registry for UI plot renderers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .cdf import CdfStrategy
from .contour import ContourStrategy
from .dotplot import DotPlotStrategy
from .histogram import HistogramStrategy
from .pseudocolor import PseudocolorStrategy

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
            return cls._strategies.get("Dot Plot")  # type: ignore
        return strategy


RenderStrategyFactory.register("Pseudocolor", PseudocolorStrategy())
RenderStrategyFactory.register("Dot Plot", DotPlotStrategy())
RenderStrategyFactory.register("Histogram", HistogramStrategy())
RenderStrategyFactory.register("Contour", ContourStrategy())
RenderStrategyFactory.register("CDF", CdfStrategy())
