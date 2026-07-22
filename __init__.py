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
    pass


def shutdown():
    """Module-level shutdown."""
    pass
