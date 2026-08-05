"""Compatibility layer for Matplotlib Qt backends."""

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: F401
except ImportError:
    pass
