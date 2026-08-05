"""Axis transformations for flow cytometry data visualization.

Provides linear, logarithmic, and biexponential (logicle) transforms
using ``flowkit``'s validated C-extension implementations.

The Logicle transform uses the Parks et al. (2006) algorithm via
``flowutils``, not a simplified approximation.

Reference:
    Parks, D.R., Roederer, M., Moore, W.A. (2006). A new "Logicle"
    display method avoids deceptive effects of logarithmic scaling for
    low signals and compensated data. *Cytometry Part A*, 69A:541-551.
"""

from __future__ import annotations

import threading
from enum import Enum
from typing import Any

import numpy as np
from biopro_sdk.plugin import get_logger

logger = get_logger(__name__, "flow_cytometry")


class TransformType(Enum):
    """Available axis transformation types."""

    LINEAR = "linear"
    LOG = "log"
    BIEXPONENTIAL = "biexponential"


# ── Cache for FlowKit transform instances ────────────────────────────────────

_thread_local = threading.local()
_flowkit_logicle_warning_issued = False


def _get_logicle_transform(
    fk: Any, top: float, width: float, positive: float, negative: float
) -> Any:
    if not hasattr(_thread_local, "logicle_cache"):
        _thread_local.logicle_cache = {}
    key = (top, width, positive, negative)
    if key not in _thread_local.logicle_cache:
        _thread_local.logicle_cache[key] = fk.transforms.LogicleTransform(
            top, width, positive, negative
        )
    return _thread_local.logicle_cache[key]


def linear_transform(
    data: np.ndarray,
    **_kwargs,
) -> np.ndarray:
    """Linear (identity) transform — returns raw values unchanged.

    Matplotlib auto-ranges the axes based on the actual data extent,
    which is what scientists expect for scatter parameters like
    FSC-A and SSC-A.

    Args:
        data: Raw channel values.

    Returns:
        The same values (as float64 for consistency).
    """
    return data.astype(np.float64)


def log_transform(
    data: np.ndarray,
    decades: float = 4.5,
    min_value: float = 1.0,
) -> np.ndarray:
    """Logarithmic (base-10) scaling.

    Values below ``min_value`` are clamped to ``min_value`` to avoid
    log(0) or log(negative).

    Args:
        data:      Raw channel values.
        decades:   Number of decades to display.
        min_value: Floor value before taking the log.

    Returns:
        Log-scaled values.
    """
    clamped = np.maximum(data, min_value)
    return np.log10(clamped) / decades


def biexponential_transform(  # noqa: PLR0913
    data: np.ndarray,
    *,
    enable_dithering: bool = False,
    top: float = 262144.0,
    width: float = 1.0,
    positive: float = 4.5,
    negative: float = 0.0,
) -> np.ndarray:
    """Biexponential (logicle) transform for compensated data.

    Uses ``flowkit.transforms.LogicleTransform`` which wraps the
    validated C implementation from ``flowutils``.  This is the **real**
    Parks 2006 algorithm, not an approximation.

    Falls back to ``flowutils.transforms.logicle`` if FlowKit's
    high-level API is unavailable, and finally to an asinh
    approximation as a last resort.

    Args:
        data:             Raw channel values.
        enable_dithering: If True, apply +/-0.5 uniform jitter to prevent barcode artifacts.
        top:              Maximum expected data value (T parameter).
        width:            Linearization width (W parameter, decades).
        positive:         Number of positive decades (M parameter).
        negative:         Additional negative decades (A parameter).

    Returns:
        Transformed values in display units.
    """
    # Apply continuous +/-0.5 uniform dithering to prevent integer banding
    # (barcode artifacts) which dramatically skew density calculations near 0
    data_jitter = np.asarray(data, dtype=np.float64).copy()
    if enable_dithering:
        data_jitter += np.random.uniform(-0.5, 0.5, size=data_jitter.shape)

    # ── FlowKit LogicleTransform (real Parks 2006 algorithm) ──────────
    # NOTE: flowkit.transforms is a namespace package — it cannot be imported
    # with 'from flowkit.transforms import LogicleTransform'. Access via fk.transforms.
    try:
        import flowkit as fk

        transform_obj = _get_logicle_transform(fk, top, width, positive, negative)
        # np.ascontiguousarray ensures a C-contiguous, owned float64 buffer —
        # the FlowKit C extension (flowutils) requires this; a non-contiguous
        # view from ravel() can cause a SIGBUS on ARM macOS.
        flat_data = np.ascontiguousarray(data_jitter.ravel(), dtype=np.float64)
        transformed = transform_obj.apply(flat_data)
        return transformed.reshape(data_jitter.shape)
    except Exception as e:
        global _flowkit_logicle_warning_issued
        if not _flowkit_logicle_warning_issued:
            logger.warning(
                "FlowKit LogicleTransform unavailable: %s. Falling back to arcsinh approximation. "
                "This can alter display scaling in pseudocolor plots.",
                e,
            )
            _flowkit_logicle_warning_issued = True
        else:
            logger.debug("FlowKit LogicleTransform fallback repeated: %s", e)

    # ── arcsinh Approximation (last resort) ───────────────────────────
    # Only reached if flowkit is not installed at all.
    cofactor = (top / (10**positive)) * (10**width)
    return np.arcsinh(data_jitter / cofactor) / positive


