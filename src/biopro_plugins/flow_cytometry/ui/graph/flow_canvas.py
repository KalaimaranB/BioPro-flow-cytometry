"""FlowCanvas — embedded matplotlib widget for flow cytometry plots.

This is the core rendering engine for the graph window.  It creates
a ``FigureCanvasQTAgg`` embedded in PyQt6 and handles:
- Scatter (dot) plots
- Pseudocolor (hexbin density) plots
- Contour plots
- Histograms (1-D)
- Density plots (KDE)
- CDF plots
- Interactive gate drawing (Rectangle, Polygon, Ellipse, Quadrant, Range)
- Gate overlay rendering with named, color-coded patches
- Gate selection and editing via drag handles

Mouse events are handled via matplotlib's ``mpl_connect`` system with a
state machine that manages drawing, selection, and editing modes.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

import pandas as pd
from biopro.ui.theme import Colors
from biopro_sdk.plugin import CentralEventBus, get_logger
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QSizePolicy

from biopro_plugins.flow_cytometry.analysis import events
from biopro_plugins.flow_cytometry.analysis.gating import (
    Gate,
    GateNode,
)
from biopro_plugins.flow_cytometry.analysis.protocols import IGateCoordinator
from biopro_plugins.flow_cytometry.analysis.scaling import AxisScale
from biopro_plugins.flow_cytometry.analysis.state import FlowState
from biopro_plugins.flow_cytometry.analysis.transforms import TransformType
from biopro_plugins.flow_cytometry.ui.graph._mpl_compat import FigureCanvasQTAgg

from ._mpl_lock import MPL_LOCK
from .canvas.axis_formatter import AxisFormatter

# Decomposed components
from .canvas.data_layer import DataLayerRenderer
from .canvas.event_handler import CanvasEventHandler
from .canvas.gate_layer import GateLayerRenderer
from .flow_services import (
    CoordinateMapper,
    GateFactory,
    GateOverlayRenderer,
)

logger = get_logger(__name__, "flow_cytometry")
print(f"DEBUG: flow_canvas.py LOADED from {__file__}")


class DisplayMode(Enum):
    """Available plot display modes."""

    PSEUDOCOLOR = "Pseudocolor"
    DOT_PLOT = "Dot Plot"
    CONTOUR = "Contour"
    HISTOGRAM = "Histogram"
    CDF = "CDF"


class GateDrawingMode(Enum):
    """Active gate drawing tool."""

    NONE = "none"  # Default — pointer / selection mode
    RECTANGLE = "rectangle"
    POLYGON = "polygon"
    ELLIPSE = "ellipse"
    QUADRANT = "quadrant"
    RANGE = "range"


# ── Visual constants ─────────────────────────────────────────────────────────

# Plot area uses a pure white background inside the axes
# so all populations and density hexbins are perfectly visible.
_PLOT_BG = "#FFFFFF"

_MPL_STYLE = {
    "figure.facecolor": "#FFFFFF",
    "axes.facecolor": _PLOT_BG,
    "axes.edgecolor": "#333333",
    "axes.labelcolor": "#333333",
    "xtick.color": "#333333",
    "ytick.color": "#333333",
    "text.color": "#333333",
    "grid.color": "#E0E0E0",  # Light grey for visibility on white background
    "grid.alpha": 0.5,
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
}

# Gate drawing colours (Clean & Professional)
_GATE_EDGE_COLOR = "#000000"  # Black
_GATE_FILL_COLOR = "#000000"
_GATE_ALPHA = 0.05
_GATE_EDGE_ALPHA = 1.0
_GATE_LINEWIDTH = 1.2
_GATE_SELECTED_EDGE = "#2188FF"  # Subtle blue for selection
_GATE_SELECTED_ALPHA = 0.10
_RUBBER_BAND_COLOR = "#333333"
_RUBBER_BAND_ALPHA = 0.4

# Vibrant palette for multi-gate plots on white background
_GATE_PALETTE = [
    "#FF0000",  # Red
    "#0000FF",  # Blue
    "#008000",  # Green
    "#FF8C00",  # Dark Orange
    "#8B008B",  # Dark Magenta
]


class FlowCanvas(FigureCanvasQTAgg):
    """Interactive matplotlib canvas for flow cytometry plots.

    Signals:
        point_clicked(x, y):     Emitted on left-click with data coords.
        region_selected(dict):   Emitted when a rectangular selection is made.
        gate_created(Gate):      Emitted when a gate drawing is completed.
        gate_modified(str):      Emitted when a gate is edited (gate_id).
        gate_selected(str):      Emitted when a gate overlay is clicked (gate_id).
    """

    point_clicked = pyqtSignal(float, float)
    region_selected = pyqtSignal(dict)
    gate_created = pyqtSignal(object)  # Gate instance
    gate_modified = pyqtSignal(str)  # gate_id
    gate_selected = pyqtSignal(object)  # gate_id or None
    render_requested = pyqtSignal()  # Emitted on context menu "Render"
    quality_mode_changed = pyqtSignal(str)  # "optimized" or "transparent"
    gate_preview_emitted = pyqtSignal(object)  # Temporary gate object

    def __init__(  # noqa: PLR0915
        self,
        state: FlowState | None = None,
        controller: IGateCoordinator | None = None,
        parent=None,
    ) -> None:
        # Apply BioPro theme
        import matplotlib

        for key, val in _MPL_STYLE.items():
            matplotlib.rcParams[key] = val  # type: ignore

        self._fig = Figure(figsize=(6, 5), dpi=100)
        self._fig.set_facecolor(_PLOT_BG)
        super().__init__(self._fig)
        self.setObjectName("FlowCanvas")
        self.setStyleSheet(f"background-color: {_PLOT_BG};")

        logger.info(f"FlowCanvas.__init__: state={state}, controller={controller}, parent={parent}")
        self._state = state
        self._controller = controller
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._ax = self._fig.add_subplot(111)
        self._ax.set_facecolor(_PLOT_BG)
        self._ax.grid(True, color="#B0B0B0", alpha=0.35, linewidth=0.5)

        # Set fixed subplot margins once — avoids calling tight_layout()
        # which inspects every artist and crashes with non-standard ones.
        self._fig.subplots_adjust(left=0.12, bottom=0.12, right=0.95, top=0.95)

        # ── Data state ────────────────────────────────────────────────
        self._sample_id: str | None = None
        self._current_data: pd.DataFrame | None = None
        self._x_param: str = "FSC-A"
        self._y_param: str = "SSC-A"
        self._x_scale = AxisScale(TransformType.LINEAR)
        self._y_scale = AxisScale(TransformType.LINEAR)
        self._display_mode = DisplayMode.PSEUDOCOLOR
        self._x_label: str = "FSC-A"
        self._y_label: str = "SSC-A"
        self._fmo_sample_id: str | None = None

        self._guide_poly_patch: Any | None = None

        # ── Service instances (SOLID: Separation of concerns) ────────────
        # These services decouple rendering, drawing, and gate creation logic
        self._coordinate_mapper = CoordinateMapper(self._x_scale, self._y_scale)
        self._gate_factory = GateFactory(
            self._x_param,
            self._y_param,
            self._x_scale,
            self._y_scale,
            self._coordinate_mapper,
        )
        self._gate_overlay_renderer = GateOverlayRenderer(self._coordinate_mapper)

        # ── Cached background bitmap ──────────────────────────────────
        # The expensive scatter data is rendered once and cached.
        # Gate overlays are drawn on top without re-rendering scatter.
        self._canvas_bitmap_cache = None  # Matplotlib canvas background bitmap for fast redraw
        self._gate_overlay_artists: dict = {}  # gate_id → OverlayArtists
        self._gate_artists: list = []  # matplotlib patches/lines for all gates

        # ── Gate drawing state machine ────────────────────────────────
        self._drawing_mode = GateDrawingMode.NONE

        # Gate Drawing FSM (Manages state, previews, and instructions)
        from .gate_drawing_fsm import GateDrawingFSM

        self._fsm = GateDrawingFSM(self)

        # ── Gate overlays ─────────────────────────────────────────────
        self._gate_patches: dict[str, dict] = {}  # gate_id → patch info
        self._active_gates: list[Gate] = []
        self._gate_nodes: list[GateNode] = []  # for stat labels
        self._selected_gate_id: str | None = None
        self._instruction_text = None  # on-canvas drawing hint

        # ── Setup ──────────────────────────────────────────────────────
        self._max_events: int | None = 100_000  # Default subsampling limit
        self._quality_multiplier: float = 1.0  # Grid resolution scaler
        self._use_cache: bool = True  # ENABLED for blitting

        # ── Gate editing ──────────────────────────────────────────────
        self._editing_gate_id: str | None = None
        self._edit_handle_idx: int | None = None
        self._edit_handles: list = []  # matplotlib artists for handles

        # ── Signals ───────────────────────────────────────────────────
        from biopro_sdk.plugin import CentralEventBus

        from ...analysis import events

        CentralEventBus.subscribe(
            events.GATE_MODIFIED,
            lambda p: self._on_controller_geometry_changed(
                p.get("sample_id", ""), p.get("gate_id", "")
            ),
        )
        CentralEventBus.subscribe(
            events.GATE_CREATED,
            lambda p: self._on_controller_geometry_changed(
                p.get("sample_id", ""), p.get("gate_id", "")
            ),
        )
        CentralEventBus.subscribe(
            events.GATE_SELECTED,
            lambda p: self._on_controller_selected(p.get("sample_id", ""), p.get("node_id", "")),
        )
        CentralEventBus.subscribe(
            events.GATE_DELETED,
            lambda p: self._on_controller_gate_removed(
                p.get("sample_id", ""), p.get("node_id", "")
            ),
        )
        CentralEventBus.subscribe(
            events.GATE_RENAMED,
            lambda p: self._on_controller_gate_renamed(
                p.get("sample_id", ""), p.get("node_id", "")
            ),
        )

        # Mouse event connections
        self._mpl_conn_press = self.mpl_connect("button_press_event", self._on_press)
        self._mpl_conn_release = self.mpl_connect("button_release_event", self._on_release)
        self._cid_motion = self.mpl_connect("motion_notify_event", self._on_motion)
        self._mpl_conn_dblclick = self.mpl_connect("button_press_event", self._on_dblclick)
        self._cid_scroll = self.mpl_connect("scroll_event", self._on_scroll)
        self._cid_key = self.mpl_connect("key_press_event", self._on_key_press)
        self._cid_draw = self.mpl_connect("draw_event", self._on_draw)

        # ── Decomposed components ─────────────────────────────────────
        from .canvas.overlay_manager import OverlayManager
        from .canvas.zoom_handler import ZoomHandler

        self._overlay_manager = OverlayManager(self)
        self._zoom_handler = ZoomHandler(self)

        # ── Decomposed components ─────────────────────────────────────
        self._data_renderer = DataLayerRenderer(self)
        self._gate_renderer = GateLayerRenderer(self)
        self._event_handler = CanvasEventHandler(self)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # Show empty state
        self._show_empty()

    def _apply_theme_styles(self) -> None:
        """Dynamically refresh canvas when theme changes."""
        if hasattr(self, "draw_idle"):
            self.draw_idle()

    def mouseDoubleClickEvent(self, event) -> None:
        """Intercept double clicks to prevent macOS fullscreen tearing.

        On macOS, QMainWindow interprets unhandled double-clicks as a
        title-bar toggle, dropping the app out of full screen. By explicitly
        accepting the event after Matplotlib processes it, we stop the
        bubbling.
        """
        super().mouseDoubleClickEvent(event)
        event.accept()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if getattr(self, "_dirty", False):
            self.redraw()

    def set_guide_polygon(self, vertices: list[tuple[float, float]] | None) -> None:
        """Draws a faint dark purple dotted polygon to guide tutorial users."""
        if self._guide_poly_patch:
            try:
                self._guide_poly_patch.remove()
            except (ValueError, AttributeError, NotImplementedError):
                pass
            self._guide_poly_patch = None

        if vertices:
            from matplotlib.patches import Polygon

            self._guide_poly_patch = Polygon(
                vertices,
                closed=True,
                fill=False,
                edgecolor="#800080",  # Dark purple
                linestyle="--",
                linewidth=2,
                alpha=0.8,
                zorder=100,  # Ensure it renders on top
            )
            self._ax.add_patch(self._guide_poly_patch)

        self.draw_idle()

    def paintEvent(self, event) -> None:
        """Override paintEvent to acquire the global lock."""
        if not hasattr(self, "_paint_count"):
            self._paint_count = 0
        self._paint_count += 1
        if self._paint_count <= 5:  # noqa: PLR2004
            logger.info(
                f"FlowCanvas.paintEvent {self._paint_count} for {self._x_param}/{self._y_param}"
            )

        # Acquire global matplotlib lock because paintEvent calls C-level Agg
        # rendering, which is NOT thread-safe with background RenderTasks.
        # Use a non-blocking acquire so we don't freeze the Qt Main Thread if
        # a background task is taking a long time to render a thumbnail.
        if not MPL_LOCK.acquire(blocking=False):
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(50, self.update)
            return

        try:
            super().paintEvent(event)
        finally:
            MPL_LOCK.release()

    def draw(self) -> None:
        """Override draw to acquire the global lock."""
        if not MPL_LOCK.acquire(blocking=False):
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(50, self.draw)
            return

        try:
            super().draw()
        finally:
            MPL_LOCK.release()

    def resizeEvent(self, event) -> None:
        """Keep the loading overlay centered over the canvas."""
        super().resizeEvent(event)
        logger.info(f"FlowCanvas resized: {self.width()}x{self.height()}")
        if hasattr(self, "_overlay_manager"):
            self._overlay_manager.resize_loading(self.width(), self.height())

    # ── coordinate mapping ────────────────────────────────────────────

    def set_sample_id(self, sample_id: str) -> None:
        """Set the sample ID for event publication context."""
        self._sample_id = sample_id

    # ── Public API ────────────────────────────────────────────────────

    def set_data(self, events: pd.DataFrame) -> None:
        """Set the event data for this canvas.

        Args:
            events: DataFrame with columns matching axis parameters.
        """
        self._current_data = events
        self.redraw()

    def set_axes(
        self,
        x_param: str,
        y_param: str,
        x_label: str = "",
        y_label: str = "",
    ) -> None:
        """Update axis parameters and labels.

        Args:
            x_param: Column name for X axis.
            y_param: Column name for Y axis.
            x_label: Display label for X axis.
            y_label: Display label for Y axis.
        """
        self._x_param = x_param
        self._y_param = y_param
        self._x_label = x_label or x_param
        self._y_label = y_label or y_param
        # Update services with new parameters
        self._gate_factory.update_params(x_param, y_param)
        self.redraw()

    def set_scales(
        self,
        x_scale: AxisScale,
        y_scale: AxisScale,
    ) -> None:
        """Update the axis scaling configurations.

        Args:
            x_scale: Scale configuration for X axis.
            y_scale: Scale configuration for Y axis.
        """
        self._x_scale = x_scale
        self._y_scale = y_scale
        # Update services with new scales
        self._coordinate_mapper.update_scales(x_scale, y_scale)
        self._gate_factory.update_scales(x_scale, y_scale)
        self.redraw()

    def set_display_mode(self, mode: DisplayMode) -> None:
        """Change the plot display mode.

        Args:
            mode: One of the :class:`DisplayMode` values.
        """
        self._display_mode = mode
        self.redraw()

    def set_fmo_overlay(self, sample_id: str) -> None:
        """Set the FMO overlay sample ID and trigger a redraw."""
        self._fmo_sample_id = sample_id or None
        self.redraw()

    def set_drawing_mode(self, mode: GateDrawingMode) -> None:
        """Set the active gate drawing tool.

        Args:
            mode: The drawing mode to activate.
        """
        self._cancel_drawing()
        self._drawing_mode = mode

        from PyQt6.QtCore import Qt as _Qt

        if mode == GateDrawingMode.NONE:
            self.setCursor(_Qt.CursorShape.ArrowCursor)
            self._hide_instruction()
        else:
            self.setCursor(_Qt.CursorShape.CrossCursor)
            self._show_instruction(mode)

    def set_gates(self, gates: list[Gate], gate_nodes: list[GateNode] | None = None) -> None:
        """Set the gates to render as overlays.

        Args:
            gates:      List of Gate objects to render.
            gate_nodes: Optional matching GateNode list for stat labels.
        """
        self._active_gates = gates
        self._gate_nodes = gate_nodes or []
        # Only redraw the gate layer — never re-render the scatter data
        self._gate_renderer.render()

    def select_gate(self, gate_id: str | None) -> None:
        """Programmatically select a gate overlay."""
        self._selected_gate_id = gate_id
        self._gate_renderer.render()

    def _on_transform_changed(self) -> None:
        """Called when a transform is modified (e.g. logicle params).

        Invalidates the bitmap cache so the plot is fully re-rendered
        in the next frame with new scales applied to the data.
        """
        logger.info("FlowCanvas: Transform changed, invalidating cache.")
        self._canvas_bitmap_cache = None
        self.redraw()

    def _auto_range_axes(self) -> None:
        """Request parent window to re-calculate auto-range for active axes."""
        # This is typically called when switching to Full quality
        # to ensure the plot is centered on the real data boundaries.
        parent = self.parent()
        while parent and not hasattr(parent, "_calculate_auto_range"):
            parent = parent.parent()

        if parent:
            # We use the parent's logic to compute and apply new scales
            x_min, x_max = parent._calculate_auto_range("x")
            y_min, y_max = parent._calculate_auto_range("y")

            # Update local scales (parent will also sync globally)
            parent._x_scale.min_val = x_min
            parent._x_scale.max_val = x_max
            parent._y_scale.min_val = y_min
            parent._y_scale.max_val = y_max

            self.set_scales(parent._x_scale, parent._y_scale)
            # Notify the system to refresh thumbnails and sidebar
            parent._notify_axis_change()

    # ── Batch update ───────────────────────────────────────────────

    def begin_update(self) -> None:
        """Start a batch update — suppress intermediate redraws."""
        self._batch_update = True

    def end_update(self) -> None:
        """End batch — perform a single redraw with final state."""
        self._batch_update = False
        self.redraw()

    def redraw(self) -> None:
        """Full redraw: render data layer (expensive) + gate layer (cheap)."""
        if getattr(self, "_batch_update", False):
            return

        # If the canvas is 0x0, defer the redraw until it has a size.
        if self.width() <= 0 or self.height() <= 0:
            logger.warning("Canvas redraw deferred: size is 0x0. Setting timer for retry.")
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(200, self.redraw)
            return

        # Removed isVisible guard to ensure rendering even if Qt state is delayed
        self._dirty = False
        logger.info(
            "Canvas redraw triggered: data_size=%s, x=%s, y=%s, size=(%d, %d)",
            len(self._current_data) if self._current_data is not None else "None",
            self._x_param,
            self._y_param,
            self.width(),
            self.height(),
        )
        self._canvas_bitmap_cache = None  # Invalidate cached bitmap

        self._show_loading()

        # Defer the heavy data rendering by 50ms to allow the Qt event loop
        # to process the show_loading() call and paint the overlay.
        # Use a persistent timer to debounce multiple rapid redraw calls
        if not hasattr(self, "_redraw_timer"):
            from PyQt6.QtCore import QTimer

            self._redraw_timer = QTimer(self)
            self._redraw_timer.setSingleShot(True)
            self._redraw_timer.timeout.connect(self._perform_heavy_redraw)

        self._redraw_timer.start(50)

    def _perform_heavy_redraw(self) -> None:
        try:
            self._data_renderer.render()
        except Exception as exc:
            logger.exception("Canvas render failed: %s", exc)
            self._show_error(f"Render error: {exc}")
        finally:
            # Always hide the overlay — even if the render crashed.
            self._hide_loading()
        self._gate_renderer.render()
        self.draw()  # Forced immediate draw instead of idle

    def _show_loading(self) -> None:
        """Show the loading overlay, keeping it on top."""
        if hasattr(self, "_overlay_manager"):
            self._overlay_manager.show_loading()

    def _hide_loading(self) -> None:
        """Hide the loading overlay."""
        if hasattr(self, "_overlay_manager"):
            self._overlay_manager.hide_loading()

    def _render_data_layer(self) -> None:
        """Render the expensive scatter/histogram data.

        Delegated to DataLayerRenderer.
        """
        self._data_renderer.render()

    def _render_gate_layer(self) -> None:
        """Draw gate overlays on top of the cached data layer.

        Delegated to GateLayerRenderer.
        """
        self._gate_renderer.render()

    # ── Mouse event handlers — gate drawing state machine ─────────────

    def keyPressEvent(self, event) -> None:
        """Handle keyboard — Escape cancels drawing."""
        self._event_handler.handle_key_press(event)
        super().keyPressEvent(event)

    def _on_key_press(self, event) -> None:
        """Handle keyboard shortcuts for the canvas."""
        if getattr(event, "key", None) in ("f", "F"):
            self._auto_range_axes()

    def _on_draw(self, event) -> None:
        """Called by Matplotlib when a full draw is completed."""
        if getattr(self, "_use_cache", False):
            self._canvas_bitmap_cache = self._fig.canvas.copy_from_bbox(self._ax.bbox)  # type: ignore

    def _on_scroll(self, event) -> None:
        """Handle scroll wheel to zoom in and out."""
        self._zoom_handler.handle_scroll(event)

    def _on_press(self, event) -> None:
        """Handle mouse press — start drawing or select gate."""
        self._event_handler.handle_press(event)

    def _on_motion(self, event) -> None:
        """Handle mouse movement — rubber-band preview during drawing."""
        self._event_handler.handle_motion(event)

    def _on_release(self, event) -> None:
        """Handle mouse release — finalize gate drawing."""
        self._event_handler.handle_release(event)

    def _on_dblclick(self, event) -> None:
        """Handle double-click — close polygon."""
        self._event_handler.handle_dblclick(event)

    def _finalize_drag_gate(self, x0: float, y0: float, x1: float, y1: float, mode: str) -> None:
        self._event_handler.finalize_drag_gate(x0, y0, x1, y1, mode)

    def _finalize_rectangle(self, x0, y0, x1, y1):
        # Kept for backward compatibility if needed, but FSM calls _finalize_drag_gate
        self._event_handler.finalize_drag_gate(x0, y0, x1, y1, "rectangle")

    def _finalize_polygon(self, vertices: list[tuple[float, float]]) -> None:
        self._event_handler.finalize_polygon(vertices)

    def _finalize_ellipse(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self._event_handler.finalize_drag_gate(x0, y0, x1, y1, "ellipse")

    def _finalize_quadrant(self, x: float, y: float) -> None:
        self._event_handler.finalize_quadrant(x, y)

    def _finalize_range(self, x0: float, x1: float) -> None:
        self._event_handler.finalize_drag_gate(x0, 0, x1, 0, "range")

    def _try_select_gate(self, x: float, y: float) -> bool:
        return self._event_handler.try_select_gate(x, y)

    def _find_node_id_for_gate(self, gate_id: str) -> str | None:
        """Look up which node_id corresponds to this gate_id in active nodes."""
        for node in self._gate_nodes:
            if node.gate and node.gate.gate_id == gate_id:
                return node.node_id
        return None

    # ── Controller Event Handlers ─────────────────────────────────────

    def _on_controller_geometry_changed(self, sample_id: str, gate_id: str) -> None:
        """Update a specific gate overlay when its geometry changes elsewhere."""
        if sample_id != self._sample_id:
            return

        logger.debug(f"FlowCanvas: Handling geometry change for {gate_id}")
        self.update_gate_overlays()

    def _on_controller_selected(self, sample_id: str, node_id: str) -> None:
        """Update selection highlight when changed globally."""
        if sample_id != self._sample_id:
            return

        self._selected_gate_id = node_id if node_id else None
        self.gate_selected.emit(self._selected_gate_id)
        self._gate_renderer.render()

    def _on_controller_gate_removed(self, sample_id: str, node_id: str) -> None:
        if sample_id == self._sample_id:
            self.refresh_gates()

    def _on_controller_gate_renamed(self, sample_id: str, node_id: str) -> None:
        if sample_id == self._sample_id:
            self._gate_renderer.render()

    def refresh_gates(self) -> None:
        """Fetch the latest gates from the controller and re-render."""
        if self._controller and self._sample_id:
            # Note: parent_node_id could be passed if we want to support nested gating view
            # For now, we assume root-level display or that the controller knows the context.
            gates, nodes = self._controller.get_gates_for_display(self._sample_id)
            self.set_gates(gates, nodes)
        else:
            self._gate_renderer.render()

    def update_gate_overlays(self) -> None:
        """Backward-compatible alias for refreshing and re-rendering gates."""
        self.refresh_gates()

    def _cancel_drawing(self) -> None:
        """Cancel the active drawing operation."""
        self._fsm.cancel()
        self._hide_instruction()
        self._clear_previews()

    def _clear_drawing_state(self) -> None:
        """Backward-compatible alias for clearing the drawing state."""
        self._cancel_drawing()
        self._drawing_mode = GateDrawingMode.NONE

    def _setup_axis_ticks(self) -> None:
        """Backward-compatible alias for axis tick setup."""
        AxisFormatter(self).apply_formatting()

    def _show_instruction(self, mode: GateDrawingMode) -> None:
        if hasattr(self, "_overlay_manager"):
            self._overlay_manager.show_instruction(mode)

    def _update_instruction(self, text: str) -> None:
        if hasattr(self, "_overlay_manager"):
            self._overlay_manager.update_instruction(text)

    def _hide_instruction(self) -> None:
        if hasattr(self, "_overlay_manager"):
            self._overlay_manager.hide_instruction()

    # ── Internal helpers ──────────────────────────────────────────────

    def _show_empty(self) -> None:
        if hasattr(self, "_overlay_manager"):
            self._overlay_manager.show_empty()

    def _show_error(self, msg: str) -> None:
        if hasattr(self, "_overlay_manager"):
            self._overlay_manager.show_error(msg)

    # ── Context Menu ──────────────────────────────────────────────────

    def _on_context_menu(self, pos) -> None:
        """Show context menu on right click."""
        from PyQt6.QtGui import QAction
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY};"
            f" border: 1px solid {Colors.BORDER}; font-size: 11px; }}"
            f"QMenu::item:selected {{ background: {Colors.BG_MEDIUM}; }}"
        )

        # Copy to clipboard
        copy_act = QAction("📋  Copy to Clipboard (PNG)", self)
        copy_act.triggered.connect(self._copy_to_clipboard)
        menu.addAction(copy_act)

        menu.addSeparator()

        # Download submenu
        download_menu = menu.addMenu("💾  Download")
        if download_menu:
            for fmt, suffix in [("PNG", "png"), ("PDF", "pdf"), ("SVG", "svg")]:
                action = QAction(fmt, self)
                action.triggered.connect(lambda checked=False, f=suffix: self._on_download_plot(f))
                download_menu.addAction(action)

        menu.exec(self.mapToGlobal(pos))

    def _copy_to_clipboard(self) -> None:
        """Render figure to PNG in memory and copy to system clipboard."""
        import io

        from PyQt6.QtGui import QImage
        from PyQt6.QtWidgets import QApplication

        try:
            buf = io.BytesIO()
            self._fig.savefig(buf, format="png", dpi=96, bbox_inches="tight")
            buf.seek(0)
            image = QImage()
            image.loadFromData(buf.read())

            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setImage(image)
            logger.info("Plot copied to clipboard")
        except Exception as e:
            logger.error(f"Failed to copy plot: {e}")

    def _on_download_plot(self, fmt: str) -> None:
        """Download plot in specified format (png, pdf, or svg)."""
        from datetime import datetime

        from PyQt6.QtWidgets import QFileDialog

        # Generate default filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"flow_plot_{timestamp}.{fmt}"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save plot as {fmt.upper()}",
            default_name,
            f"{fmt.upper()} (*.{fmt})",
        )

        if not file_path:
            return

        try:
            # DPI settings for different formats
            dpi = 300 if fmt == "pdf" else 150
            self._fig.savefig(file_path, format=fmt, dpi=dpi, bbox_inches="tight")
            logger.info(f"Plot saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save plot: {e}")

    def _clear_previews(self) -> None:
        """Clear temporary gate previews across all views."""
        CentralEventBus.publish(events.GATE_PREVIEW, {"gate": None})
