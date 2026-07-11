#!/usr/bin/env python3
"""Local sandbox to reproduce the BioPro flow_cytometry FCS loading pipeline
without launching the full Qt app.

This drives the REAL code your plugin ships — it imports fcs_io.py directly
from your plugin repo by file path (not a reimplementation), and shells out
to the REAL fcs_worker.py --selftest / worker invocation via uv, exactly as
biopro.core.package_manager.PackageManager and analysis.fcs_io do in the
packaged app. Whatever this script reports is what the app would do.

Usage:
    # Run with the SAME interpreter that has biopro_sdk installed —
    # typically your repo's own dev .venv, since fcs_io.py imports
    # `from biopro_sdk.plugin import get_logger, validate_file_exists`.
    .venv/bin/python sandbox_repro.py path/to/file.fcs

    # Force a clean venv rebuild first (mirrors deleting .plugin_venv +
    # reinstalling the plugin in the real app):
    .venv/bin/python sandbox_repro.py path/to/file.fcs --rebuild-venv

    # Point at a plugin repo checkout other than the current directory:
    .venv/bin/python sandbox_repro.py path/to/file.fcs --plugin-dir /path/to/BioPro-flow-cytometry
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import traceback
from pathlib import Path


def _fail(msg: str) -> None:
    print(f"\n❌ {msg}")
    sys.exit(1)


def build_venv(plugin_dir: Path, uv_path: str) -> Path:
    """Mirrors PackageManager.resolve_and_install_all: uv venv + uv pip install
    into that venv's own interpreter, reading deps from manifest.json."""
    manifest_path = plugin_dir / "manifest.json"
    if not manifest_path.exists():
        _fail(f"manifest.json not found at {manifest_path} — wrong --plugin-dir?")

    manifest = json.loads(manifest_path.read_text())
    deps = manifest.get("python_dependencies")
    if deps is None:
        deps = {d: "" for d in manifest.get("core_dependencies", [])}

    reqs = []
    for name, ver in deps.items():
        if ver and not ver.startswith(("=", ">", "<")):
            reqs.append(f"{name}=={ver}")
        else:
            reqs.append(f"{name}{ver}")

    venv_dir = plugin_dir / ".plugin_venv"
    if venv_dir.exists():
        print(f"Removing stale venv: {venv_dir}")
        shutil.rmtree(venv_dir)

    print(f"Creating venv: {venv_dir}")
    result = subprocess.run(
        [uv_path, "venv", str(venv_dir), "--python", "3.12"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _fail(f"uv venv failed:\n{result.stderr}")

    venv_python = venv_dir / "bin" / "python3.12"
    if not venv_python.exists():
        _fail(f"uv venv did not produce expected interpreter at {venv_python}")

    print(f"Installing {len(reqs)} deps into {venv_python}")
    result = subprocess.run(
        [uv_path, "pip", "install", "--python", str(venv_python)] + reqs,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        _fail(f"uv pip install failed:\n{result.stderr}")

    return venv_python


def run_selftest(venv_python: Path, worker_script: Path) -> bool:
    if not worker_script.exists():
        _fail(f"fcs_worker.py not found at {worker_script}")

    result = subprocess.run(
        [str(venv_python), str(worker_script), "--selftest"],
        capture_output=True,
        text=True,
    )
    print("---- selftest stdout ----")
    print(result.stdout.strip() or "(empty)")
    print("---- selftest stderr ----")
    print(result.stderr.strip() or "(empty)")
    return result.returncode == 0


def load_via_fcs_io(fcs_path: Path, plugin_dir: Path):
    """Imports the ACTUAL fcs_io.py from the plugin repo and calls the
    ACTUAL load_fcs(path, plugin_dir), exactly as FCSLoaderAnalysis.run()
    does in the real app."""
    fcs_io_path = plugin_dir / "analysis" / "fcs_io.py"
    if not fcs_io_path.exists():
        _fail(f"fcs_io.py not found at {fcs_io_path}")

    spec = importlib.util.spec_from_file_location("fcs_io_under_test", fcs_io_path)
    fcs_io = importlib.util.module_from_spec(spec)
    sys.modules["fcs_io_under_test"] = fcs_io
    try:
        spec.loader.exec_module(fcs_io)
    except ImportError as exc:
        _fail(
            f"Could not import fcs_io.py: {exc}\n"
            "This usually means biopro_sdk isn't importable from THIS interpreter. "
            "Run this script with the interpreter/venv that has biopro_sdk installed "
            "(e.g. your repo's own .venv), not with the plugin's .plugin_venv."
        )

    print(f"\nLoading {fcs_path} via fcs_io.load_fcs(path, plugin_dir)...\n")
    try:
        data = fcs_io.load_fcs(fcs_path, plugin_dir)
    except Exception:
        print("load_fcs raised an exception:")
        traceback.print_exc()
        sys.exit(1)

    print(f"\n✅ Result: {data.num_events} events × {data.num_channels} channels")
    print(f"   is_compensated={data.is_compensated}")
    print(f"   channels={data.channels}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fcs_file", type=Path, help="Path to a .fcs file to load")
    parser.add_argument(
        "--plugin-dir",
        type=Path,
        default=Path.cwd(),
        help="Path to the flow_cytometry plugin repo (default: current directory)",
    )
    parser.add_argument(
        "--rebuild-venv",
        action="store_true",
        help="Delete and recreate .plugin_venv before testing (mirrors a fresh plugin reinstall)",
    )
    parser.add_argument("--uv-path", default=shutil.which("uv") or "uv")
    args = parser.parse_args()

    if not args.fcs_file.exists():
        _fail(f"FCS file not found: {args.fcs_file}")

    plugin_dir = args.plugin_dir.resolve()
    worker_script = plugin_dir / "analysis" / "fcs_worker.py"
    venv_python = plugin_dir / ".plugin_venv" / "bin" / "python3.12"

    if args.rebuild_venv or not venv_python.exists():
        venv_python = build_venv(plugin_dir, args.uv_path)
    else:
        print(f"Using existing venv: {venv_python}")

    print("\nRunning self-test...")
    if not run_selftest(venv_python, worker_script):
        _fail(
            "Self-test failed — stopping before file load. "
            "Fix the venv/worker before testing FCS loading."
        )
    print("\n✅ Self-test passed.")

    load_via_fcs_io(args.fcs_file, plugin_dir)


if __name__ == "__main__":
    main()
