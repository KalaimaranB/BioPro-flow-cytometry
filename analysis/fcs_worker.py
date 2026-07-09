"""Isolated FlowKit worker for safe FCS loading.

This module is intended to be run in a separate Python interpreter from the
main BioPro application process. It loads an FCS file via FlowKit and writes
serialized results to a temporary output file so the main process can ingest
channels, markers, metadata, and event data without importing FlowKit/Bokeh
into the app process.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import numpy as np


def _prepare_worker_import_environment() -> tuple[bool, str | None, list[str]]:
    was_frozen = getattr(sys, "frozen", False)
    meipass = getattr(sys, "_MEIPASS", None)

    if was_frozen:
        sys.frozen = False  # type: ignore[attr-defined]
    if meipass is not None:
        try:
            del sys._MEIPASS
        except Exception:
            pass

    original_path = list(sys.path)
    sys.path[:] = [
        p
        for p in sys.path
        if p
        and "/Applications/BioPro.app/Contents/Frameworks" not in p
        and "BioPro.app" not in p
    ]
    importlib.invalidate_caches()
    return was_frozen, meipass, original_path


def _restore_worker_import_environment(
    state: tuple[bool, str | None, list[str]],
) -> None:
    was_frozen, meipass, original_path = state
    if was_frozen:
        sys.frozen = True  # type: ignore[attr-defined]
    if meipass is not None:
        try:
            sys._MEIPASS = meipass
        except Exception:
            pass
    sys.path[:] = original_path


def _load_sample(path: Path):
    state = _prepare_worker_import_environment()
    try:
        try:
            import flowkit

            sample = flowkit.Sample(path)
        except Exception:
            import flowkit

            sample = flowkit.Sample(
                path,
                ignore_offset_error=True,
                ignore_offset_discrepancy=True,
                use_header_offsets=True,
            )
    finally:
        _restore_worker_import_environment(state)

    return sample


def _serialize_sample(sample, output_path: Path) -> None:
    channel_info = sample.channels
    channels = list(channel_info["pnn"])
    markers = [
        m if m and m.strip() else ""
        for m in channel_info.get("pns", [""] * len(channels))
    ]
    events = np.asarray(sample.get_events(source="raw"))
    metadata = dict(sample.metadata) if hasattr(sample, "metadata") else {}

    np.savez_compressed(
        output_path,
        events=events,
        channels=np.asarray(channels, dtype=str),
        markers=np.asarray(markers, dtype=str),
        metadata=np.asarray(json.dumps(metadata), dtype=str),
    )


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Usage: python -m analysis.fcs_worker <input_fcs_path> <output_npy_path>",
            file=sys.stderr,
        )
        return 2

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    try:
        sample = _load_sample(input_path)
        _serialize_sample(sample, output_path)
        return 0
    except Exception:
        print("FlowKit worker failed:\n", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
