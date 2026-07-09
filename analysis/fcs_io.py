"""FCS file I/O — wraps FlowKit for robust FCS loading.

Uses ``flowkit.Sample`` for FCS 2.0/3.0/3.1 parsing, metadata
extraction, and channel naming.  Falls back to ``fcsparser`` if
FlowKit is unavailable.

Reference:
    FlowKit: https://github.com/whitews/FlowKit
    FCS standard: https://www.isac-net.org/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import json
import tempfile
import numpy as np
import pandas as pd
from biopro_sdk.plugin import get_logger
import importlib
import importlib.util
import importlib.metadata
import traceback
import sys
import os
import subprocess
import platform


logger = get_logger(__name__, "flow_cytometry")


def _log_import_diagnostics() -> None:
    """Log import origins and versions for critical packages to aid debugging.

    Emits the module file path and version for a small set of packages that
    influence FCS loading behaviour. This is intentionally lightweight so it
    can be called on application startup without heavy overhead.
    """
    mods = ["flowkit", "FlowIO", "fcsparser", "numpy", "numba", "llvmlite"]
    entries = []
    for name in mods:
        try:
            spec = importlib.util.find_spec(name)
            mod_file = spec.origin if spec is not None else "not-found"
        except Exception:
            mod_file = "error"

        try:
            # Prefer import to read __version__ when available
            module = importlib.import_module(name)
            ver = getattr(module, "__version__", None)
        except Exception:
            module = None
            ver = None

        # Fallback to distribution metadata if module didn't expose __version__
        if ver is None:
            try:
                ver = importlib.metadata.version(name)
            except Exception:
                ver = "unknown"

        entries.append(f"{name} file={mod_file} version={ver}")

    logger.info(
        "Import diagnostics: python=%s executable=%s",
        ".".join(map(str, sys.version_info[:3])),
        sys.executable,
    )
    logger.info("Import diagnostics modules: %s", ", ".join(entries))
    logger.debug("sys.path head for diagnostics: %s", sys.path[:16])


def _deep_import_diagnostics(module_names: list[str], max_files: int = 50) -> None:
    """Collect deeper diagnostics for modules: distribution files and native deps.

    This logs discovered distribution files for each named package and for any
    native extension files attempts to inspect dynamic links using `otool -L`
    on macOS or `ldd` on Linux. The function is defensive and will never raise.
    """
    try:
        system = platform.system()
        logger.info(
            "Deep diagnostics: platform=%s, python=%s, exe=%s",
            system,
            ".".join(map(str, sys.version_info[:3])),
            sys.executable,
        )
        # Relevant env vars
        for var in ("DYLD_LIBRARY_PATH", "LD_LIBRARY_PATH", "PYTHONPATH", "PATH"):
            logger.debug("Env %s=%s", var, os.environ.get(var, ""))

        for name in module_names:
            try:
                spec = importlib.util.find_spec(name)
                origin = spec.origin if spec is not None else "not-found"
            except Exception:
                origin = "error"

            try:
                ver = importlib.metadata.version(name)
            except Exception:
                ver = (
                    getattr(sys.modules.get(name), "__version__", "unknown")
                    if name in sys.modules
                    else "unknown"
                )

            logger.info("Deep diag: module=%s origin=%s version=%s", name, origin, ver)

            # Distribution-level file listing (if available)
            try:
                dist = importlib.metadata.distribution(name)
                files = list(dist.files)[:max_files]
                logger.debug(
                    "Distribution %s files (sample %d): %s",
                    name,
                    len(files),
                    ", ".join(str(f) for f in files),
                )

                # Check native extension files and inspect their linked libs
                for f in files:
                    sf = str(f)
                    if sf.endswith((".so", ".dylib", ".pyd")):
                        try:
                            full_path = str(dist.locate_file(f))
                            if os.path.exists(full_path):
                                if system == "Darwin":
                                    cmd = ["otool", "-L", full_path]
                                else:
                                    cmd = ["ldd", full_path]
                                try:
                                    out = subprocess.run(
                                        cmd, capture_output=True, text=True, timeout=5
                                    )
                                    logger.debug(
                                        "Native deps for %s: %s",
                                        full_path,
                                        out.stdout.replace("\n", "\\n"),
                                    )
                                except Exception as e:
                                    logger.debug(
                                        "Failed to run %s on %s: %s",
                                        cmd[0],
                                        full_path,
                                        e,
                                    )
                        except Exception:
                            logger.debug(
                                "Could not locate file %s for distribution %s", f, name
                            )
            except Exception:
                logger.debug(
                    "No distribution metadata for %s: %s", name, traceback.format_exc()
                )

    except Exception:
        logger.debug("Deep diagnostics failed: %s", traceback.format_exc())


def _find_plugin_site_packages() -> Path | None:
    """Return the plugin-local site-packages path, if present on sys.path."""
    for entry in list(sys.path):
        if not entry:
            continue
        try:
            entry_path = Path(entry).resolve()
        except Exception:
            continue
        if not entry_path.exists():
            continue

        if (
            (entry_path / "flowkit").exists()
            or (entry_path / "bokeh").exists()
            or (entry_path / "bokeh" / "core" / "_templates").exists()
        ) and ("site-packages" in str(entry_path) or ".plugin_venv" in str(entry_path)):
            return entry_path

    return None


def _find_plugin_python_executable(plugin_site_packages: Path | None) -> Path | None:
    """Find the candidate Python executable for the plugin venv if available."""
    if plugin_site_packages is None:
        return None

    site_path = plugin_site_packages.resolve()
    if site_path.name == "site-packages":
        python_root = (
            site_path.parent.parent.parent
            if site_path.parent.name.startswith("python")
            else site_path.parent
        )
    else:
        python_root = site_path

    candidates = [
        python_root / "bin" / "python",
        python_root
        / "bin"
        / f"python{sys.version_info.major}.{sys.version_info.minor}",
        python_root / "Scripts" / "python.exe",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def _load_with_flowkit_subprocess(
    path: Path, plugin_python: Path, plugin_site_packages: Path
) -> FCSData:
    """Load FCS in a separate plugin-local Python process to isolate FlowKit/Bokeh."""
    plugin_root = plugin_site_packages
    if plugin_site_packages.name == "site-packages":
        plugin_root = (
            plugin_site_packages.parent.parent.parent
            if plugin_site_packages.parent.name.startswith("python")
            else plugin_site_packages.parent
        )

    env = os.environ.copy()
    env["PYTHONPATH"] = str(plugin_root)
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONUSERBASE", None)

    with tempfile.TemporaryDirectory(prefix="biopro_flowkit_") as tmpdir:
        result_path = Path(tmpdir) / "flowkit_fcs_result.npz"
        cmd = [
            str(plugin_python),
            "-m",
            "analysis.fcs_worker",
            str(path),
            str(result_path),
        ]
        logger.debug("Launching isolated FlowKit subprocess: %s", cmd)
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )

        if proc.returncode != 0:
            logger.warning(
                "FlowKit subprocess failed with exit %s: %s",
                proc.returncode,
                proc.stderr.strip() or proc.stdout.strip(),
            )
            raise ImportError(
                "Could not import FlowKit in isolated subprocess. "
                "See log output for details."
            )

        return _deserialize_flowkit_worker_result(result_path, path)


def _deserialize_flowkit_worker_result(result_path: Path, path: Path) -> FCSData:
    with np.load(result_path, allow_pickle=False) as result:
        events = result["events"]
        channels = [
            c.decode("utf-8") if isinstance(c, bytes) else str(c)
            for c in result["channels"]
        ]
        markers = [
            m.decode("utf-8") if isinstance(m, bytes) else str(m)
            for m in result["markers"]
        ]
        metadata_json = result["metadata"].tolist()
        metadata = json.loads(metadata_json)

    events_df = pd.DataFrame(events, columns=channels)
    is_comp = _auto_apply_spill(path.name, events_df, metadata)

    logger.info(
        "Loaded %s via isolated FlowKit subprocess: %d events × %d channels",
        path.name,
        len(events_df),
        len(channels),
    )

    return FCSData(
        file_path=path,
        channels=channels,
        markers=markers,
        events=events_df,
        metadata=metadata,
        is_compensated=is_comp,
        _fk_sample=None,
    )


@dataclass
class FCSData:
    """Container for a loaded FCS dataset.

    Attributes:
        file_path:  Path to the source ``.fcs`` file.
        channels:   Ordered list of channel short names (e.g., ``FSC-A``).
        markers:    Ordered list of marker labels (e.g., ``CD4``).
                    May be empty if no staining annotations are present.
        events:     (N, C) DataFrame of raw event data.
        metadata:   FCS keyword dictionary (TEXT segment).
        _fk_sample: The underlying ``flowkit.Sample`` object, if loaded
                    via FlowKit.  Retained for downstream transform
                    and compensation operations.
    """

    file_path: Path
    channels: list[str] = field(default_factory=list)
    markers: list[str] = field(default_factory=list)
    events: pd.DataFrame | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    is_compensated: bool = False
    _fk_sample: object = field(default=None, repr=False)

    @property
    def num_events(self) -> int:
        """Total number of events."""
        return len(self.events) if self.events is not None else 0

    @property
    def num_channels(self) -> int:
        return len(self.channels)


def load_fcs(path: str | Path) -> FCSData:
    """Load an FCS file and return an :class:`FCSData` container.

    Attempts to use ``flowkit.Sample`` first.  If FlowKit is not
    installed, falls back to ``fcsparser``.

    Args:
        path: Path to the ``.fcs`` file.

    Returns:
        A populated :class:`FCSData` with events and metadata.

    Raises:
        FileNotFoundError: If the file does not exist.
        RuntimeError: If both FlowKit and fcsparser are unavailable.
    """
    import sys

    path = str(Path(path))
    from biopro_sdk.plugin import validate_file_exists

    logger.info(
        "Loading FCS file %s with python=%s executable=%s",
        path,
        ".".join(map(str, sys.version_info[:3])),
        sys.executable,
    )
    if "flowkit" in sys.modules:
        fk_mod = sys.modules["flowkit"]
        logger.debug(
            "flowkit already loaded from %s, version=%s",
            getattr(fk_mod, "__file__", "unknown"),
            getattr(fk_mod, "__version__", "unknown"),
        )
    if "fcsparser" in sys.modules:
        fp_mod = sys.modules["fcsparser"]
        logger.debug(
            "fcsparser already loaded from %s, version=%s",
            getattr(fp_mod, "__file__", "unknown"),
            getattr(fp_mod, "__version__", "unknown"),
        )

    exists, msg = validate_file_exists(path)
    if not exists:
        raise FileNotFoundError(msg)
    path = Path(path)

    # ── Try FlowKit first ────────────────────────────────────────────
    # FlowKit is the preferred loader: it correctly handles truncated
    # BD FACSDiva files, byte-order quirks, and partial data sections.
    # Emit pre-flight import diagnostics to help identify environment
    # differences on end-user devices where FlowKit may be present but
    # failing to import or behave differently.
    try:
        _log_import_diagnostics()
    except Exception:
        logger.debug("Import diagnostics failed: %s", traceback.format_exc())

    try:
        return _load_with_flowkit(path)
    except ImportError as exc:
        logger.warning(
            "FlowKit not available — falling back to fcsparser. Reason: %s",
            exc,
        )
        logger.debug("FlowKit import traceback:\n%s", traceback.format_exc())
        logger.debug("Current sys.path head: %s", sys.path[:12])
        try:
            _deep_import_diagnostics(
                ["flowkit", "FlowIO", "fcsparser", "numpy", "numba", "llvmlite"]
            )
        except Exception:
            logger.debug(
                "Deep diagnostics on import failure failed: %s", traceback.format_exc()
            )
    except Exception as exc:
        logger.warning("FlowKit failed to load %s: %s", path, exc)
        logger.debug("FlowKit failure traceback:\n%s", traceback.format_exc())
        logger.debug("Current sys.path head: %s", sys.path[:12])
        try:
            _deep_import_diagnostics(
                ["flowkit", "FlowIO", "fcsparser", "numpy", "numba", "llvmlite"]
            )
        except Exception:
            logger.debug(
                "Deep diagnostics on runtime failure failed: %s", traceback.format_exc()
            )

    # ── Fallback: fcsparser ──────────────────────────────────────────
    try:
        return _load_with_fcsparser(path)
    except ImportError:
        raise RuntimeError(
            "Neither flowkit nor fcsparser is installed. "
            "Install at least one: pip install flowkit"
        )


def _prepare_runtime_for_flowkit_import() -> tuple[bool, str | None]:
    """Neutralize PyInstaller's frozen/app-bundle state before importing FlowKit.

    Bokeh decides whether to use bundled templates based on ``sys.frozen`` and
    ``sys._MEIPASS``.  In packaged BioPro builds those values can point at the
    app bundle even though the plugin environment is injected earlier on
    ``sys.path``.  This helper clears cached imports, prioritizes the plugin
    site-packages path, and removes conflicting app-bundle package roots so
    FlowKit/Bokeh resolve from the plugin env.
    """
    was_frozen = getattr(sys, "frozen", False)
    meipass = getattr(sys, "_MEIPASS", None)

    if was_frozen:
        sys.frozen = False  # type: ignore[attr-defined]
    if meipass is not None:
        try:
            del sys._MEIPASS
        except Exception:
            pass

    stale_names: list[str] = []
    for name, module in list(sys.modules.items()):
        if name == "bokeh" or name.startswith("bokeh."):
            stale_names.append(name)
            continue

        if name == "flowkit" or name.startswith("flowkit."):
            mod_file = getattr(module, "__file__", "") or ""
            if (
                not mod_file
                or "/Contents/" in mod_file
                or "/Frameworks/" in mod_file
                or "_MEIPASS" in mod_file
            ):
                stale_names.append(name)

    for name in stale_names:
        sys.modules.pop(name, None)

    plugin_site_packages: str | None = None
    removed_paths: list[str] = []

    for entry in list(sys.path):
        if not entry:
            continue
        entry_path = os.path.realpath(entry)
        if not entry_path:
            continue
        if (
            os.path.exists(os.path.join(entry_path, "flowkit", "__init__.py"))
            or os.path.exists(os.path.join(entry_path, "bokeh", "__init__.py"))
            or os.path.exists(os.path.join(entry_path, "bokeh", "core", "_templates"))
        ) and ("site-packages" in entry_path or ".plugin_venv" in entry_path):
            plugin_site_packages = entry_path
            break

    if plugin_site_packages is not None:
        sys.path[:] = [plugin_site_packages] + [
            path for path in sys.path if os.path.realpath(path) != plugin_site_packages
        ]

    for entry in list(sys.path):
        if not entry:
            continue
        entry_path = os.path.realpath(entry)
        if not entry_path or entry_path == plugin_site_packages:
            continue
        if (
            "/Applications/BioPro.app/Contents/Frameworks" in entry_path
            or "BioPro.app" in entry_path
        ):
            removed_paths.append(entry_path)
            sys.path.remove(entry)

    try:
        importlib.invalidate_caches()
    except Exception:
        pass

    for name in ("bokeh", "flowkit"):
        try:
            spec = importlib.util.find_spec(name)
            logger.debug(
                "Pre-import %s spec origin=%s", name, spec.origin if spec else None
            )
        except Exception:
            logger.debug("Failed to resolve spec for %s before FlowKit import", name)

    if plugin_site_packages is not None:
        logger.debug(
            "Adjusted sys.path for FlowKit import: plugin_site_packages=%s removed=%s",
            plugin_site_packages,
            removed_paths,
        )

    return was_frozen, meipass


def _restore_runtime_after_flowkit_import(
    was_frozen: bool, meipass: str | None
) -> None:
    """Restore the original PyInstaller-related runtime state after import."""
    if was_frozen:
        sys.frozen = True  # type: ignore[attr-defined]
    if meipass is not None:
        try:
            sys._MEIPASS = meipass
        except Exception:
            pass


def _load_with_flowkit(path: Path) -> FCSData:
    """Load using flowkit.Sample — the preferred path.

    FlowKit handles truncated BD FACSDiva files, byte-order quirks,
    and FCS 2.0/3.0/3.1 format variations that fcsparser cannot.
    """
    plugin_site_packages = _find_plugin_site_packages()
    plugin_python = _find_plugin_python_executable(plugin_site_packages)

    if plugin_python is not None and plugin_site_packages is not None:
        try:
            return _load_with_flowkit_subprocess(
                path, plugin_python, plugin_site_packages
            )
        except Exception as exc:
            logger.warning(
                "Isolated FlowKit subprocess failed, falling back to in-process import: %s",
                exc,
            )
            logger.debug("Subprocess traceback:\n%s", traceback.format_exc())

    return _load_with_flowkit_inprocess(path)


def _load_with_flowkit_inprocess(path: Path) -> FCSData:
    """Load FCS using FlowKit directly in the current process."""
    runtime_state = _prepare_runtime_for_flowkit_import()

    try:
        try:
            import flowkit as fk

            logger.debug(
                "FlowKit loaded from %s, version=%s",
                getattr(fk, "__file__", "unknown"),
                getattr(fk, "__version__", "unknown"),
            )
        except Exception as import_exc:
            logger.warning("FlowKit import failed: %s", import_exc)
            logger.debug("FlowKit import traceback:\n%s", traceback.format_exc())
            try:
                _deep_import_diagnostics(
                    ["flowkit", "FlowIO", "fcsparser", "numpy", "numba", "llvmlite"]
                )
            except Exception:
                logger.debug(
                    "Deep diagnostics during import failure failed: %s",
                    traceback.format_exc(),
                )
            raise

        # Monkeypatch to use spawn, preventing PyQt fork crashes on macOS
        fk._conf.mp_context = "spawn"

        try:
            sample = fk.Sample(path)
        except Exception as exc:
            logger.warning(
                "FlowKit raw load failed for %s (%s). Retrying with tolerant offset handling.",
                path.name,
                exc,
            )
            logger.debug("FlowKit Sample() traceback:\n%s", traceback.format_exc())
            try:
                _deep_import_diagnostics(
                    ["flowkit", "FlowIO", "fcsparser", "numpy", "numba", "llvmlite"]
                )
            except Exception:
                logger.debug(
                    "Deep diagnostics during Sample() failure failed: %s",
                    traceback.format_exc(),
                )
            sample = fk.Sample(
                path,
                ignore_offset_error=True,
                ignore_offset_discrepancy=True,
                use_header_offsets=True,
            )
            logger.info(
                "FlowKit tolerant offset load succeeded for %s.",
                path.name,
            )
    finally:
        _restore_runtime_after_flowkit_import(*runtime_state)

    channel_info = sample.channels
    channels = list(channel_info["pnn"])
    markers = list(channel_info.get("pns", [""] * len(channels)))
    markers = [m if m and m.strip() else "" for m in markers]

    raw_events = sample.get_events(source="raw")
    events_df = pd.DataFrame(raw_events, columns=channels)
    metadata = dict(sample.metadata) if hasattr(sample, "metadata") else {}
    is_comp = _auto_apply_spill(path.name, events_df, metadata)

    logger.info(
        "Loaded %s via FlowKit: %d events × %d channels",
        path.name,
        len(events_df),
        len(channels),
    )

    return FCSData(
        file_path=path,
        channels=channels,
        markers=markers,
        events=events_df,
        metadata=metadata,
        is_compensated=is_comp,
        _fk_sample=sample,
    )


def _auto_apply_spill(filename: str, events_df: pd.DataFrame, metadata: dict) -> bool:
    """Apply an embedded spillover matrix to events_df in-place.

    BD FACSDiva and Beckman Coulter instruments embed the compensation
    matrix in the FCS TEXT segment as a comma-separated string under
    the key 'spill', '$SPILL', '$SPILLOVER', or 'SPILLOVER'.  This
    function finds whichever variant is present, parses it, and applies
    ``D_raw @ S⁻¹`` to the matching fluorescence columns.

    The mutation is in-place so the FCSData.events DataFrame already
    contains compensated values by the time the caller returns.
    """
    # All known key variants, checked in priority order
    spill_str: str | None = None
    for key in ("$SPILLOVER", "$SPILL", "SPILLOVER", "SPILL", "spill", "spillover"):
        if key in metadata:
            spill_str = str(metadata[key])
            break

    if not spill_str:
        return False  # No spill key — nothing to do

    try:
        parts = [p.strip() for p in spill_str.split(",") if p.strip()]
        n = int(parts[0])
        spill_channels = parts[1 : n + 1]
        values = [float(v) for v in parts[n + 1 : n + 1 + n * n]]

        if len(values) != n * n:
            logger.warning(
                "Spill string in %s malformed: expected %d values, got %d. "
                "Skipping auto-compensation.",
                filename,
                n * n,
                len(values),
            )
            return False

        spill_matrix = np.array(values, dtype=np.float64).reshape(n, n)

        # Only compensate channels that are actually in the DataFrame
        present = [ch for ch in spill_channels if ch in events_df.columns]
        if not present:
            logger.warning(
                "Spill channels %s not found in %s data columns %s. "
                "Skipping auto-compensation.",
                spill_channels,
                filename,
                list(events_df.columns),
            )
            return False

        idx = [spill_channels.index(ch) for ch in present]
        sub_spill = spill_matrix[np.ix_(idx, idx)]
        sub_inv = np.linalg.inv(sub_spill)

        raw = events_df[present].values.astype(np.float64)
        # Suppress divide-by-zero / overflow — expected for extreme flow events
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            events_df[present] = raw @ sub_inv

        logger.info(
            "Auto-applied embedded spill compensation to %s (%d/%d channels: %s)",
            filename,
            len(present),
            n,
            present,
        )
        return True

    except (ValueError, IndexError, np.linalg.LinAlgError) as exc:
        logger.warning(
            "Failed to auto-apply spill compensation for %s: %s",
            filename,
            exc,
        )
        return False


def _load_with_fcsparser(path: Path) -> FCSData:
    """Fallback loader using fcsparser.

    Handles a common cytometer export quirk where the data section recorded in
    the FCS header is a few bytes larger than the actual file (typically 1–3
    events short).  When the standard ``fcsparser.parse`` call fails with a
    reshape error, we fall back to direct numpy binary reading using only the
    metadata header offsets and load as many *complete* events as the file
    actually contains.
    """
    import fcsparser

    logger.debug(
        "fcsparser loaded from %s, version=%s",
        getattr(fcsparser, "__file__", "unknown"),
        getattr(fcsparser, "__version__", "unknown"),
    )

    # ── Try standard fcsparser load first ──────────────────────────────
    try:
        meta, data = fcsparser.parse(
            str(path), reformat_meta=True, channel_naming="$PnN"
        )
        channels = list(data.columns)
        events_df = data.copy()

        # Extract marker names from metadata ($PnS)
        markers = [meta.get(f"$P{i}S", "") for i in range(1, len(channels) + 1)]

    except (ValueError, Exception) as parse_exc:
        # ── Fallback: read raw binary, truncating to complete events ────
        logger.warning(
            "fcsparser standard parse failed for %s (%s). "
            "Attempting tolerant binary read for truncated data section.",
            path.name,
            parse_exc,
        )

        # Read metadata only to get header offsets
        meta_raw = fcsparser.parse(str(path), meta_data_only=True, reformat_meta=False)
        logger.debug(
            "fcsparser meta header values: BEGINDATA=%s ENDDATA=%s BYTEORD=%s TOT=%s PAR=%s",
            meta_raw.get("$BEGINDATA"),
            meta_raw.get("$ENDDATA"),
            meta_raw.get("$BYTEORD"),
            meta_raw.get("$TOT"),
            meta_raw.get("$PAR"),
        )

        n_params = int(meta_raw.get("$PAR", 0))
        begin_data = int(meta_raw.get("$BEGINDATA", 0))
        claimed_events = int(meta_raw.get("$TOT", 0))
        byteord_str = meta_raw.get("$BYTEORD", "1,2,3,4").strip()
        dtype_prefix = "<" if byteord_str.startswith("1") else ">"
        dtype = np.dtype(f"{dtype_prefix}f4")  # FCS 3.x float32

        bytes_per_event = n_params * dtype.itemsize
        file_size = path.stat().st_size
        available_bytes = file_size - begin_data

        # Read at most what the header claims — this prevents ingesting junk
        # bytes that lie past the real data end in truncated FCS files.
        # If the file is shorter than the header claims, read as many complete
        # events as the file actually contains.
        claimed_bytes = claimed_events * bytes_per_event
        read_bytes = min(available_bytes, claimed_bytes)
        actual_events = read_bytes // bytes_per_event

        if actual_events <= 0 or n_params <= 0:
            raise RuntimeError(
                f"Cannot recover usable events from {path.name}: "
                f"n_params={n_params}, available_bytes={available_bytes}"
            ) from parse_exc

        with open(path, "rb") as fh:
            fh.seek(begin_data)
            raw = np.frombuffer(fh.read(actual_events * bytes_per_event), dtype=dtype)

        # Convert to native float64 so downstream numpy operations (matrix
        # multiply in _auto_apply_spill, matplotlib, etc.) work regardless of
        # the instrument's byte order.
        array_2d = raw.reshape(actual_events, n_params).astype(np.float64)

        # ── Garbage event filter ────────────────────────────────────────────
        # Truncated files can contain non-finite (NaN/Inf) or physically
        # impossible values in the last few events.  We apply two filters:
        #
        #  1. np.isfinite — removes NaN and ±Inf from any partial trailing event.
        #  2. FSC threshold — the cytometer records a $THRESHOLD keyword (e.g.
        #     "FSC,5000") below which no events should exist.  Denormal values
        #     like 6e-39 (IEEE 754 garbage from reading past real data end) are
        #     far below this and are stripped here.  If $THRESHOLD is absent we
        #     fall back to requiring FSC-A > 0 (all real scatter is positive).

        # Step 1: finite check across all channels
        valid_rows = np.all(np.isfinite(array_2d), axis=1)

        # Step 2: FSC threshold from the header (format: "channel,value[,...]").
        # Note: fcsparser with reformat_meta=False keeps "$" on standard FCS
        # keywords like $BYTEORD but stores instrument keywords like THRESHOLD
        # without a prefix — so we look up "THRESHOLD", not "$THRESHOLD".
        threshold_str = meta_raw.get("THRESHOLD", "")
        fsc_min = 0.0
        if threshold_str:
            parts = [p.strip() for p in threshold_str.split(",")]
            for i in range(0, len(parts) - 1, 2):
                if parts[i].upper().startswith("FSC"):
                    try:
                        fsc_min = float(parts[i + 1])
                    except ValueError:
                        pass
                    break

        # Fallback: if no threshold keyword, any FSC-A below 1.0 is a denormal
        # artefact — real acquisition thresholds are always in the hundreds+.
        if fsc_min <= 0:
            fsc_min = 1.0

        valid_rows &= array_2d[:, 0] >= fsc_min

        n_stripped = actual_events - int(valid_rows.sum())
        if n_stripped > 0:
            logger.warning(
                "Stripped %d artefact events from %s "
                "(non-finite or below FSC threshold %.0f — truncated file).",
                n_stripped,
                path.name,
                fsc_min,
            )
            array_2d = array_2d[valid_rows]
            actual_events = len(array_2d)

        # Channel names from $PnN, markers from $PnS
        channels = [meta_raw.get(f"$P{i}N", f"Ch{i}") for i in range(1, n_params + 1)]
        markers = [meta_raw.get(f"$P{i}S", "") for i in range(1, n_params + 1)]

        events_df = pd.DataFrame(array_2d, columns=channels)

        # Reform metadata: strip leading "$" so downstream code sees consistent keys
        meta = {k.lstrip("$"): v for k, v in meta_raw.items()}

        logger.info(
            "Tolerant binary read of %s: %d events × %d channels "
            "(header claimed %d events — %d events truncated).",
            path.name,
            actual_events,
            n_params,
            int(meta_raw.get("$TOT", actual_events)),
            int(meta_raw.get("$TOT", actual_events)) - actual_events,
        )

    # ── Auto-apply embedded spillover matrix (same as FlowKit path) ────
    is_comp = _auto_apply_spill(path.name, events_df, meta)

    logger.info(
        "Loaded %s via fcsparser: %d events × %d channels",
        path.name,
        len(events_df),
        len(channels),
    )

    return FCSData(
        file_path=path,
        channels=channels,
        markers=markers,
        events=events_df,
        metadata=meta,
        is_compensated=is_comp,
    )


def get_fluorescence_channels(data: FCSData) -> list[str]:
    """Return channel names that are likely fluorescence (not scatter/time).

    Heuristic: exclude names starting with FSC, SSC, Time.

    Args:
        data: A loaded :class:`FCSData`.

    Returns:
        List of fluorescence channel names.
    """
    exclude = ("FSC", "SSC", "Time", "time")
    return [ch for ch in data.channels if not ch.startswith(exclude)]


def get_channel_marker_label(data: FCSData, channel: str) -> str:
    """Return the display label for a channel.

    If a marker is mapped to this channel, returns ``"Marker (Channel)"``,
    otherwise returns just the channel name.

    Args:
        data:    A loaded :class:`FCSData`.
        channel: The channel short name.

    Returns:
        A human-readable label.
    """
    try:
        idx = data.channels.index(channel)
        marker = data.markers[idx] if idx < len(data.markers) else ""
        if marker:
            return f"{marker} ({channel})"
    except ValueError:
        pass
    return channel
