"""Axis scaling and range calculation utilities.

Provides data structures for persisting per-axis scale settings (e.g.,
Min/Max, Logicle T, W, M, A parameters) and utilities for calculating
robust auto-ranges that ignore extreme outliers.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from biopro_sdk.plugin import get_logger

from .transforms import TransformType

logger = get_logger(__name__, "flow_cytometry")


@dataclass
class AxisScale:
    """Settings for how to scale and display a single axis."""

    transform_type: TransformType = TransformType.LINEAR

    # Range limits (None means auto-scale)
    min_val: float | None = None
    max_val: float | None = None

    # Biexponential (Logicle) parameters
    # Matches standard Transform dialog defaults and naming
    logicle_t: float = 262144.0  # Top data value (determines max scale)
    logicle_w: float = 1.0  # Width Basis (linear range around 0)
    logicle_m: float = 4.5  # Positive decades
    logicle_a: float = 0.0  # Extra negative decades

    # Outlier bounds (percentile to ignore at each end)
    outlier_percentile: float = 0.1  # Default to 0.1% (p0.1 and p99.9)

    def __post_init__(self):
        """Validate scale parameters after initialization."""
        # Validate transform type
        valid_transforms = {t.value for t in TransformType}
        if self.transform_type.value not in valid_transforms:
            raise ValueError(
                f"Invalid transform_type: {self.transform_type}. "
                f"Must be one of: {valid_transforms}"
            )

        # Validate range
        if self.min_val is not None and self.max_val is not None:
            if self.min_val >= self.max_val:
                raise ValueError(
                    f"min_val ({self.min_val}) must be less than max_val ({self.max_val})"
                )

        # Validate Logicle parameters
        if self.transform_type == TransformType.BIEXPONENTIAL:
            if self.logicle_t <= 0:
                raise ValueError(f"logicle_t must be positive, got {self.logicle_t}")
            if self.logicle_w < 0:
                raise ValueError(
                    f"logicle_w must be non-negative, got {self.logicle_w}"
                )
            if self.logicle_m <= 0:
                raise ValueError(f"logicle_m must be positive, got {self.logicle_m}")
            if self.logicle_a < 0:
                raise ValueError(
                    f"logicle_a must be non-negative, got {self.logicle_a}"
                )

        # Validate outlier percentile
        if not 0 <= self.outlier_percentile <= 50:
            raise ValueError(
                f"outlier_percentile must be between 0 and 50, got {self.outlier_percentile}"
            )

    def copy(self) -> AxisScale:
        return AxisScale(
            transform_type=self.transform_type,
            min_val=self.min_val,
            max_val=self.max_val,
            logicle_t=self.logicle_t,
            logicle_w=self.logicle_w,
            logicle_m=self.logicle_m,
            logicle_a=self.logicle_a,
            outlier_percentile=self.outlier_percentile,
        )

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "transform_type": self.transform_type.value,
            "min_val": self.min_val,
            "max_val": self.max_val,
            "logicle_t": self.logicle_t,
            "logicle_w": self.logicle_w,
            "logicle_m": self.logicle_m,
            "logicle_a": self.logicle_a,
            "outlier_percentile": self.outlier_percentile,
        }

    @classmethod
    def from_dict(cls, data: dict) -> AxisScale:
        """Create an AxisScale instance from a dictionary."""
        return cls(
            transform_type=TransformType(data.get("transform_type", "linear")),
            min_val=data.get("min_val"),
            max_val=data.get("max_val"),
            logicle_t=data.get("logicle_t", 262144.0),
            logicle_w=data.get("logicle_w", 1.0),
            logicle_m=data.get("logicle_m", 4.5),
            logicle_a=data.get("logicle_a", 0.0),
            outlier_percentile=data.get("outlier_percentile", 0.1),
        )


def calculate_auto_range(
    data: np.ndarray, transform_type: TransformType, outlier_percentile: float = 0.1
) -> tuple[float, float]:
    """Calculate a robust display range ignoring extreme outliers."""
    if len(data) == 0:
        return (0.0, 1.0)

    valid = np.isfinite(data)
    valid_data = data[valid]

    if len(valid_data) == 0:
        return (0.0, 1.0)

    # Secondary guard: discard physically impossible values (|x| > 1e9) that
    # can appear as artefacts when truncated FCS files are read.  These are
    # technically finite IEEE 754 floats so np.isfinite() doesn't catch them,
    # but no real cytometer channel will ever legitimately exceed ±1 GFU.
    physical_mask = np.abs(valid_data) <= 1e9
    if not np.all(physical_mask):
        valid_data = valid_data[physical_mask]
        if len(valid_data) == 0:
            return (0.0, 1.0)

    # Calculate percentiles based on outlier_percentile parameter
    p_min = float(np.percentile(valid_data, outlier_percentile))
    p_max = float(np.percentile(valid_data, 100.0 - outlier_percentile))

    if transform_type == TransformType.LINEAR:
        # Floor: anchor at 0 so scatter channels always show the origin.
        # Allow slightly negative for compensated/gated subsets.
        floor = min(0.0, p_min)

        # Ceiling: No longer hardcoded to 262144. Instead, use p_max plus 5% headroom.
        # This fixes squishing for small-range channels like Time.
        # We only snap to 262144 if the data is already approaching it (e.g. FSC/SSC).
        span = p_max - floor
        if span <= 0:
            span = 1.0

        ceiling = p_max + span * 0.05

        # Heuristic: If it looks like a standard 18-bit channel, keep the full scale.
        if p_max > 200000 and p_max < 262144:
            ceiling = 262144.0

        return (floor, ceiling)

    elif transform_type == TransformType.LOG:
        pos_data = valid_data[valid_data > 0]
        if len(pos_data) == 0:
            return (0.1, 10.0)
        p_min_pos = np.percentile(pos_data, outlier_percentile)
        return (p_min_pos * 0.5, p_max * 2.0)

    elif transform_type == TransformType.BIEXPONENTIAL:
        # p_min and p_max already calculated above using outlier_percentile
        if p_min < 0:
            # Compensated fluorescence: show the negative tail with reasonable headroom.
            display_min = p_min - max(abs(p_min) * 0.1, 100.0)
        else:
            # Positive-only data (like viability dyes), but we still MUST pad below zero!
            # If we don't, the zero point is clipped and populations look like sharp spikes.
            # FlowJo always provides negative display space (e.g., -100 or -1000) for biex.
            display_min = min(-100.0, p_min - 100.0)

        span = max(p_max - display_min, 1.0)
        display_max = p_max + span * 0.05

        # Heuristic: If it looks like a standard 18-bit channel, keep the full scale.
        # This prevents the axis from zooming in dynamically and expanding noise.
        if display_max > 20000.0 and display_max < 262144.0:
            display_max = 262144.0

        return (display_min, display_max)

    else:
        return (p_min, p_max)


def _filter_physical(data: np.ndarray) -> np.ndarray:
    """Return finite, physically-plausible values only.

    Factored out of calculate_auto_range's existing guard so every
    percentile-based estimator in this module uses the same rule:
    discard non-finite values and |x| > 1e9 artefacts from truncated
    FCS files. No real cytometer channel legitimately exceeds ±1 GFU.
    """
    valid = data[np.isfinite(data)]
    if len(valid) == 0:
        return valid
    physical_mask = np.abs(valid) <= 1e9
    return valid[physical_mask]


def detect_logicle_top(data) -> float:
    """Return the Logicle T (Top) parameter for this channel's data."""
    if len(data) == 0:
        return 262144.0

    valid = _filter_physical(np.asarray(data))
    if len(valid) == 0:
        return 262144.0

    p99 = float(np.percentile(valid, 99.9))

    if p99 <= 262144.0 * 1.5:
        return 262144.0
    if p99 <= 1_048_576.0 * 1.5:
        return 1_048_576.0
    return float(2 ** int(np.ceil(np.log2(p99))))


