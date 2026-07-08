"""
simulate_biopro_env.py
======================
Simulates the exact sys.path environment that BioPro Core creates for a plugin,
then attempts to import EVERY dependency the flow cytometry module uses.

What it replicates:
  1. BioPro app Frameworks dir is on sys.path FIRST (mocked as an empty dir)
     -- Python stdlib paths are preserved (BioPro does not strip those)
  2. Plugin packages are in the plugin venv, appended AFTER Frameworks
  3. The plugin's _ensure_plugin_bokeh() / metadata shim logic runs
  4. Every significant import the plugin makes is attempted in sequence

Any "No package metadata", missing template, or import error here = real end-user bug.

Usage:
  uv run python tests/simulate_biopro_env.py
"""

import sys
import subprocess
import pathlib

VENV = pathlib.Path(".venv")
FCS_FILE = pathlib.Path("tests/data/fcs/Specimen_001_Sample A.fcs")
SITE_PACKAGES = VENV / "lib" / "python3.12" / "site-packages"

# Every top-level package the plugin imports, grouped by module
# Format: (import_statement, description)
PLUGIN_IMPORTS = [
    # ── Core data / IO ────────────────────────────────────────────────────────
    ("import numpy as np", "numpy"),
    ("import pandas as pd", "pandas"),
    ("import flowio", "flowio  (FCS file reader)"),
    ("import flowutils", "flowutils"),
    ("import flowkit as fk", "flowkit (main FCS loader)"),
    ("import fcsparser", "fcsparser (fallback loader)"),
    # ── Plotting / visualisation ──────────────────────────────────────────────
    ("import matplotlib", "matplotlib"),
    ("import matplotlib.pyplot as plt", "matplotlib.pyplot"),
    ("import matplotlib.patches as mpatches", "matplotlib.patches"),
    ("import matplotlib.colors as mcolors", "matplotlib.colors"),
    ("import matplotlib.path as mpath", "matplotlib.path"),
    ("import seaborn as sns", "seaborn"),
    # ── Bokeh (used by flowkit internally) ────────────────────────────────────
    ("import bokeh", "bokeh"),
    ("from bokeh.plotting import figure", "bokeh.plotting"),
    # ── Scientific / analysis ─────────────────────────────────────────────────
    ("import scipy", "scipy"),
    ("import scipy.spatial", "scipy.spatial"),
    ("import scipy.ndimage", "scipy.ndimage"),
    ("import scipy.stats", "scipy.stats"),
    ("import sklearn", "scikit-learn"),
    ("from sklearn.preprocessing import StandardScaler", "sklearn.preprocessing"),
    # ── Dimensionality reduction / clustering ─────────────────────────────────
    ("import umap", "umap-learn"),
    ("from umap import UMAP", "umap.UMAP"),
    ("import hdbscan", "hdbscan"),
    ("from hdbscan import HDBSCAN", "hdbscan.HDBSCAN"),
    # ── JIT / performance ─────────────────────────────────────────────────────
    ("import numba", "numba"),
    ("import llvmlite", "llvmlite"),
    ("import fast_histogram", "fast-histogram"),
    # ── Tree / network ────────────────────────────────────────────────────────
    ("import anytree", "anytree"),
    ("import networkx", "networkx"),
    # ── Other plugin deps ─────────────────────────────────────────────────────
    ("import lxml", "lxml"),
    ("import psutil", "psutil"),
    ("import contourpy", "contourpy"),
]

# Packages whose __init__.py calls importlib.metadata at import time
PACKAGES_TO_PROBE = [
    "bokeh",
    "flowkit",
    "flowio",
    "flowutils",
    "scipy",
    "numpy",
    "pandas",
    "matplotlib",
    "sklearn",
    "umap",
    "hdbscan",
    "seaborn",
    "numba",
    "llvmlite",
    "anytree",
    "lxml",
    "networkx",
    "contourpy",
    "psutil",
    "fast_histogram",
    "fcsparser",
]

PASS = "\033[92m✅\033[0m"
FAIL = "\033[91m❌\033[0m"
WARN = "\033[93m⚠️ \033[0m"


def _scan_for_metadata_calls(pkg_name: str) -> list[str]:
    pkg_dir = SITE_PACKAGES / pkg_name
    init_file = pkg_dir / "__init__.py"
    if not init_file.exists():
        return []
    hits = []
    for line in init_file.read_text(errors="replace").splitlines():
        if "importlib" in line and ("version" in line or "metadata" in line):
            hits.append(line.strip())
    return hits


