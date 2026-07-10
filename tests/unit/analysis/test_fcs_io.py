import sys
from pathlib import Path

import biopro_sdk.plugin
from biopro.plugins.flow_cytometry.analysis.fcs_io import load_fcs


def test_find_plugin_python_executable_uses_python312_in_plugin_venv(tmp_path):
    """A plugin venv must contain python3.12."""
    plugin_dir = tmp_path / "plugin"
    python_bin = plugin_dir / ".plugin_venv" / "bin"
    python_bin.mkdir(parents=True)
    python312 = python_bin / "python3.12"
    python312.write_text("")
    python312.chmod(0o755)

    from analysis.fcs_io import _find_plugin_python_executable

    assert _find_plugin_python_executable(plugin_dir) == python312


def test_load_with_flowkit_subprocess_uses_worker_script_when_analysis_not_on_path(
    monkeypatch, tmp_path
):
    """The isolated worker must launch successfully when only plugin site-packages is on PYTHONPATH."""
    plugin_site_packages = tmp_path / "plugin" / "site-packages"
    flowkit_pkg = plugin_site_packages / "flowkit"
    flowkit_pkg.mkdir(parents=True)
    (flowkit_pkg / "__init__.py").write_text(
        "import pathlib\n"
        "class Sample:\n"
        "    def __init__(self, path, **kwargs):\n"
        "        self.channels = {'pnn': ['FSC-A'], 'pns': ['']}\n"
        "        self.metadata = {}\n"
        "    def get_events(self, source='raw'):\n"
        "        return [[1.0]]\n"
        "__version__ = '1.2.3'\n"
    )

    from analysis.fcs_io import _load_with_flowkit_subprocess

    fcs_file = tmp_path / "test.fcs"
    fcs_file.write_text("dummy")

    monkeypatch.chdir(tmp_path)

    result = _load_with_flowkit_subprocess(
        fcs_file,
        Path(sys.executable),
        plugin_site_packages,
    )

    assert result.num_events == 1
    assert result.channels == ["FSC-A"]
    assert list(result.events.iloc[0]) == [1.0]


def test_simulate_packaged_user_flow_in_sandbox(tmp_path):
    """A sandboxed app-style launch should successfully load FCS via FlowKit."""
    from scripts.repro_packaged_flowkit_bokeh_import import run_end_user_sandbox

    result = run_end_user_sandbox(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "Loaded via FlowKit" in result.stdout


def test_load_fcs_retries_flowkit_with_tolerant_offsets(monkeypatch, tmp_path):
    """FlowKit should retry with tolerant offset handling when initial load fails."""
    plugin_dir = tmp_path / "plugin"
    site_packages = (
        plugin_dir
        / ".plugin_venv"
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    flowkit_pkg = site_packages / "flowkit"
    flowkit_pkg.mkdir(parents=True, exist_ok=True)
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

    plugin_dir = tmp_path / "plugin"
    python_bin = plugin_dir / ".plugin_venv" / "bin"
    python_bin.mkdir(parents=True, exist_ok=True)
    python312 = python_bin / "python3.12"
    python312.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    python312.chmod(0o755)

    # Pass the plugin dir to load_fcs
    fcs_data = load_fcs(str(fcs_file), plugin_dir)

    assert fcs_data.num_events == 1
    assert fcs_data.channels == ["FSC-A"]
    assert list(fcs_data.events.iloc[0]) == [1.0]
    assert fcs_data.metadata == {}
