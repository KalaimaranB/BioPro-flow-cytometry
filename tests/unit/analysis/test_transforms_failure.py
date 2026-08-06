"""Tests for the no-fallback failure behavior of the biexponential (Logicle) transform.

There used to be a resilience chain here: FlowKit's LogicleTransform -> flowutils
directly -> an arcsinh approximation. That was removed deliberately: an approximation
silently substitutes a mathematically different formula (arcsinh treats "width"
differently), producing a plausible-looking but numerically wrong plot with no visible
sign anything went wrong -- exactly the failure mode that let the Windows bokeh/frozen
bundle bug hide for so long. FlowKit failing to import or apply now must (a) report a
fatal diagnostic and (b) propagate the exception, not return a silently-wrong array.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import numpy as np
import pytest

from biopro_plugins.flow_cytometry.analysis import transforms


def _seed_fake_diagnostics(monkeypatch) -> MagicMock:
    """Register a fake `biopro.core.diagnostics` module so the plugin's lazy
    `from biopro.core.diagnostics import diagnostics` import resolves to a mock,
    without requiring the real BioPro core app to be installed.
    """
    mock_diagnostics = MagicMock()
    fake_diagnostics_module = types.ModuleType("biopro.core.diagnostics")
    fake_diagnostics_module.diagnostics = mock_diagnostics  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "biopro", types.ModuleType("biopro"))
    monkeypatch.setitem(sys.modules, "biopro.core", types.ModuleType("biopro.core"))
    monkeypatch.setitem(sys.modules, "biopro.core.diagnostics", fake_diagnostics_module)
    return mock_diagnostics


@pytest.fixture(autouse=True)
def _reset_warning_flag(monkeypatch):
    monkeypatch.setattr(transforms, "_flowkit_logicle_warning_issued", False)


@pytest.mark.unit
class TestBiexponentialTransformNoFallback:
    def test_uses_real_flowkit_and_reports_nothing(self, monkeypatch):
        """The primary (only) path: FlowKit succeeds, no diagnostic is reported."""
        mock_diagnostics = _seed_fake_diagnostics(monkeypatch)

        data = np.array([-500.0, 0.0, 1.0, 100.0, 10_000.0, 200_000.0])
        result = transforms.biexponential_transform(data)

        assert result.shape == data.shape
        assert np.all(np.isfinite(result))
        mock_diagnostics.report_error.assert_not_called()

    def test_import_failure_reports_fatal_and_raises(self, monkeypatch):
        """`import flowkit` failing must be loud and must not return a value."""
        mock_diagnostics = _seed_fake_diagnostics(monkeypatch)

        # sys.modules[name] = None makes `import name` raise ImportError — this
        # simulates flowkit (or its bokeh dependency) failing to import, the exact
        # condition seen on Windows.
        monkeypatch.setitem(sys.modules, "flowkit", None)

        with pytest.raises(ImportError):
            transforms.biexponential_transform(np.array([1.0, 100.0]))

        mock_diagnostics.report_error.assert_called_once()
        _, kwargs = mock_diagnostics.report_error.call_args
        assert kwargs.get("fatal") is True

    def test_apply_failure_reports_fatal_and_raises(self, monkeypatch):
        """FlowKit importing fine but the transform itself failing must also be loud."""
        mock_diagnostics = _seed_fake_diagnostics(monkeypatch)

        def _boom(*_args, **_kwargs):
            raise RuntimeError("LogicleTransform.apply exploded")

        monkeypatch.setattr(transforms, "_get_logicle_transform", _boom)

        with pytest.raises(RuntimeError, match="exploded"):
            transforms.biexponential_transform(np.array([1.0, 100.0]))

        mock_diagnostics.report_error.assert_called_once()
        _, kwargs = mock_diagnostics.report_error.call_args
        assert kwargs.get("fatal") is True

    def test_no_arcsinh_fallback_symbol_remains(self):
        """Guard against the fallback chain quietly being reintroduced.

        Checks for actual fallback *usage*, not the word "flowutils" — that still
        legitimately appears in the docstring describing what FlowKit wraps.
        """
        import inspect

        source = inspect.getsource(transforms.biexponential_transform)
        assert "np.arcsinh" not in source
        assert "flowutils.transforms" not in source


@pytest.mark.unit
class TestInvertBiexponentialTransformNoFallback:
    def test_uses_real_flowkit_and_reports_nothing(self, monkeypatch):
        mock_diagnostics = _seed_fake_diagnostics(monkeypatch)

        data = np.array([0.0, 0.2, 0.5, 0.8, 1.0])
        result = transforms.invert_biexponential_transform(data)

        assert result.shape == data.shape
        assert np.all(np.isfinite(result))
        mock_diagnostics.report_error.assert_not_called()

    def test_apply_failure_reports_fatal_and_raises(self, monkeypatch):
        mock_diagnostics = _seed_fake_diagnostics(monkeypatch)

        def _boom(*_args, **_kwargs):
            raise RuntimeError("LogicleTransform.inverse exploded")

        monkeypatch.setattr(transforms, "_get_logicle_transform", _boom)

        with pytest.raises(RuntimeError, match="exploded"):
            transforms.invert_biexponential_transform(np.array([0.1, 0.5]))

        mock_diagnostics.report_error.assert_called_once()
        _, kwargs = mock_diagnostics.report_error.call_args
        assert kwargs.get("fatal") is True
