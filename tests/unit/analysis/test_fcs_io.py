import shutil
import sys
import types
from pathlib import Path

import biopro_sdk.plugin

from analysis.fcs_io import load_fcs, _prepare_runtime_for_flowkit_import


class DummySample:
    def __init__(self):
        self.channels = {"pnn": ["FSC-A"], "pns": [""]}
        self.metadata = {}

    def get_events(self, source="raw"):
        return [[1.0]]


def test_prepare_runtime_for_flowkit_import_clears_cached_modules(monkeypatch):
    """FlowKit import prep should clear cached app-bundle modules so plugin env wins."""
    monkeypatch.setitem(sys.modules, "flowkit", object())
    monkeypatch.setitem(sys.modules, "bokeh", object())
    monkeypatch.setitem(sys.modules, "bokeh.core.templates", object())

    _prepare_runtime_for_flowkit_import()

    assert "flowkit" not in sys.modules
    assert "bokeh" not in sys.modules
    assert "bokeh.core.templates" not in sys.modules


def test_prepare_runtime_for_flowkit_import_clears_existing_bokeh_submodules(
    monkeypatch, tmp_path
):
    """Cached app-bundle Bokeh submodules must not survive the FlowKit prep."""
    app_bundle = tmp_path / "BioPro.app" / "Contents" / "Frameworks"
    plugin_site_packages = tmp_path / "plugin" / "site-packages"
    (app_bundle / "bokeh" / "core" / "_templates").mkdir(parents=True)
    (plugin_site_packages / "bokeh" / "core" / "_templates").mkdir(parents=True)

    (app_bundle / "bokeh" / "__init__.py").write_text("")
    (app_bundle / "bokeh" / "core" / "__init__.py").write_text("")
    (app_bundle / "bokeh" / "core" / "templates.py").write_text(
        "from pathlib import Path\n\n"
        "def load_template():\n"
        "    return (Path(__file__).resolve().parent / '_templates' / 'file.html.jinja').read_text()\n"
    )
    (plugin_site_packages / "bokeh" / "__init__.py").write_text("")
    (plugin_site_packages / "bokeh" / "core" / "__init__.py").write_text("")
    (plugin_site_packages / "bokeh" / "core" / "templates.py").write_text(
        "from pathlib import Path\n\n"
        "def load_template():\n"
        "    return (Path(__file__).resolve().parent / '_templates' / 'file.html.jinja').read_text()\n"
    )
    (
        plugin_site_packages / "bokeh" / "core" / "_templates" / "file.html.jinja"
    ).write_text("<h1>ok</h1>")

    monkeypatch.setattr(
        sys,
        "path",
        [str(app_bundle), str(plugin_site_packages), "/usr/lib/python"],
    )

    sys.modules["bokeh"] = types.SimpleNamespace(
        __file__=str(app_bundle / "bokeh" / "__init__.py"), __name__="bokeh"
    )
    sys.modules["bokeh.core"] = types.SimpleNamespace(
        __file__=str(app_bundle / "bokeh" / "core" / "__init__.py"),
        __name__="bokeh.core",
    )
    sys.modules["bokeh.core.templates"] = types.SimpleNamespace(
        __file__=str(app_bundle / "bokeh" / "core" / "templates.py"),
        __name__="bokeh.core.templates",
    )

    _prepare_runtime_for_flowkit_import()

    assert "bokeh" not in sys.modules
    assert "bokeh.core" not in sys.modules
    assert "bokeh.core.templates" not in sys.modules

    import bokeh.core.templates as templates

    assert str(plugin_site_packages) in templates.__file__
    assert templates.load_template() == "<h1>ok</h1>"


def test_prepare_runtime_for_flowkit_import_prioritizes_plugin_site_packages(
    monkeypatch, tmp_path
):
    """FlowKit import prep should make the plugin Bokeh package win over bundled app paths."""
    app_bundle = tmp_path / "BioPro.app" / "Contents" / "Frameworks"
    plugin_site_packages = tmp_path / "plugin" / "site-packages"
    (app_bundle / "bokeh" / "core" / "_templates").mkdir(parents=True)
    (plugin_site_packages / "bokeh" / "core" / "_templates").mkdir(parents=True)

    (app_bundle / "bokeh" / "__init__.py").write_text("")
    (app_bundle / "bokeh" / "core" / "__init__.py").write_text("")
    (app_bundle / "bokeh" / "core" / "templates.py").write_text(
        "from pathlib import Path\n\n"
        "def load_template():\n"
        "    return (Path(__file__).resolve().parent / '_templates' / 'file.html.jinja').read_text()\n"
    )
    (plugin_site_packages / "bokeh" / "__init__.py").write_text("")
    (plugin_site_packages / "bokeh" / "core" / "__init__.py").write_text("")
    (plugin_site_packages / "bokeh" / "core" / "templates.py").write_text(
        "from pathlib import Path\n\n"
        "def load_template():\n"
        "    return (Path(__file__).resolve().parent / '_templates' / 'file.html.jinja').read_text()\n"
    )
    (
        plugin_site_packages / "bokeh" / "core" / "_templates" / "file.html.jinja"
    ).write_text("<h1>ok</h1>")

    monkeypatch.setattr(
        sys,
        "path",
        [str(app_bundle), str(plugin_site_packages), "/usr/lib/python"],
    )

    for name in ["bokeh", "bokeh.core", "bokeh.core.templates"]:
        sys.modules.pop(name, None)

    try:
        import bokeh.core.templates as templates

        templates.load_template()
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Expected the bundled app path to fail before import prep")

    _prepare_runtime_for_flowkit_import()

    import bokeh.core.templates as templates

    assert str(plugin_site_packages) in templates.__file__
    assert templates.load_template() == "<h1>ok</h1>"


