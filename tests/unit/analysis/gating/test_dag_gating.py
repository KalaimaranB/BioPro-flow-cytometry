"""Tests for DAG Boolean Logic gating."""

import numpy as np
import pandas as pd
import pytest
from biopro_plugins.flow_cytometry.analysis.gating.gate_node import GateNode
from biopro_plugins.flow_cytometry.analysis.gating.polygon import PolygonGate


@pytest.fixture
def dummy_events():
    """Create 10,000 synthetic events."""
    np.random.seed(42)
    return pd.DataFrame(
        {
            "FSC-A": np.random.normal(50000, 10000, 10000),
            "SSC-A": np.random.normal(50000, 10000, 10000),
        }
    )


def test_dag_boolean_and(dummy_events):
    root = GateNode(name="All Events")

    # Gate A: X > 50k
    gate_a = PolygonGate(
        x_param="FSC-A",
        y_param="SSC-A",
        vertices=[(50000, 0), (100000, 0), (100000, 100000), (50000, 100000)],
    )
    node_a = GateNode(gate=gate_a, name="Gate A", parents=[root])
    root.children.append(node_a)

    # Gate B: Y > 50k
    gate_b = PolygonGate(
        x_param="FSC-A",
        y_param="SSC-A",
        vertices=[(0, 50000), (100000, 50000), (100000, 100000), (0, 100000)],
    )
    node_b = GateNode(gate=gate_b, name="Gate B", parents=[root])
    root.children.append(node_b)

    # Logic Node: AND
    node_and = GateNode(name="AND Node", logic_operator="AND", parents=[node_a, node_b])
    node_a.children.append(node_and)
    node_b.children.append(node_and)

    # Evaluate masks using apply_hierarchy
    mask_a = node_a.apply_hierarchy(dummy_events)
    mask_b = node_b.apply_hierarchy(dummy_events)
    mask_and = node_and.apply_hierarchy(dummy_events)

    # The AND node should perfectly match the mathematical intersection
    expected_count = len(pd.merge(mask_a, mask_b, how="inner"))

    # We can just check the dataframe length because apply_hierarchy returns the filtered dataframe
    assert len(mask_and) == expected_count


def test_dag_boolean_or(dummy_events):
    root = GateNode(name="All Events")

    # Gate A: X > 50k
    gate_a = PolygonGate(
        x_param="FSC-A",
        y_param="SSC-A",
        vertices=[(50000, 0), (100000, 0), (100000, 100000), (50000, 100000)],
    )
    node_a = GateNode(gate=gate_a, name="Gate A", parents=[root])
    root.children.append(node_a)

    # Gate B: Y > 50k
    gate_b = PolygonGate(
        x_param="FSC-A",
        y_param="SSC-A",
        vertices=[(0, 50000), (100000, 50000), (100000, 100000), (0, 100000)],
    )
    node_b = GateNode(gate=gate_b, name="Gate B", parents=[root])
    root.children.append(node_b)

    # Logic Node: OR
    node_or = GateNode(name="OR Node", logic_operator="OR", parents=[node_a, node_b])
    node_a.children.append(node_or)
    node_b.children.append(node_or)

    mask_a = node_a.apply_hierarchy(dummy_events)
    mask_b = node_b.apply_hierarchy(dummy_events)
    mask_or = node_or.apply_hierarchy(dummy_events)

    expected_count = len(pd.concat([mask_a, mask_b]).drop_duplicates())
    assert len(mask_or) == expected_count


def test_dag_boolean_not(dummy_events):
    root = GateNode(name="All Events")

    gate_a = PolygonGate(
        x_param="FSC-A",
        y_param="SSC-A",
        vertices=[(50000, 0), (100000, 0), (100000, 100000), (50000, 100000)],
    )
    node_a = GateNode(gate=gate_a, name="Gate A", parents=[root])
    root.children.append(node_a)

    node_not = GateNode(name="NOT Node", logic_operator="NOT", parents=[node_a])
    node_a.children.append(node_not)

    mask_a = node_a.apply_hierarchy(dummy_events)
    mask_not = node_not.apply_hierarchy(dummy_events)

    assert len(mask_not) == len(dummy_events) - len(mask_a)
