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


def _purge_flowkit_bokeh_state() -> None:
    """Force flowkit/bokeh to be re-imported from scratch on the next `import`.

    Also clears bokeh's own `get_env()` lru_cache — it's a process-lifetime cache
    keyed on nothing (a bare `@lru_cache(None)` on a zero-arg function), so a
    previous test (or a previous production call) succeeding once would otherwise
    make every later call return the same cached Environment regardless of
    sys.frozen/_MEIPASS, silently defeating the whole point of these tests.
    """
    import bokeh.core.templates as bokeh_templates

    bokeh_templates.get_env.cache_clear()
    for name in list(sys.modules):
        if (
            name == "flowkit"
            or name.startswith("flowkit.")
            or name == "bokeh"
            or name.startswith("bokeh.")
        ):
            del sys.modules[name]


@pytest.mark.unit
class TestFrozenEnvironmentSimulation:
    """Regression coverage for the actual bug: bokeh's `get_env()` (imported as a
    side effect of `import flowkit`) checks `sys.frozen`/`sys._MEIPASS` globally to
    decide where its own Jinja2 templates live, wrongly assuming that if the
    *process* is frozen, bokeh itself must be bundled at the PyInstaller standard
    location. It never is here — bokeh lives in this plugin's own separate,
    non-frozen `.venv`. This is what actually broke on Windows; none of the
    dependency-resolution fixes (module shadowing, sys.path priority) touch it,
    because the *right* bokeh was always being imported — bokeh's own internal
    logic was just looking in the wrong place regardless.

    This needs no PyInstaller build, no frozen executable, and no CI `build` job —
    it reproduces the real condition directly and runs in milliseconds.
    """

    @pytest.fixture(autouse=True)
    def _isolate_module_state(self):
        _purge_flowkit_bokeh_state()
        yield
        # Leave a *correctly* primed cache behind for any other test that imports
        # flowkit/bokeh afterward in the same session. Don't rely on monkeypatch's
        # teardown having already run by this point (fixture teardown order isn't
        # guaranteed relative to a same-test monkeypatch fixture) — just make
        # `sys.frozen` falsy directly; that alone is enough to take the correct
        # branch in bokeh's get_env(), regardless of whether _MEIPASS is still
        # set (monkeypatch will clean that up on its own schedule).
        sys.frozen = False  # type: ignore[attr-defined]
        _purge_flowkit_bokeh_state()
        import flowkit  # noqa: F401

    def test_simulated_frozen_state_reproduces_the_real_bug_when_unguarded(self, monkeypatch):
        """Proves the test condition itself is real, not a vacuous simulation.

        A bare `import flowkit`, with no frozen-state handling at all, must still
        fail under the simulated condition — otherwise this whole test class
        wouldn't actually be testing anything.
        """
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/nonexistent_meipass", raising=False)

        with pytest.raises(Exception, match="file.html.jinja"):
            import flowkit  # noqa: F401

    def test_biexponential_transform_survives_simulated_frozen_state(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/nonexistent_meipass", raising=False)

        result = transforms.biexponential_transform(np.array([1.0, 100.0, 10_000.0]))

        assert result.shape == (3,)
        assert np.all(np.isfinite(result))

    def test_invert_biexponential_transform_survives_simulated_frozen_state(self, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/nonexistent_meipass", raising=False)

        result = transforms.invert_biexponential_transform(np.array([0.1, 0.5]))

        assert result.shape == (2,)
        assert np.all(np.isfinite(result))

    def test_warmup_primes_cache_correctly_despite_simulated_frozen_state(self, monkeypatch):
        """Directly tests `warmup_flowkit_bokeh`'s worker: prime while "frozen",
        then confirm a raw (unwrapped) bokeh template load succeeds afterward —
        proving the lru_cache now holds the correct, real templates path.
        """
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/nonexistent_meipass", raising=False)

        transforms._do_flowkit_bokeh_warmup()

        import bokeh.core.templates as bokeh_templates

        env = bokeh_templates.get_env()
        assert env.get_template("file.html.jinja") is not None
