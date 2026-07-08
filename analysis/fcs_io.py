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

import numpy as np
import pandas as pd
from biopro_sdk.plugin import get_logger

# Hint for PyInstaller to bundle these dependencies
try:
    import flowkit  # noqa: F401
    import fcsparser  # noqa: F401
except ImportError:
    pass

logger = get_logger(__name__, "flow_cytometry")


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
    path = str(Path(path))
    from biopro_sdk.plugin import validate_file_exists

    exists, msg = validate_file_exists(path)
    if not exists:
        raise FileNotFoundError(msg)
    path = Path(path)

    # ── Try FlowKit first ────────────────────────────────────────────
    # FlowKit is the preferred loader: it correctly handles truncated
    # BD FACSDiva files, byte-order quirks, and partial data sections.
    try:
        return _load_with_flowkit(path)
    except ImportError:
        logger.info("FlowKit not available — falling back to fcsparser.")
    except Exception as exc:
        logger.warning("FlowKit failed to load %s: %s", path, exc)

    # ── Fallback: fcsparser ──────────────────────────────────────────
    try:
        return _load_with_fcsparser(path)
    except ImportError:
        raise RuntimeError(
            "Neither flowkit nor fcsparser is installed. "
            "Install at least one: pip install flowkit"
        )


def _load_with_flowkit(path: Path) -> FCSData:
    """Load using flowkit.Sample — the preferred path.

    FlowKit handles truncated BD FACSDiva files, byte-order quirks,
    and FCS 2.0/3.0/3.1 format variations that fcsparser cannot.
    """
    import flowkit as fk

    sample = fk.Sample(path)

    # Channel short names (PnN) and marker labels (PnS)
    channel_info = sample.channels
    channels = list(channel_info["pnn"])
    markers = list(channel_info.get("pns", [""] * len(channels)))
    markers = [m if m and m.strip() else "" for m in markers]

    # Raw events as DataFrame
    raw_events = sample.get_events(source="raw")
    events_df = pd.DataFrame(raw_events, columns=channels)

    # Metadata
    metadata = dict(sample.metadata) if hasattr(sample, "metadata") else {}

    # Auto-apply embedded compensation if present.
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
