#!/usr/bin/env python3
"""Reproduce a packaged BioPro FlowKit/Bokeh import failure in a sandbox.

This script creates a fake PyInstaller-style application bundle and a fake
plugin-local site-packages environment, then simulates the exact runtime
conditions reported in the user log:

- sys.frozen = True
- sys._MEIPASS points to the app bundle
- app-bundle paths are on sys.path ahead of plugin site-packages
- stale bokeh/flowkit modules may already be loaded from the app bundle

It then shows whether the helper in analysis/fcs_io.py can recover the
correct plugin-local package path.
"""

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.fcs_io import (  # noqa: E402
    _prepare_runtime_for_flowkit_import,
    _restore_runtime_after_flowkit_import,
)


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def build_fake_package(base: Path, package_name: str, template_exists: bool) -> None:
    package_dir = base / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    write_file(package_dir / "__init__.py", "\n")
    if package_name == "bokeh":
        write_file(package_dir / "core" / "__init__.py", "\n")
        write_file(
            package_dir / "core" / "templates.py",
            "from pathlib import Path\n\n"
            "def load_template():\n"
            "    path = Path(__file__).resolve().parent / '_templates' / 'file.html.jinja'\n"
            "    return path.read_text()\n",
        )
        if template_exists:
            write_file(
                package_dir / "core" / "_templates" / "file.html.jinja",
                "<h1>app bundle</h1>\n",
            )
    elif package_name == "flowkit":
        write_file(
            package_dir / "__init__.py",
            "from bokeh.core.templates import load_template\n"
            "\n"
            "def _check_template():\n"
            "    return load_template()\n"
            "\n"
            "_check_template()\n"
            "__version__ = '1.2.3'\n",
        )


def build_sandbox(sandbox_root: Path) -> tuple[Path, Path]:
    app_bundle = sandbox_root / "BioPro.app" / "Contents" / "Frameworks"
    plugin_site_packages = (
        sandbox_root
        / "plugins"
        / "flow_cytometry"
        / ".plugin_venv"
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )

    build_fake_package(app_bundle, "bokeh", template_exists=False)
    build_fake_package(app_bundle, "flowkit", template_exists=False)

    build_fake_package(plugin_site_packages, "bokeh", template_exists=True)
    build_fake_package(plugin_site_packages, "flowkit", template_exists=True)

    return app_bundle, plugin_site_packages


def print_modules(prefix: str, module_names: list[str]) -> None:
    print(f"--- {prefix}")
    for name in module_names:
        module = sys.modules.get(name)
        if module is None:
            print(f"{name}: not loaded")
            continue
        print(f"{name}: {getattr(module, '__file__', 'no __file__')}")


def main() -> int:
    sandbox = Path(tempfile.mkdtemp(prefix="biopro_packaged_repro_"))
    app_bundle, plugin_site_packages = build_sandbox(sandbox)

    print("Sandbox root:", sandbox)
    print("App bundle:", app_bundle)
    print("Plugin site-packages:", plugin_site_packages)

    original_path = list(sys.path)
    original_frozen = getattr(sys, "frozen", None)
    original_meipass = getattr(sys, "_MEIPASS", None)

    try:
        sys.path[:] = [str(app_bundle), str(plugin_site_packages)] + original_path
        sys.frozen = True  # type: ignore[attr-defined]
        sys._MEIPASS = str(app_bundle)

        print("\nInitial sys.path head:")
        for entry in sys.path[:4]:
            print(" ", entry)

        try:
            import bokeh.core.templates as templates

            print("\nImported bokeh before helper from:", templates.__file__)
            print("Template content:", templates.load_template())
        except Exception as exc:
            print("\nFailed to import bokeh before helper:", type(exc).__name__, exc)

        # Keep stale app-bundle modules loaded
        print_modules(
            "Before helper sys.modules",
            ["bokeh", "bokeh.core", "bokeh.core.templates", "flowkit"],
        )

        print("\nRunning _prepare_runtime_for_flowkit_import()...")
        helper_state = _prepare_runtime_for_flowkit_import()

        print("Updated sys.path head:")
        for entry in sys.path[:4]:
            print(" ", entry)

        try:
            import flowkit

            print("\nImported flowkit after helper from:", flowkit.__file__)
        except Exception as exc:
            print("\nFlowkit import failed after helper:", type(exc).__name__, exc)
            raise

        print("\nLoaded modules after helper:")
        print_modules(
            "After helper sys.modules",
            ["bokeh", "bokeh.core", "bokeh.core.templates", "flowkit"],
        )

        print("\nflowkit.__file__:", getattr(flowkit, "__file__", None))
        return 0
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        _restore_runtime_after_flowkit_import(*helper_state)
        if original_frozen is None:
            delattr(sys, "frozen")
        else:
            sys.frozen = original_frozen  # type: ignore[attr-defined]
        if original_meipass is None:
            if hasattr(sys, "_MEIPASS"):
                del sys._MEIPASS
        else:
            sys._MEIPASS = original_meipass
        sys.path[:] = original_path
        print("\nRestored sys.path and runtime state.")
        print("Sandbox preserved at:", sandbox)


if __name__ == "__main__":
    raise SystemExit(main())
