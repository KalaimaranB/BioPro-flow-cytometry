from unittest.mock import MagicMock

import numpy as np

from biopro_plugins.flow_cytometry.analysis.scaling import AxisScale
from biopro_plugins.flow_cytometry.analysis.transforms import TransformType
from biopro_plugins.flow_cytometry.ui.graph.render_task import RenderTask


def test_render_task_execution(sample_data):
    task = RenderTask()
    x_scale = AxisScale(TransformType.LINEAR)
    y_scale = AxisScale(TransformType.LINEAR)

    task.configure(
        data=sample_data,
        x_param="FSC-A",
        y_param="SSC-A",
        x_scale=x_scale,
        y_scale=y_scale,
        x_range=(0, 1024),
        y_range=(0, 1024),
        width_px=100,
        height_px=100,
        plot_type="pseudocolor",
    )

    state = MagicMock()
    results = task.run(state)

    assert "image_data" in results
    assert results["width"] == 100
    assert results["height"] == 100


def test_rendering_math():
    from biopro_plugins.flow_cytometry.analysis.rendering import (
        compute_1d_histogram,
        compute_pseudocolor_points,
    )

    x = np.linspace(0, 100, 50)
    counts, edges = compute_1d_histogram(x, (0, 100), bins=10)
    assert len(counts) == 10
    assert counts.sum() == 50

    y = np.linspace(0, 100, 50)
    # compute_pseudocolor_points returns (x, y, colors)
    xv, yv, c = compute_pseudocolor_points(x, y, (0, 100), (0, 100))
    assert len(xv) == 50
    assert len(c) == 50


def test_rendering_custom_params():
    from biopro_plugins.flow_cytometry.analysis.rendering import (
        compute_pseudocolor_points,
    )

    # Dense cluster to ensure some values pass threshold
    np.random.seed(42)
    x = np.random.normal(50, 5, 1000)
    y = np.random.normal(50, 5, 1000)

    # Render with defaults
    xv_def, yv_def, c_def = compute_pseudocolor_points(x, y, (0, 100), (0, 100))

    # Render with custom aggressive threshold and vibrancy
    xv_cust, yv_cust, c_cust = compute_pseudocolor_points(
        x,
        y,
        (0, 100),
        (0, 100),
        density_threshold=0.3,
        vibrancy_min=0.5,
        vibrancy_range=1.0,
    )

    assert len(xv_cust) == 1000
    # Custom config should zero out more background points than defaults
    zeros_def = np.sum(c_def == 0.0)
    zeros_cust = np.sum(c_cust == 0.0)
    assert zeros_cust > zeros_def


def test_compute_pseudocolor_base_density_disabled_returns_none():
    from biopro_plugins.flow_cytometry.analysis.rendering import compute_pseudocolor_base_density

    x = np.linspace(0, 100, 50)
    y = np.linspace(0, 100, 50)
    assert compute_pseudocolor_base_density(x, y, max_events=1000, enabled=False) is None


def test_compute_pseudocolor_base_density_empty_input_returns_none():
    from biopro_plugins.flow_cytometry.analysis.rendering import compute_pseudocolor_base_density

    empty = np.array([])
    assert compute_pseudocolor_base_density(empty, empty, max_events=1000, enabled=True) is None


def test_compute_pseudocolor_base_density_subsamples_large_input():
    """This is the fix for a real segfault-adjacent bug: the Comparisons
    Pseudocolor Overlay plot type used to run this (potentially multi-second)
    computation while holding the process-wide MPL_LOCK, starving the main
    gating canvas's paint retries for the whole duration. It must stay a
    plain, subsampled numpy computation independent of any lock.
    """
    from biopro_plugins.flow_cytometry.analysis.rendering import compute_pseudocolor_base_density

    rng = np.random.default_rng(0)
    n = 5000
    x = rng.normal(50, 10, n)
    y = rng.normal(50, 10, n)

    result = compute_pseudocolor_base_density(x, y, max_events=1000, enabled=True)
    assert result is not None
    x_plot, y_plot, c_plot = result
    assert len(x_plot) <= n
    # Subsampling should have kept the result well under the full input size.
    assert len(x_plot) < n
    assert len(x_plot) == len(y_plot) == len(c_plot)
