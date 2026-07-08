"""Flow Cytometry Workspace — BioPro plugin entry point.

A scientist-centric flow cytometry analysis environment with workspace-based
navigation, FMO-guided gating, adaptive gates, and reusable workflow templates.
"""

__version__ = "0.1.3"
__plugin_id__ = "flow_cytometry"
import os
import sys

# Ensure the plugin's root directory is in sys.path so absolute imports like 'from analysis import ...' work
plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

# ── BioPro metadata shim ──────────────────────────────────────────────────────
# BioPro Core installs each dependency into a separate --target directory
# (e.g. ~/.biopro/cache/packages/bokeh_3.0).  It adds those dirs to sys.path
# so the actual package code is importable, but importlib.metadata searches
# sys.path for *.dist-info directories.  Some packages (e.g. bokeh) call
# importlib.metadata.version("bokeh") in their own __init__.py, which fails
# with "No package metadata was found" because the .dist-info lives in the
# --target dir which may not be on sys.path.
#
# Fix: scan the BioPro package cache and register every target dir that
# contains a .dist-info directory with importlib.metadata's path list.
try:
    import pathlib as _pathlib

    _biopro_cache = _pathlib.Path.home() / ".biopro" / "cache" / "packages"
    if _biopro_cache.is_dir():
        for _pkg_target in _biopro_cache.iterdir():
            if _pkg_target.is_dir():
                _target_str = str(_pkg_target)
                # Add the target dir to sys.path if any .dist-info lives there
                if any(_pkg_target.glob("*.dist-info")):
                    if _target_str not in sys.path:
                        sys.path.insert(0, _target_str)
except Exception:
    pass  # Never crash plugin boot over metadata path setup
# ─────────────────────────────────────────────────────────────────────────────


def get_panel_class():
    """Returns the main QWidget class that should be injected into the UI.

    Standard BioPro entry point.  The core ``ModuleManager`` calls this
    function to obtain the class (not an instance) and then instantiates it
    into the central workspace container.
    """
    # Pre-warm numba JIT in the background so the first UMAP run doesn't freeze.
    from .analysis.numba_warmup import warmup_numba_jit

    warmup_numba_jit()

    from biopro.core.tutorial_manager import global_tutorial_manager

    from .tutorials.courses import (
        course_1_fundamentals,
        course_2_gating,
        course_3_analysis,
    )

    global_tutorial_manager.register_storyboard(__plugin_id__, course_1_fundamentals)
    global_tutorial_manager.register_storyboard(__plugin_id__, course_2_gating)
    global_tutorial_manager.register_storyboard(__plugin_id__, course_3_analysis)

    from .ui.main_panel import FlowCytometryPanel

    return FlowCytometryPanel


def cleanup():
    """Module-level cleanup."""
    pass


def shutdown():
    """Module-level shutdown."""
    pass