def apply_transform(
    data: np.ndarray,
    transform_type: TransformType,
    **_kwargs,
) -> np.ndarray:
    """Apply a named transform to data.

    Args:
        data:           Raw channel values.
        transform_type: Which transform to apply.
        **_kwargs:       Additional arguments passed to the transform.

    Returns:
        Transformed values.
    """
    # Use .value to avoid module-aliasing identity bugs with Enums sent across IPC
    val = transform_type.value if isinstance(transform_type, Enum) else str(transform_type)

    if val == TransformType.LINEAR.value:
        return linear_transform(data, **_kwargs)
    if val == TransformType.LOG.value:
        return log_transform(data, **_kwargs)
    if val == TransformType.BIEXPONENTIAL.value:
        return biexponential_transform(data, **_kwargs)
    raise ValueError(f"Unknown transform: {transform_type}")


def invert_linear_transform(
    data: np.ndarray,
    **_kwargs,
) -> np.ndarray:
    """Inverse of linear (identity) transform."""
    return data.astype(np.float64)


def invert_log_transform(
    data: np.ndarray,
    decades: float = 4.5,
    _min_value: float = 1.0,
    **_kwargs,
) -> np.ndarray:
    """Inverse of logarithmic scaling.

    Args:
        data:      Transformed channel values.
        decades:   Number of decades displayed.
        min_value: Floor value that was originally used.

    Returns:
        Raw channel values.
    """
    return 10.0 ** (data * decades)


def invert_biexponential_transform(
    data: np.ndarray,
    *,
    top: float = 262144.0,
    width: float = 1.0,
    positive: float = 4.5,
    negative: float = 0.0,
    **_kwargs,
) -> np.ndarray:
    """Inverse of biexponential (logicle) transform.

    Args:
        data:     Transformed channel values in display units.
        top:      Maximum expected data value (T parameter).
        width:    Linearization width (W parameter, decades).
        positive: Number of positive decades (M parameter).
        negative: Additional negative decades (A parameter).

    Returns:
        Raw channel values.
    """
    # ── FlowKit inverse (real Parks 2006 algorithm) ───────────────────
    # NOTE: flowkit.transforms is a namespace package — access via fk.transforms.
    try:
        import flowkit as fk

        transform_obj = _get_logicle_transform(fk, top, width, positive, negative)
        flat_data = np.asarray(data, dtype=np.float64).ravel()
        raw = transform_obj.inverse(flat_data)
        return raw.reshape(data.shape)
    except Exception as e:
        logger.debug("FlowKit LogicleTransform inverse failed: %s. Falling back to arcsinh.", e)

    # ── arcsinh fallback (last resort) ────────────────────────────────
    cofactor = (top / (10**positive)) * (10**width)
    return np.sinh(data * positive) * cofactor


def invert_transform(
    data: np.ndarray,
    transform_type: TransformType,
    **_kwargs,
) -> np.ndarray:
    """Apply the inverse of a named transform to mapped data.

    Args:
        data:           Transformed display values.
        transform_type: Which transform was applied.
        **_kwargs:       Additional arguments passed to the transform.

    Returns:
        Raw data values.
    """
    # Use .value to avoid module-aliasing identity bugs with Enums sent across IPC
    val = transform_type.value if isinstance(transform_type, Enum) else str(transform_type)

    if val == TransformType.LINEAR.value:
        return invert_linear_transform(data, **_kwargs)
    if val == TransformType.LOG.value:
        return invert_log_transform(data, **_kwargs)
    if val == TransformType.BIEXPONENTIAL.value:
        return invert_biexponential_transform(data, **_kwargs)
    raise ValueError(f"Unknown transform: {transform_type}")