def estimate_logicle_params(
    data: np.ndarray,
    t: float = 262144.0,
    m: float = 4.5,
) -> tuple[float, float]:
    """Estimate Logicle W and A parameters from data.

    W is calculated using the FlowJo/flowCore method:
        W = (M - log10(T / |r|)) / 2
    where r is the 5th percentile of the negative tail.
    """
    valid = _filter_physical(np.asarray(data))
    if len(valid) == 0:
        return 1.0, 0.0

    neg_data = valid[valid < 0]

    if len(neg_data) < 10 or len(neg_data) / len(valid) < 0.005:
        w = 0.5
    else:
        # FlowCore reference implementation uses the raw 5th percentile of negative events
        # without pre-trimming, ensuring the exact FlowJo mathematical behavior.
        r = float(np.percentile(neg_data, 5))

        if r >= 0:
            w = 0.5
        else:
            try:
                w = (m - np.log10(t / abs(r))) / 2.0
                # Original clamp ceiling: m/2.0
                # This allows uncompensated tails to properly scale.
                w = max(0.1, min(w, m / 2.0))
            except Exception:
                w = 0.5

    min_val = float(np.percentile(valid, 0.1))
    try:
        if min_val < -10.0:
            # Positive log10 of the magnitude, minus the decades already in the linear region
            a = np.log10(abs(min_val)) - w
            # Cap A at 1.0 to provide enough negative log space to compress the tail
            # into a tight cluster without shifting the entire plot's zero point too far right.
            a = max(0.0, min(a, 1.0))
        else:
            a = 0.0
    except Exception:
        a = 0.0

    return float(w), float(a)
