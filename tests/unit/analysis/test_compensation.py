import numpy as np
import pandas as pd

from biopro_plugins.flow_cytometry.analysis.compensation import CompensationMatrix


def test_compensation_matrix_init():
    detectors = ["FITC-A", "PE-A", "APC-A"]
    matrix = np.eye(3)
    comp = CompensationMatrix(matrix=matrix, channel_names=detectors)

    assert comp.channel_names == detectors
    assert comp.matrix.shape == (3, 3)
    assert comp.inverse.shape == (3, 3)


def test_calculate_spillover_matrix():
    from pathlib import Path

    from biopro_plugins.flow_cytometry.analysis.compensation import (
        calculate_spillover_matrix,
    )

    class MockFCS:
        def __init__(self, events):
            self.events = events
            self.file_path = Path("mock.fcs")

    # FITC Single stain: high FITC, slight spillover into PE (10%)
    ss_fitc = MockFCS(
        pd.DataFrame({"FITC-A": [10000.0, 10000.0, 10000.0], "PE-A": [1000.0, 1000.0, 1000.0]})
    )

    # PE Single stain: high PE, slight spillover into FITC (5%)
    ss_pe = MockFCS(
        pd.DataFrame({"FITC-A": [500.0, 500.0, 500.0], "PE-A": [10000.0, 10000.0, 10000.0]})
    )

    comp = calculate_spillover_matrix(
        single_stains=[ss_fitc, ss_pe],
        unstained=None,
        fluorescence_channels=["FITC-A", "PE-A"],
    )

    assert comp.channel_names == ["FITC-A", "PE-A"]
    # FITC row: FITC=1.0, PE=0.1
    # PE row: FITC=0.05, PE=1.0
    expected_matrix = np.array([[1.0, 0.1], [0.05, 1.0]])
    assert np.allclose(comp.matrix, expected_matrix)
    assert comp.source == "computed"


def test_compensation_apply():
    detectors = ["FITC-A", "PE-A"]
    # 10% spillover from PE to FITC because row @ M^-1 combines columns
    matrix = np.array([[1.0, 0.0], [0.1, 1.0]])
    comp = CompensationMatrix(matrix=matrix, channel_names=detectors)

    class MockFCS:
        def __init__(self, events):
            self.events = events

    events = pd.DataFrame(
        {
            "FITC-A": [100.0, 1000.0],
            "PE-A": [1000.0, 0.0],
            "FSC-A": [50000.0, 50000.0],  # Uncompensated channel
        }
    )

    from biopro_plugins.flow_cytometry.analysis.compensation import apply_compensation

    comp_events = apply_compensation(MockFCS(events), comp)

    # FITC = Raw_FITC - 0.1 * PE -> 100 - 100 = 0
    assert np.isclose(comp_events["FITC-A"].iloc[0], 0.0)
    assert np.isclose(comp_events["PE-A"].iloc[0], 1000.0)

    # Uncompensated channels pass through unchanged
    assert np.isclose(comp_events["FSC-A"].iloc[0], 50000.0)


def test_parse_spillover():
    from biopro_plugins.flow_cytometry.analysis.compensation import (
        extract_spill_from_fcs,
    )

    class MockFCSData:
        def __init__(self):
            self.metadata = {"$SPILLOVER": "2,FITC-A,PE-A,1.0,0.0,0.1,1.0"}

    comp = extract_spill_from_fcs(MockFCSData())

    assert comp.channel_names == ["FITC-A", "PE-A"]
    assert np.allclose(comp.matrix, [[1.0, 0.0], [0.1, 1.0]])


def test_compensation_to_dict():
    detectors = ["FITC-A", "PE-A"]
    matrix = np.array([[1.0, 0.0], [0.1, 1.0]])
    comp = CompensationMatrix(matrix=matrix, channel_names=detectors)

    d = comp.to_dict()
    assert d["channel_names"] == detectors
    assert d["matrix"] == matrix.tolist()

    comp2 = CompensationMatrix.from_dict(d)
    assert comp2.channel_names == comp.channel_names
    assert np.allclose(comp2.matrix, comp.matrix)