def test_prepare_runtime_for_flowkit_import_handles_missing_meipass(monkeypatch):
    """Missing sys._MEIPASS should not cause state preparation to fail."""
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)

    from analysis.fcs_io import (
        _prepare_runtime_for_flowkit_import,
        _restore_runtime_after_flowkit_import,
    )

    state = _prepare_runtime_for_flowkit_import()
    assert state["had_meipass"] is False
    assert state["had_frozen"] is False

    # restore should be a no-op and must not raise
    _restore_runtime_after_flowkit_import(state)


def test_prepare_runtime_for_flowkit_import_restores_existing_frozen_state(monkeypatch):
    """Existing sys.frozen and sys._MEIPASS values must be restored."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", "/tmp/biopro_meipass", raising=False)

    from analysis.fcs_io import (
        _prepare_runtime_for_flowkit_import,
        _restore_runtime_after_flowkit_import,
    )

    state = _prepare_runtime_for_flowkit_import()
    assert state["had_meipass"] is True
    assert state["had_frozen"] is True
    assert getattr(sys, "frozen", False) is False
    assert not hasattr(sys, "_MEIPASS")

    _restore_runtime_after_flowkit_import(state)

    assert getattr(sys, "frozen", None) is True
    assert getattr(sys, "_MEIPASS", None) == "/tmp/biopro_meipass"


def test_find_plugin_python_executable_from_site_packages(tmp_path, monkeypatch):
    """The plugin workflow must locate a venv executable from a plugin site-packages path."""
    plugin_site_packages = (
        tmp_path
        / ".plugin_venv"
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    flowkit_pkg = plugin_site_packages / "flowkit"
    flowkit_pkg.mkdir(parents=True)
    (flowkit_pkg / "__init__.py").write_text("")

    python_bin = plugin_site_packages.parents[2] / "bin"
    python_bin.mkdir(parents=True)
    (python_bin / "python").write_text("")

    monkeypatch.setattr(sys, "path", [str(plugin_site_packages), "/usr/lib/python"])

    from analysis.fcs_io import (
        _find_plugin_site_packages,
        _find_plugin_python_executable,
    )

    assert _find_plugin_site_packages() == plugin_site_packages
    assert _find_plugin_python_executable(plugin_site_packages) == python_bin / "python"


def test_find_plugin_python_executable_avoids_frozen_app_executable(
    tmp_path, monkeypatch
):
    """A frozen app executable must not be used as the worker Python."""
    plugin_site_packages = (
        tmp_path
        / ".plugin_venv"
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    plugin_site_packages.mkdir(parents=True)

    monkeypatch.setattr(sys, "path", [str(plugin_site_packages), "/usr/lib/python"])
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        sys,
        "executable",
        "/Applications/BioPro.app/Contents/MacOS/BioPro",
        raising=False,
    )
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/python3")

    from analysis.fcs_io import _find_plugin_python_executable

    assert _find_plugin_python_executable(plugin_site_packages) == Path(
        "/usr/bin/python3"
    )


def test_find_plugin_python_executable_falls_back_to_current_executable(
    tmp_path, monkeypatch
):
    """When the plugin environment is target-only, we must still launch a worker."""
    plugin_site_packages = (
        tmp_path
        / ".plugin_venv"
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    flowkit_pkg = plugin_site_packages / "flowkit"
    flowkit_pkg.mkdir(parents=True)
    (flowkit_pkg / "__init__.py").write_text("")

    monkeypatch.setattr(sys, "path", [str(plugin_site_packages), "/usr/lib/python"])

    from analysis.fcs_io import _find_plugin_python_executable

    assert _find_plugin_python_executable(plugin_site_packages) == Path(sys.executable)


def test_load_fcs_retries_flowkit_with_tolerant_offsets(monkeypatch, tmp_path):
    """FlowKit should retry with tolerant offset handling when initial load fails."""
    flowkit_pkg = tmp_path / "plugin" / "site-packages" / "flowkit"
    flowkit_pkg.mkdir(parents=True)
    (flowkit_pkg / "state.py").write_text("count = 0\n")
    (flowkit_pkg / "__init__.py").write_text(
        "from . import state\n"
        "\n"
        "class Sample:\n"
        "    def __init__(self, path, ignore_offset_error=False, ignore_offset_discrepancy=False, use_header_offsets=False, **kwargs):\n"
        "        state.count += 1\n"
        "        if state.count == 1:\n"
        "            raise RuntimeError('FCS file indicates data section greater than file size')\n"
        "        self.channels = {'pnn': ['FSC-A'], 'pns': ['']}\n"
        "        self.metadata = {}\n"
        "    def get_events(self, source='raw'):\n"
        "        return [[1.0]]\n"
        "\n"
        "_conf = type('C', (), {'mp_context': None})()\n"
        "__version__ = '1.2.3'\n"
    )
    monkeypatch.setattr(sys, "path", [str(flowkit_pkg.parent), "/usr/lib/python"])
    monkeypatch.delitem(sys.modules, "flowkit", raising=False)
    monkeypatch.setattr(
        biopro_sdk.plugin, "validate_file_exists", lambda path: (True, "")
    )

    fcs_file = tmp_path / "test.fcs"
    fcs_file.write_text("dummy")

    fcs_data = load_fcs(str(fcs_file))

    assert fcs_data.num_events == 1
    assert fcs_data.channels == ["FSC-A"]
    assert list(fcs_data.events.iloc[0]) == [1.0]
    assert fcs_data.metadata == {}
