import os
import sys
import types

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_repo_root, "src"))


from unittest.mock import MagicMock  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from biopro_plugins.flow_cytometry.analysis.experiment import (  # noqa: E402
    Experiment,
    Sample,
)
from biopro_plugins.flow_cytometry.analysis.state import FlowState  # noqa: E402
from PyQt6.QtWidgets import QLabel, QPushButton, QSplitter, QWidget  # noqa: E402

# Mock biopro_sdk before it gets imported
mock_biopro_sdk_plugin = MagicMock()


class DummyTaskBase:
    def __init__(self, *args, **kwargs):
        pass


from PyQt6.QtCore import pyqtSignal  # noqa: E402


class DummyPluginBase(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.plugin_id = kwargs.get("plugin_id", args[0] if args else "")


class DummyAnalysisBase:
    def __init__(self, *args, **kwargs):
        self.plugin_id = kwargs.get("plugin_id", args[0] if args else "")
        self.signals = MagicMock()
        self._is_cancelled = False

    def is_cancelled(self):
        return self._is_cancelled


class DummyButton(QPushButton):
    def setHelpText(self, text: str, title: str = "") -> None:
        pass

    def _apply_theme_styles(self) -> None:
        pass


class DummySplitter(QSplitter):
    pass


class DummyLabel(QLabel):
    pass


from PyQt6.QtWidgets import QComboBox, QLineEdit, QListWidget, QSpinBox  # noqa: E402


class DummyComboBox(QComboBox):
    pass


class DummyLineEdit(QLineEdit):
    pass


class DummyListWidget(QListWidget):
    pass


class DummySpinBox(QSpinBox):
    pass


from biopro_sdk.plugin.daemon import PluginDaemon  # noqa: E402

mock_biopro_sdk_plugin.PluginBase = DummyPluginBase
mock_biopro_sdk_plugin.PluginDaemon = PluginDaemon
mock_biopro_sdk_plugin.AnalysisBase = DummyAnalysisBase
mock_biopro_sdk_plugin.PluginState = DummyAnalysisBase
mock_biopro_sdk_plugin.validate_file_exists = lambda path: (True, "")

mock_tasks = MagicMock()
mock_tasks.TaskBase = DummyTaskBase
mock_biopro_sdk_plugin.tasks = mock_tasks
sys.modules["biopro_sdk.plugin.tasks"] = mock_tasks


class MockComponents:
    pass


mock_components = MockComponents()
mock_components.PrimaryButton = DummyButton
mock_components.SecondaryButton = DummyButton
mock_components.BioSplitter = DummySplitter
mock_components.BioCaptionLabel = DummyLabel
mock_components.BioComboBox = DummyComboBox
mock_components.BioRunButton = DummyButton
mock_components.BioCancelButton = DummyButton
mock_components.BioStatusLabel = DummyLabel
mock_components.BioLineEdit = DummyLineEdit
mock_components.BioListWidget = DummyListWidget
mock_components.BioToggleButton = DummyButton
mock_components.BioSpinBox = DummySpinBox
mock_components.BioHelpButton = DummyButton
mock_components.theme_manager = MagicMock()
mock_biopro_sdk_plugin.components = mock_components

sys.modules["biopro_sdk"] = MagicMock()
sys.modules["biopro_sdk.plugin"] = mock_biopro_sdk_plugin
sys.modules["biopro_sdk.plugin.components"] = mock_components
sys.modules["biopro_sdk.plugin.events"] = MagicMock()
sys.modules["biopro_sdk.plugin.workflow"] = MagicMock()

# Mock biopro core and UI as well
mock_biopro = MagicMock()
if "biopro" not in sys.modules or not isinstance(
    sys.modules["biopro"], types.ModuleType
):
    sys.modules["biopro"] = mock_biopro
else:
    mock_ui = MagicMock()
    sys.modules["biopro.ui"] = mock_ui
    sys.modules["biopro"].ui = mock_ui
    sys.modules["biopro_plugins.flow_cytometry"].ui = mock_ui


class DummyThemeMeta(type):
    def __getattr__(cls, name):
        if name.startswith("SIZE"):
            return "12"
        return "#000000"


class DummyColors(metaclass=DummyThemeMeta):
    pass


class DummyFonts(metaclass=DummyThemeMeta):
    pass


mock_theme = MagicMock()
mock_theme.Colors = DummyColors
mock_theme.Fonts = DummyFonts
sys.modules["biopro.ui.theme"] = mock_theme
sys.modules["biopro.core"] = MagicMock()
sys.modules["biopro.core.task_scheduler"] = MagicMock()
sys.modules["biopro.shared"] = MagicMock()
sys.modules["biopro.shared.ui"] = MagicMock()
sys.modules["biopro.shared.ui.ui_components"] = mock_components


from .fixtures import *  # noqa: F403, E402


@pytest.fixture
def empty_state():
    """Returns a fresh FlowState with an empty experiment."""
    state = FlowState()
    state.data.experiment = Experiment()
    return state


@pytest.fixture
def sample_data():
    """Returns a dummy FCS DataFrame."""
    return pd.DataFrame(
        {
            "FSC-A": np.random.rand(1000) * 1024,
            "SSC-A": np.random.rand(1000) * 1024,
            "FL1-A": np.random.rand(1000) * 100,
        }
    )


@pytest.fixture
def sample_with_data(sample_data):
    """Returns a Sample object populated with dummy data."""
    sample = Sample(sample_id="s1", display_name="Sample 1")
    sample.fcs_data = MagicMock()
    sample.fcs_data.events = sample_data
    return sample


@pytest.fixture
def state_with_sample(empty_state, sample_with_data):
    """Returns a FlowState with one sample loaded."""
    empty_state.experiment.samples[sample_with_data.sample_id] = sample_with_data
    return empty_state
