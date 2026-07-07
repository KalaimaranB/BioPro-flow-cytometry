import sys
import time

import pytest
from PyQt6.QtWidgets import QApplication

# Ensure QApplication exists for signal processing
from analysis.axis_manager import AxisManager
from analysis.gate_coordinator import GateCoordinator
from analysis.gate_propagator import GatePropagator
from analysis.population_service import PopulationService

app = QApplication.instance() or QApplication(sys.argv)

# Make debounce instantaneous for tests
GatePropagator.DEBOUNCE_MS = 0


@pytest.fixture
def gate_coordinator(flow_state):
    axis_manager = AxisManager(flow_state)
    pop_service = PopulationService(flow_state)
    from unittest.mock import MagicMock

    mock_scheduler = MagicMock()

    # Mock submit to just run the task synchronously
    def sync_submit(worker, state):
        res = worker.run(state)
        # Check if it's the StatisticsAnalysis worker
        from analysis.statistics_analysis import StatisticsAnalysis

        if isinstance(worker, StatisticsAnalysis):
            # The callback is connected to task_finished signal
            if hasattr(mock_scheduler, "task_finished"):
                mock_scheduler.task_finished.emit("test_task_1", res)
        else:
            # Call the finished signal manually since we aren't using the real scheduler
            controller.propagator._on_propagation_finished("test_task_1", res)
        return MagicMock(task_id="test_task_1")

    mock_scheduler.submit.side_effect = sync_submit
    mock_scheduler.task_finished = MagicMock()

    controller = GateCoordinator(
        flow_state, axis_manager, pop_service, task_scheduler=mock_scheduler
    )
    controller.sync_stats = True
    return controller


def wait_for_propagation(gate_coordinator):
    time.sleep(0.05)
    gate_coordinator.propagator.cleanup()


def test_add_rectangle_gate(gate_coordinator, flow_state, gate_rectangle_singlet):
    sample_id = "test_sample_1"

    # Add a gate
    node_id = gate_coordinator.add_gate(
        gate_rectangle_singlet, sample_id, name="Singlets"
    )

    assert node_id is not None
    sample = flow_state.data.experiment.samples[sample_id]

    # Check tree
    node = sample.gate_tree.find_node_by_id(node_id)
    assert node is not None
    assert node.name == "Singlets"
    assert node.gate == gate_rectangle_singlet

    # Wait for background task to complete
    wait_for_propagation(gate_coordinator)

    # Check stats were computed
    assert "count" in node.statistics
    assert node.statistics["count"] > 0
    assert node.statistics["pct_parent"] <= 100.0


def test_add_quadrant_gate(gate_coordinator, flow_state, gate_quadrant_cd4_cd8):
    sample_id = "test_sample_1"

    gate_coordinator.add_gate(gate_quadrant_cd4_cd8, sample_id)
    wait_for_propagation(gate_coordinator)

    sample = flow_state.data.experiment.samples[sample_id]

    assert len(sample.gate_tree.children) == 4

    labels = [n.name for n in sample.gate_tree.children]
    assert labels == ["Q1", "Q2", "Q3", "Q4"]


def test_modify_gate(gate_coordinator, flow_state, gate_rectangle_singlet):
    sample_id = "test_sample_1"
    node_id = gate_coordinator.add_gate(
        gate_rectangle_singlet, sample_id, name="Singlets"
    )

    wait_for_propagation(gate_coordinator)

    sample = flow_state.data.experiment.samples[sample_id]
    node = sample.gate_tree.find_node_by_id(node_id)

    orig_count = node.statistics.get("count", 0)

    # Modify gate to be much smaller
    success = gate_coordinator.modify_gate(
        gate_rectangle_singlet.gate_id,
        sample_id,
        x_min=100_000,
        x_max=110_000,
        y_min=80_000,
        y_max=90_000,
    )

    assert success is True
    assert gate_rectangle_singlet.x_min == 100_000

    wait_for_propagation(gate_coordinator)

    # Check stats updated
    new_count = node.statistics["count"]
    assert new_count < orig_count


def test_remove_population(gate_coordinator, flow_state, gate_rectangle_singlet):
    sample_id = "test_sample_1"
    node_id = gate_coordinator.add_gate(
        gate_rectangle_singlet, sample_id, name="Singlets"
    )

    wait_for_propagation(gate_coordinator)

    success = gate_coordinator.remove_population(sample_id, node_id)
    assert success is True

    sample = flow_state.data.experiment.samples[sample_id]
    assert sample.gate_tree.find_node_by_id(node_id) is None


def test_rename_population(gate_coordinator, flow_state, gate_rectangle_singlet):
    sample_id = "test_sample_1"
    node_id = gate_coordinator.add_gate(
        gate_rectangle_singlet, sample_id, name="Singlets"
    )

    success = gate_coordinator.rename_population(sample_id, node_id, "New Name")
    assert success is True

    wait_for_propagation(gate_coordinator)

    sample = flow_state.data.experiment.samples[sample_id]
    node = sample.gate_tree.find_node_by_id(node_id)
    assert node.name == "New Name"


def test_split_population(gate_coordinator, flow_state, gate_rectangle_singlet):
    sample_id = "test_sample_1"
    node_id = gate_coordinator.add_gate(
        gate_rectangle_singlet, sample_id, name="Singlets"
    )

    wait_for_propagation(gate_coordinator)

    sibling_id = gate_coordinator.split_population(sample_id, node_id)
    assert sibling_id is not None

    wait_for_propagation(gate_coordinator)

    sample = flow_state.data.experiment.samples[sample_id]
    sibling = sample.gate_tree.find_node_by_id(sibling_id)

    assert sibling is not None
    assert sibling.negated is True
    assert sibling.name == "Singlets (Outside)"
