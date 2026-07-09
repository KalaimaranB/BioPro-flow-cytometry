import sys
import types

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


def test_load_fcs_retries_flowkit_with_tolerant_offsets(monkeypatch, tmp_path):
    """FlowKit should retry with tolerant offset handling when initial load fails."""
    call_log = []

    def fake_sample(
        path,
        ignore_offset_error=False,
        ignore_offset_discrepancy=False,
        use_header_offsets=False,
        **kwargs,
    ):
        call_log.append(
            (ignore_offset_error, ignore_offset_discrepancy, use_header_offsets)
        )
        if len(call_log) == 1:
            raise RuntimeError("FCS file indicates data section greater than file size")
        return DummySample()

    fake_flowkit = types.SimpleNamespace()
    fake_flowkit.Sample = fake_sample
    fake_flowkit._conf = types.SimpleNamespace(mp_context=None)
    fake_flowkit.__version__ = "1.2.3"
    fake_flowkit.__file__ = "/tmp/fake/flowkit/__init__.py"

    monkeypatch.setitem(sys.modules, "flowkit", fake_flowkit)
    monkeypatch.setattr(
        biopro_sdk.plugin, "validate_file_exists", lambda path: (True, "")
    )

    fcs_file = tmp_path / "test.fcs"
    fcs_file.write_text("dummy")

    fcs_data = load_fcs(str(fcs_file))

    assert len(call_log) == 2
    assert call_log[0] == (False, False, False)
    assert call_log[1] == (True, True, True)
    assert fcs_data.num_events == 1
    assert fcs_data.channels == ["FSC-A"]
    assert list(fcs_data.events.iloc[0]) == [1.0]
    assert fcs_data.metadata == {}
