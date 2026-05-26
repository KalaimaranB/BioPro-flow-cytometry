"""Gate hierarchy package — icicle chart redesign.

Public API (backward-compatible with the old gate_hierarchy.py):
    from flow_cytometry.ui.widgets.gate_hierarchy import GateHierarchy
"""

from .widget import GateHierarchy

__all__ = ["GateHierarchy"]