def phase1_scan_for_metadata_callers() -> list[str]:
    print("\n" + "=" * 60)
    print("PHASE 1: Static scan — importlib.metadata callers")
    print("=" * 60)
    print("These WILL fail in BioPro if their .dist-info is not on sys.path.\n")
    callers = []
    for pkg in PACKAGES_TO_PROBE:
        hits = _scan_for_metadata_calls(pkg)
        if hits:
            print(f"{WARN} {pkg}:")
            for h in hits:
                print(f"       {h}")
            callers.append(pkg)
        else:
            print(f"{PASS}  {pkg}: clean")
    print(f"\n→ {len(callers)} package(s) use importlib.metadata at import: {callers}")
    return callers


def phase2_simulate_all_imports() -> bool:
    """Simulate BioPro's sys.path and attempt every import the plugin makes."""
    print("\n" + "=" * 60)
    print("PHASE 2: Runtime simulation — import every plugin dependency")
    print("=" * 60)

    import_lines = "\n".join(
        f"    ({repr(stmt)}, {repr(desc)})," for stmt, desc in PLUGIN_IMPORTS
    )

    script = f"""
import sys, pathlib, tempfile, shutil

# ── Simulate BioPro: stdlib paths only, NO site-packages ─────────────────────
stdlib_paths = [p for p in sys.path if "site-packages" not in p and p != ""]
fake_frameworks = tempfile.mkdtemp(prefix="fake_biopro_frameworks_")
sys.path = [fake_frameworks] + stdlib_paths

# ── BioPro injects plugin venv AFTER (append) ─────────────────────────────────
plugin_venv = "{SITE_PACKAGES.resolve()}"
sys.path.append(plugin_venv)

# ── Apply _ensure_plugin_bokeh() equivalent ──────────────────────────────────
METADATA_SENSITIVE = ("bokeh", "umap")
biopro_cache = pathlib.Path.home() / ".biopro" / "cache" / "packages"
if biopro_cache.is_dir():
    for pkg_name in METADATA_SENSITIVE:
        for pkg_target in biopro_cache.iterdir():
            if pkg_target.is_dir() and pkg_target.name.startswith(pkg_name):
                if (pkg_target / pkg_name).is_dir():
                    s = str(pkg_target)
                    if s in sys.path: sys.path.remove(s)
                    sys.path.insert(0, s)
                    break

# ── Try every plugin import ───────────────────────────────────────────────────
imports = [
{import_lines}
]

failed = []
for stmt, desc in imports:
    try:
        exec(stmt, {{}})
        print(f"  ✅  {{desc}}")
    except Exception as e:
        print(f"  ❌  {{desc}}: {{type(e).__name__}}: {{e}}")
        failed.append((desc, str(e)))

shutil.rmtree(fake_frameworks, ignore_errors=True)

if failed:
    print(f"\\n  {{len(failed)}} import(s) FAILED:")
    for d, e in failed:
        print(f"    - {{d}}: {{e}}")
    raise SystemExit(1)
else:
    print(f"\\n  All {{len(imports)}} imports succeeded.")
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(pathlib.Path(__file__).parent.parent),
    )
    print(result.stdout)
    if result.stderr:
        errs = [
            line
            for line in result.stderr.splitlines()
            if not any(
                x in line
                for x in [
                    "NumbaDeprecationWarning",
                    "llvmlite",
                    "numba",
                    "UserWarning",
                    "FutureWarning",
                    "DeprecationWarning",
                ]
            )
        ]
        if errs:
            print(f"{WARN} stderr:\n" + "\n".join(errs[:40]))

    passed = result.returncode == 0 and "❌" not in result.stdout
    if passed:
        print(
            f"\n{PASS} Phase 2 PASSED — all plugin imports work in simulated BioPro env!"
        )
    else:
        print(
            f"\n{FAIL} Phase 2 FAILED — fix the imports listed above before shipping!"
        )
    return passed


if __name__ == "__main__":
    print("\n🔬 BioPro Plugin Environment Simulator")
    print(f"  Plugin venv : {SITE_PACKAGES}")

    if not SITE_PACKAGES.exists():
        print(f"\n{FAIL} Plugin venv not found. Run: uv sync")
        sys.exit(1)

    callers = phase1_scan_for_metadata_callers()
    p2 = phase2_simulate_all_imports()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  importlib.metadata callers : {callers}")
    print(f"  All plugin imports in BioPro env : {'PASS' if p2 else 'FAIL'}")

    if p2:
        print(f"\n{PASS} All checks passed. Safe to ship.")
        if callers:
            print(
                f"  Note: {callers} use importlib.metadata — covered by __init__.py shim + _ensure_plugin_bokeh()"
            )
        sys.exit(0)
    else:
        print(f"\n{FAIL} Issues found. Fix before shipping.")
        sys.exit(1)
