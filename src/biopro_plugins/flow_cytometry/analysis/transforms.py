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

import contextlib
import sys
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

# ── bokeh/flowkit frozen-app warmup ───────────────────────────────────────────
# bokeh's own bokeh.core.templates.get_env() is @lru_cache'd and checks
# sys.frozen/sys._MEIPASS *globally* to decide where its Jinja2 templates
# live, assuming that if the process is frozen, bokeh itself must be bundled
# at the standard PyInstaller location. That's true for a normal frozen app,
# but false here: BioPro core is frozen, while bokeh (a transitive plugin
# dependency, pulled in by flowkit) lives in this plugin's own separate,
# non-frozen .venv. sys.frozen is process-global, so it reads True for this
# plugin's code too, even though bokeh's real templates are elsewhere.
_frozen_state_lock = threading.Lock()
_flowkit_bokeh_warmup_lock = threading.Lock()
_flowkit_bokeh_warmup_done = False


@contextlib.contextmanager
def _suspend_frozen_state():
    """Temporarily hide sys.frozen/sys._MEIPASS from code running inside.

    bokeh.core.templates.get_env() is cached via @lru_cache(None), so getting
    it right the first time it's ever called in this process permanently
    fixes every later call — regardless of what sys.frozen reads by then.
    Serialized via a lock so concurrent warmup/real-call races can't leave
    the flags in an inconsistent state.
    """
    with _frozen_state_lock:
        was_frozen = getattr(sys, "frozen", False)
        had_meipass = hasattr(sys, "_MEIPASS")
        meipass = getattr(sys, "_MEIPASS", None)
        if was_frozen:
            sys.frozen = False  # type: ignore[attr-defined]
        if had_meipass:
            del sys._MEIPASS  # type: ignore[attr-defined]
        try:
            yield
        finally:
            if was_frozen:
                sys.frozen = was_frozen  # type: ignore[attr-defined]
            if had_meipass:
                sys._MEIPASS = meipass  # type: ignore[attr-defined]


def warmup_flowkit_bokeh() -> None:
    """Prime bokeh's Jinja2 template environment in the background, once.

    Call at plugin load time (see ``get_panel_class()``). Importing flowkit
    triggers bokeh.core.templates.get_env() as a side effect (flowkit eagerly
    imports its own plotting utilities, which import bokeh.document, which
    accesses bokeh's template environment at import time). Doing that first
    import inside ``_suspend_frozen_state()`` means the real call, whenever a
    user first renders a biexponential axis, hits an already-correct cache.
    """
    global _flowkit_bokeh_warmup_done
    with _flowkit_bokeh_warmup_lock:
        if _flowkit_bokeh_warmup_done:
            return
        _flowkit_bokeh_warmup_done = True

    t = threading.Thread(target=_do_flowkit_bokeh_warmup, name="flowkit-bokeh-warmup", daemon=True)
    t.start()


def _do_flowkit_bokeh_warmup() -> None:
    try:
        with _suspend_frozen_state():
            import flowkit  # noqa: F401  side effect: primes bokeh's template env
    except Exception as exc:
        logger.debug("flowkit/bokeh warm-up failed (will self-heal on first real call): %s", exc)


def _report_flowkit_failure(e: Exception) -> None:
    """Report a FlowKit LogicleTransform failure loudly and fatally.

    There is no acceptable approximate substitute for the real Logicle
    transform — a silently-swapped formula (e.g. arcsinh) produces a
    plausible-looking but numerically wrong plot, which is worse than an
    outright failure because it goes undetected. FlowKit failing to import
    or apply indicates a real environment problem (e.g. a dependency
    resolving from the wrong location) that must be fixed, not papered over.
    """
    global _flowkit_logicle_warning_issued
    if not _flowkit_logicle_warning_issued:
        logger.error("FlowKit LogicleTransform unavailable: %s", e)
        _flowkit_logicle_warning_issued = True
    else:
        logger.debug("FlowKit LogicleTransform unavailable (repeated): %s", e)

    try:
        from biopro.core.diagnostics import diagnostics

        diagnostics.report_error(
            "The biexponential (Logicle) transform is unavailable — FlowKit failed to "
            "load or apply. Plots using this transform cannot be rendered correctly.",
            exception=e,
            fatal=True,
        )
    except ImportError:
        pass


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

    There is no fallback: an approximation formula uses the ``width``
    parameter differently and produces a plausible-looking but numerically
    wrong plot. If FlowKit is unavailable, this raises (after reporting a
    fatal diagnostic) rather than silently degrading.

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
        with _suspend_frozen_state():
            import flowkit as fk

        transform_obj = _get_logicle_transform(fk, top, width, positive, negative)
        # np.ascontiguousarray ensures a C-contiguous, owned float64 buffer —
        # the FlowKit C extension (flowutils) requires this; a non-contiguous
        # view from ravel() can cause a SIGBUS on ARM macOS.
        flat_data = np.ascontiguousarray(data_jitter.ravel(), dtype=np.float64)
        transformed = transform_obj.apply(flat_data)
        return transformed.reshape(data_jitter.shape)
    except Exception as e:
        _report_flowkit_failure(e)
        raise


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
        with _suspend_frozen_state():
            import flowkit as fk

        transform_obj = _get_logicle_transform(fk, top, width, positive, negative)
        flat_data = np.asarray(data, dtype=np.float64).ravel()
        raw = transform_obj.inverse(flat_data)
        return raw.reshape(data.shape)
    except Exception as e:
        _report_flowkit_failure(e)
        raise


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
