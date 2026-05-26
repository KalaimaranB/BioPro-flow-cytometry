"""Unit tests for UmapAnalysis background worker.
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from unittest.mock import MagicMock

from analysis.umap_analysis import UmapAnalysis
from analysis.experiment import Sample
from analysis.fcs_io import FCSData
from analysis.axis_manager import AxisManager
from analysis.state import FlowState


@pytest.fixture
def test_state():
    """Create a fully populated FlowState for UMAP testing."""
    state = FlowState()
    
    # Instantiate actual AxisManager
    state.axis_manager = AxisManager(state, parent=None)
    
    # Construct a sample with real FCSData
    sample = Sample(sample_id="s1", display_name="Sample 1")
    
    # 100 events, 4 channels (2 scatter, 2 fluorescence)
    np.random.seed(42)
    events_df = pd.DataFrame({
        "FSC-A": np.random.rand(100) * 1000,
        "SSC-A": np.random.rand(100) * 1000,
        "FL1-A": np.random.rand(100) * 100,
        "FL2-A": np.random.rand(100) * 100
    })
    
    sample.fcs_data = FCSData(
        file_path=Path("test.fcs"),
        channels=["FSC-A", "SSC-A", "FL1-A", "FL2-A"],
        markers=["", "", "CD4", "CD8"],
        events=events_df
    )
    
    state.experiment.add_sample(sample)
    state.current_sample_id = "s1"
    
    return state


def test_umap_validation_missing_sample(test_state):
    """Verify validation fails if no sample is selected or present."""
    analysis = UmapAnalysis()
    analysis.target_sample_id = "nonexistent"
    
    is_valid, err = analysis.validate(test_state)
    assert not is_valid
    assert "not found" in err


def test_umap_validation_too_few_events(test_state):
    """Verify validation fails if the sample has too few events."""
    sample = test_state.experiment.samples["s1"]
    
    # Re-assign events with only 10 rows
    events_df = pd.DataFrame({
        "FSC-A": np.random.rand(10) * 1000,
        "FL1-A": np.random.rand(10) * 100
    })
    sample.fcs_data = FCSData(
        file_path=Path("test.fcs"),
        channels=["FSC-A", "FL1-A"],
        markers=["", "CD4"],
        events=events_df
    )
    
    analysis = UmapAnalysis()
    analysis.target_sample_id = "s1"
    
    is_valid, err = analysis.validate(test_state)
    assert not is_valid
    assert "too few events" in err


def test_umap_validation_success(test_state):
    """Verify validation passes on a valid loaded sample."""
    analysis = UmapAnalysis()
    analysis.target_sample_id = "s1"
    
    is_valid, err = analysis.validate(test_state)
    assert is_valid
    assert err == ""


def test_umap_run_success(test_state):
    """Verify UMAP runs successfully and returns correct structures."""
    analysis = UmapAnalysis()
    analysis.target_sample_id = "s1"
    analysis.n_events = 50
    analysis.n_neighbors = 5
    analysis.min_dist = 0.1
    analysis.random_seed = 42
    
    # Mock/hook progress signal
    progress_calls = []
    analysis.signals.analysis_progress.connect(progress_calls.append)
    
    # Run
    results = analysis.run(test_state)
    
    # Check results
    assert "error" not in results
    assert results["sample_id"] == "s1"
    assert results["n_events"] == 50
    
    # Embedding must be shape (50, 2)
    embedding = results["embedding"]
    assert isinstance(embedding, np.ndarray)
    assert embedding.shape == (50, 2)
    
    # Output channels list
    assert results["channels"] == ["CD4 (FL1-A)", "CD8 (FL2-A)"]
    
    # Intensities must be (50, 2)
    assert results["intensities"].shape == (50, 2)
    
    # Verify progress was emitted
    assert len(progress_calls) > 0
    assert progress_calls[-1] == 100
