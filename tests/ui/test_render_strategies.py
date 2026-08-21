from unittest.mock import MagicMock

import numpy as np
import pytest

from karcytics_plugins.flow_cytometry.ui.graph.renderers.cdf import CdfStrategy
from karcytics_plugins.flow_cytometry.ui.graph.renderers.contour import ContourStrategy
from karcytics_plugins.flow_cytometry.ui.graph.renderers.dotplot import DotPlotStrategy
from karcytics_plugins.flow_cytometry.ui.graph.renderers.factory import (
    RenderStrategyFactory,
)
from karcytics_plugins.flow_cytometry.ui.graph.renderers.histogram import HistogramStrategy
from karcytics_plugins.flow_cytometry.ui.graph.renderers.pseudocolor import (
    PseudocolorStrategy,
)


@pytest.fixture
def mock_ax():
    ax = MagicMock()
    ax.get_xlim.return_value = (0.0, 100000.0)
    ax.get_ylim.return_value = (0.0, 100000.0)
    ax.hist.return_value = (np.array([1]), np.array([0, 1]), [MagicMock()])
    return ax


@pytest.fixture
def dummy_data():
    x = np.random.normal(100000, 20000, 1000)
    y = np.random.normal(50000, 10000, 1000)
    return x, y


def test_strategy_factory():
    """Verify the factory returns the correct strategies and falls back gracefully."""
    pseudo = RenderStrategyFactory.get_strategy("Pseudocolor")
    assert isinstance(pseudo, PseudocolorStrategy)

    # Unknown strategy falls back to Dot Plot
    fallback = RenderStrategyFactory.get_strategy("UnknownStrategyName")
    assert isinstance(fallback, DotPlotStrategy)


def test_pseudocolor_strategy_render(mock_ax, dummy_data):
    x, y = dummy_data
    strategy = PseudocolorStrategy()

    data = strategy.compute(x, y, xlim=mock_ax.get_xlim(), ylim=mock_ax.get_ylim())
    strategy.draw(mock_ax, data)
    # Pseudocolor uses ax.scatter
    mock_ax.scatter.assert_called_once()


def test_dotplot_strategy_render(mock_ax, dummy_data):
    x, y = dummy_data
    strategy = DotPlotStrategy()

    data = strategy.compute(x, y)
    strategy.draw(mock_ax, data)
    mock_ax.scatter.assert_called_once()

    # Check that performance optimization configs are passed
    call_kwargs = mock_ax.scatter.call_args[1]
    assert call_kwargs.get("rasterized") is True


def test_histogram_strategy_render(mock_ax, dummy_data):
    x, _ = dummy_data
    strategy = HistogramStrategy()

    # Histogram only uses x data, but API takes y=None or ignores it
    data = strategy.compute(x, None, bins=128)
    strategy.draw(mock_ax, data, bins=128)
    # Histogram uses ax.hist
    assert mock_ax.hist.called


def test_contour_strategy_render(mock_ax, dummy_data):
    x, y = dummy_data
    strategy = ContourStrategy()

    data = strategy.compute(x, y, xlim=mock_ax.get_xlim(), ylim=mock_ax.get_ylim(), levels=10)
    strategy.draw(mock_ax, data, levels=10)
    # Contour uses ax.contour or ax.contourf
    assert mock_ax.contour.called or mock_ax.contourf.called


def test_cdf_strategy_render(mock_ax, dummy_data):
    x, _ = dummy_data
    strategy = CdfStrategy()

    data = strategy.compute(x, None)
    strategy.draw(mock_ax, data)
    # CDF usually uses ax.plot
    assert mock_ax.plot.called
