"""Regression tests for FlowCanvas's post-deletion CentralEventBus guards.

CentralEventBus.publish() is queued through the Qt event loop, so an event
published just before a graph tab (and its FlowCanvas) closes can still be
delivered afterwards. The controller-event handlers guard against this with
`sip.isdeleted(self)`, but PyQt6 exposes that module as `PyQt6.sip`, not a
top-level `sip` package — a bare `import sip` raises ModuleNotFoundError as
soon as any of these handlers actually fire, which is worse than having no
guard at all. These tests would have failed with that ModuleNotFoundError
before the fix.
"""

import pytest
from PyQt6 import sip

from biopro_plugins.flow_cytometry.ui.graph.flow_canvas import FlowCanvas

_HANDLERS = [
    ("_on_controller_geometry_changed", ("s1", "gate1")),
    ("_on_controller_selected", ("s1", "node1")),
    ("_on_controller_gate_removed", ("s1", "node1")),
    ("_on_controller_gate_renamed", ("s1", "node1")),
]


@pytest.mark.ui
@pytest.mark.parametrize("handler_name,args", _HANDLERS)
def test_controller_handler_is_noop_after_canvas_deleted(qtbot, handler_name, args):
    canvas = FlowCanvas(parent=None)
    canvas._sample_id = "s1"
    # Not registered with qtbot: sip.delete() below destroys the C++ side
    # immediately, and qtbot's own teardown calling .close() on an
    # already-deleted widget would itself raise.

    sip.delete(canvas)
    assert sip.isdeleted(canvas)

    handler = getattr(canvas, handler_name)
    # Must return quietly (no ModuleNotFoundError, no RuntimeError touching
    # deleted C++ state) instead of raising.
    handler(*args)


@pytest.mark.ui
@pytest.mark.parametrize("handler_name,args", _HANDLERS)
def test_controller_handler_still_runs_while_canvas_is_alive(qtbot, handler_name, args):
    """Sanity check: the isdeleted guard must not swallow the live-object case."""
    canvas = FlowCanvas(parent=None)
    canvas._sample_id = "s1"
    qtbot.addWidget(canvas)

    assert not sip.isdeleted(canvas)
    handler = getattr(canvas, handler_name)
    handler(*args)  # should not raise for a live canvas either
