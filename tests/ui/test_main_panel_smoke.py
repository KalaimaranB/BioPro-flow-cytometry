import sys

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Create a QApplication instance for UI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_main_panel_initialization(qapp, qtbot):
    """Smoke test: Verify FlowCytometryPanel can be instantiated without crashing.

    This catches AttributeErrors in signal wiring and initialization logic.
    """
    # We don't need a real Karcytics environment for this smoke test,
    # just the widget itself.
    try:
        from PyQt6.QtWidgets import QWidget

        class DummyPluginBase(QWidget):
            def __init__(self, *args, **kwargs):
                super().__init__()
                self.plugin_id = kwargs.get("plugin_id", args[0] if args else "")

        from karcytics_plugins.flow_cytometry.ui.main_panel import FlowCytometryPanel

        panel = FlowCytometryPanel(plugin_id="flow_smoke_test")
        qtbot.addWidget(panel)
        assert panel is not None
        assert panel.state is not None
        assert hasattr(panel, "_gate_controller")
    except Exception as e:
        pytest.fail(f"FlowCytometryPanel failed to initialize: {e}")


def test_gate_modified_pushes_undo_and_dirty_flag(qapp, qtbot):
    """A gate edit (GATE_MODIFIED) must coalesce to exactly one undo
    snapshot + dirty-flag set, same as GATE_CREATED/GATE_DELETED/GATE_RENAMED
    — this was a gap: modify_gate() previously had no callers, so nothing
    ever exercised whether editing a gate was undoable.

    Exercises MainPanelController.wire() directly against a mock panel
    (real FlowCytometryPanel construction runs `_wire_signals()` only as the
    last step of an async, PluginLoaderManager-driven Phase 2 build — not
    worth dragging into a targeted wiring test).
    """
    from unittest.mock import Mock

    from karcytics_plugins.flow_cytometry.analysis import events
    from karcytics_plugins.flow_cytometry.ui.controllers.main_panel_controller import (
        MainPanelController,
    )

    panel = Mock()
    panel._loading = False
    MainPanelController.wire(panel)

    matches = [cb for topic, cb in panel._subscriptions if topic == events.GATE_MODIFIED]
    assert len(matches) == 1, "GATE_MODIFIED must be subscribed exactly once"

    panel.push_state.reset_mock()
    panel.set_dirty.reset_mock()

    matches[0]({"sample_id": "s1", "gate_id": "g1"})

    panel.push_state.assert_called_once()
    panel.set_dirty.assert_called_once_with(True)


def test_graph_manager_initialization(qapp, qtbot, flow_state):
    """Smoke test: Verify GraphManager and GraphWindow initialization."""
    from karcytics_plugins.flow_cytometry.ui.graph.graph_manager import GraphManager

    try:
        from unittest.mock import MagicMock

        mock_controller = MagicMock()
        mock_controller.get_gates_for_display.return_value = ([], [])
        manager = GraphManager(flow_state, None, MagicMock(), mock_controller)
        qtbot.addWidget(manager)

        # Test opening a graph
        sample_id = "test_sample_1"
        manager.open_graph_for_sample(sample_id)

        assert manager._tabs.count() == 1
        graph = manager._tabs.widget(0)
        assert graph is not None
        assert graph.sample_id == sample_id
    except Exception as e:
        pytest.fail(f"GraphManager failed to open graph: {e}")


def test_group_preview_panel_initialization(qapp, qtbot, flow_state):
    """Smoke test: Verify GroupPreviewPanel can rebuild its grid."""
    from karcytics_plugins.flow_cytometry.ui.widgets.group_preview import GroupPreviewPanel

    try:
        from unittest.mock import MagicMock

        panel = GroupPreviewPanel(flow_state, "test_sample_1", MagicMock(), MagicMock())
        qtbot.addWidget(panel)

        # Add another sample to ensure there are peers to preview
        from karcytics_plugins.flow_cytometry.analysis.experiment import Sample

        flow_state.data.experiment.samples["test_sample_2"] = Sample(
            sample_id="test_sample_2",
            display_name="Sample 2",
        )

        # Set context to trigger rebuild
        sample_id = "test_sample_1"
        panel.update_context(sample_id, None)
        panel._rebuild()

        assert len(panel._thumbnails) > 0
    except Exception as e:
        pytest.fail(f"GroupPreviewPanel failed: {e}")
