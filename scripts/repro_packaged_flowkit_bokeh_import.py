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

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def symlink_python(plugin_venv: Path) -> None:
    python_bin = plugin_venv / "bin"
    python_bin.mkdir(parents=True, exist_ok=True)
    python312 = python_bin / "python3.12"
    python312.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n')
    python312.chmod(0o755)


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
            "class Sample:\n"
            "    def __init__(self, path, **kwargs):\n"
            "        self.channels = {'pnn': ['FSC-A'], 'pns': ['']}\n"
            "        self.metadata = {}\n"
            "\n"
            "    def get_events(self, source='raw'):\n"
            "        return [[1.0]]\n"
            "\n"
            "class _Conf:\n"
            "    mp_context = None\n"
            "\n"
            "_conf = _Conf()\n"
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

    symlink_python(sandbox_root / "plugins" / "flow_cytometry" / ".plugin_venv")

    return app_bundle, plugin_site_packages


def print_modules(prefix: str, module_names: list[str]) -> None:
    print(f"--- {prefix}")
    for name in module_names:
        module = sys.modules.get(name)
        if module is None:
            print(f"{name}: not loaded")
            continue
        print(f"{name}: {getattr(module, '__file__', 'no __file__')}")


def run_end_user_sandbox(
    sandbox_root: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Simulate an app-style launch in a sandbox and load an FCS file via FlowKit."""
    sandbox = sandbox_root or Path(tempfile.mkdtemp(prefix="biopro_packaged_repro_"))
    app_bundle, plugin_site_packages = build_sandbox(sandbox)
    fake_fcs = sandbox / "sample.fcs"
    fake_fcs.write_text("dummy fcs payload")

    bootstrap_script = sandbox / "bootstrap_app.py"
    bootstrap_script.write_text(
        textwrap.dedent(
            f"""\
            import os
            import sys
            from pathlib import Path

            repo_root = Path({str(ROOT)!r}).resolve()
            app_bundle = Path({str(app_bundle)!r}).resolve()
            plugin_site_packages = Path({str(plugin_site_packages)!r}).resolve()
            fake_fcs = Path({str(fake_fcs)!r}).resolve()

            sys.path.insert(0, str(repo_root))
            sys.path.insert(0, str(app_bundle))
            sys.path.insert(0, str(plugin_site_packages))

            sys.frozen = True  # type: ignore[attr-defined]
            sys._MEIPASS = str(app_bundle)
            os.environ['PYTHONPATH'] = str(plugin_site_packages)
            os.environ['PYTHONNOUSERSITE'] = '1'

            from analysis.fcs_io import load_fcs
            from pathlib import Path
            result = load_fcs(str(fake_fcs), Path("plugins") / "flow_cytometry")
            print(f'Loaded via FlowKit: {{result.channels}}')
            print(f'Events: {{result.num_events}}')
            """
        )
    )

    app_executable = sandbox / "BioPro.app" / "Contents" / "MacOS" / "BioPro"
    app_executable.parent.mkdir(parents=True, exist_ok=True)
    app_executable.write_text(
        "#!/bin/sh\n" f'exec {sys.executable!r} {str(bootstrap_script)!r} "$@"\n'
    )
    app_executable.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(plugin_site_packages),
            "PYTHONNOUSERSITE": "1",
        }
    )

    return subprocess.run(
        [str(app_executable)],
        capture_output=True,
        text=True,
        cwd=str(sandbox),
        env=env,
        timeout=120,
        check=False,
    )


def main() -> int:
    sandbox = Path(tempfile.mkdtemp(prefix="biopro_packaged_repro_"))
    print("Sandbox root:", sandbox)

    result = run_end_user_sandbox(sandbox)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
