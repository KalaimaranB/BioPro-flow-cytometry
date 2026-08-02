"""Unit tests for fcs_io.py."""

from pathlib import Path

import pandas as pd
import pytest
from biopro_plugins.flow_cytometry.analysis.fcs_io import (
    FCSData,
    _auto_apply_spill,
    load_fcs,
)


def test_fcs_data_dataclass():
    data = FCSData(
        file_path=Path("sample.fcs"),
        channels=["FSC-A", "SSC-A"],
        markers=["", ""],
        events=pd.DataFrame([[100.0, 200.0]], columns=["FSC-A", "SSC-A"]),
        raw_events=pd.DataFrame([[100.0, 200.0]], columns=["FSC-A", "SSC-A"]),
    )
    assert data.num_events == 1
    assert data.num_channels == 2


def test_auto_apply_spill():
    events_df = pd.DataFrame([[1000.0, 500.0]], columns=["FL1-A", "FL2-A"])
    metadata = {"$SPILLOVER": "2,FL1-A,FL2-A,1.0,0.1,0.05,1.0"}
    applied = _auto_apply_spill("sample.fcs", events_df, metadata)
    assert applied is True
    assert events_df.shape == (1, 2)


def test_load_fcs_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_fcs("non_existent_file.fcs")
