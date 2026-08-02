"""Flow Cytometry Workspace — BioPro plugin entry point.

A scientist-centric flow cytometry analysis environment with workspace-based
navigation, FMO-guided gating, adaptive gates, and reusable workflow templates.
"""

__version__ = "0.8.0.6"
__plugin_id__ = "flow_cytometry"
import os

# CRITICAL FIX: Prevent OpenBLAS/MKL from spawning their own thread pools inside
# Qt's QThreadPool worker threads. Worker threads have small stacks, and nested
# BLAS parallelization (e.g. numpy.linalg.inv in KDE/FMO) causes stack overflows
# (EXC_BAD_ACCESS / SIGBUS) on macOS.
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"


def register_courses(manager):
    from .tutorials.courses import (
        course_1_fundamentals,
        course_2_gating,
        course_3_analysis,
    )

    # Prevent duplicate registration
    if __plugin_id__ not in manager.courses_by_module or not any(
        c.id == course_1_fundamentals.id
        for c in manager.courses_by_module[__plugin_id__]
    ):
        manager.register_storyboard(__plugin_id__, course_1_fundamentals)
        manager.register_storyboard(__plugin_id__, course_2_gating)
        manager.register_storyboard(__plugin_id__, course_3_analysis)


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

    register_courses(global_tutorial_manager)

    from .ui.main_panel import FlowCytometryPanel

    return FlowCytometryPanel


def cleanup():
    """Module-level cleanup."""


def shutdown():
    """Module-level shutdown."""


from biopro_sdk.plugin.context import PluginContext  # noqa: E402


def initialize(context: PluginContext):
    """V3 Plugin Entry Point."""
    logger = context.get("logger")
    logger.info("Initializing Flow Cytometry Workspace with PluginContext")
    # In V2, get_panel_class() was called directly. Here we can instantiate the panel
    # or return a wrapper that the core uses.
    try:
        panel_class = get_panel_class()
        # You may want to pass context to the panel here in the future
        return panel_class
    except NameError:
        logger.warning("get_panel_class not found in __init__.py")
        return None
