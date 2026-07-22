def test_state_serialization_avoids_recursive_objects(flow_state):
    """Verify that to_dict() handles non-serializable fields like EventBus."""
    data = flow_state.to_dict()
    assert isinstance(data, dict)
    assert "event_bus" not in data
    assert "data" in data
    assert "view" in data
    assert "experiment" in data["data"]


def test_state_active_params(flow_state):
    flow_state.view.active_x_param = "FSC-A"
    flow_state.view.active_y_param = "SSC-A"
    assert flow_state.view.active_x_param == "FSC-A"
    assert flow_state.view.active_y_param == "SSC-A"


def test_render_config_serialization(flow_state):
    from biopro.plugins.flow_cytometry.analysis.config import (
        PseudocolorConfig,
        RenderConfig,
    )

    custom_config = RenderConfig(
        pseudocolor=PseudocolorConfig(max_events=42000, population_detail=3.5)
    )
    flow_state.view.render_config = custom_config

    workflow_dict = flow_state.to_dict()
    assert "view" in workflow_dict
    assert "render_config" in workflow_dict["view"]
    assert workflow_dict["view"]["render_config"]["pseudocolor"]["max_events"] == 42000
    assert (
        workflow_dict["view"]["render_config"]["pseudocolor"]["population_detail"]
        == 3.5
    )

    # Test round trip
    new_state = type(flow_state)()
    new_state = new_state.from_dict(workflow_dict)
    assert new_state.view.render_config.max_events == 42000
    assert new_state.view.render_config.nbins_scaling == 3.5
