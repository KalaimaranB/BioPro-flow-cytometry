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
