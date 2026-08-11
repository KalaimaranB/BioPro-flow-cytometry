"""Smoke test: StatisticsExplorer wires correctly to the shared
SampleAndPopulationSelector (Phase 3 refactor) instead of its own duplicated
sample/population checklist.
"""

import pytest

from biopro_plugins.flow_cytometry.analysis.experiment import Sample
from biopro_plugins.flow_cytometry.analysis.state import FlowState
from biopro_plugins.flow_cytometry.ui.widgets.statistics_explorer import StatisticsExplorer


@pytest.fixture
def flow_state_with_samples():
    state = FlowState()
    for sid in ("s1", "s2"):
        sample = Sample(sample_id=sid, display_name=sid)
        sample.gate_tree.add_child(None, name="Lymphocytes")
        state.data.experiment.samples[sid] = sample
    return state


@pytest.mark.ui
def test_statistics_explorer_constructs_and_refreshes(qtbot, flow_state_with_samples):
    widget = StatisticsExplorer(flow_state_with_samples)
    qtbot.addWidget(widget)

    assert set(widget._selector.get_checked_sample_ids()) == {"s1", "s2"}
    labels = {label for _sid, _nid, label in widget._selector.get_checked_populations()}
    assert "All Events" in labels
    assert "Lymphocytes" in labels


@pytest.mark.ui
def test_refresh_samples_updates_selector(qtbot, flow_state_with_samples):
    widget = StatisticsExplorer(flow_state_with_samples)
    qtbot.addWidget(widget)

    new_sample = Sample(sample_id="s3", display_name="s3")
    flow_state_with_samples.data.experiment.samples["s3"] = new_sample
    widget.refresh_samples()

    assert "s3" in widget._selector.get_checked_sample_ids()
