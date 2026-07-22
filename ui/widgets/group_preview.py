"""Group Preview Panel — shows low-res renders of all samples in a group.

Refactored to use AxisManager, PopulationService, and RenderTask.
"""

from __future__ import annotations

from typing import Any

from biopro.core.task_scheduler import task_scheduler
from biopro.ui.theme import Colors
from biopro_sdk.plugin import CentralEventBus, get_logger
from PyQt6.QtCore import QPointF, Qt, QTimer
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from biopro.plugins.flow_cytometry.analysis import events
from biopro.plugins.flow_cytometry.analysis.constants import (
    PREVIEW_THUMBNAIL_SIZE,
)
from biopro.plugins.flow_cytometry.analysis.state import FlowState
from biopro.plugins.flow_cytometry.ui.graph.flow_services import CoordinateMapper

logger = get_logger(__name__, "flow_cytometry")


class PreviewThumbnail(QFrame):
    """A single sample thumbnail in the preview grid."""

    def __init__(
        self,
        sample_id: str,
        state: FlowState,
        axis_manager: Any = None,
        population_service: Any = None,
        parent=None,
    ):
        super().__init__(parent)
        self._sample_id = sample_id
        self._state = state
        self._axis_manager = axis_manager
        self._population_service = population_service
        self._last_params = None
        self._current_task_id = None

        # Overlay caching
        self._base_pixmap = None
        self._x_range = None
        self._y_range = None

        self._setup_ui()

        # Connect to global signals ONLY ONCE
        task_scheduler.task_finished.connect(self._on_global_task_finished)
        task_scheduler.task_error.connect(self._on_global_task_error)

    def _setup_ui(self):
        self.setFixedWidth(PREVIEW_THUMBNAIL_SIZE[0] + 8)
        self.setMinimumHeight(PREVIEW_THUMBNAIL_SIZE[1] + 24)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet(
            f"background: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; border-radius: 4px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._img = QLabel()
        self._img.setFixedSize(*PREVIEW_THUMBNAIL_SIZE)
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img.setScaledContents(True)  # Enable High-DPI scaling
        self._img.setStyleSheet("background: white; border: 1px solid #DDDDDD;")
        layout.addWidget(self._img)

        sample = self._state.data.experiment.samples.get(self._sample_id)
        display_name = sample.display_name if sample else self._sample_id
        self._name = QLabel(display_name)
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name.setWordWrap(True)
        layout.addWidget(self._name)

        self.refresh_styles()

    def refresh_styles(self) -> None:
        """Dynamically refresh colors when theme changes."""
        self.setStyleSheet(
            f"background: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; border-radius: 4px;"
        )
        self._name.setStyleSheet(
            f"color: {Colors.FG_SECONDARY}; font-size: 9px; padding: 2px;"
        )

    def preview_temp_gate(self, temp_gate) -> None:
        """Draw a temporary gate over the cached base pixmap instantly."""
        if not self._base_pixmap or not self._x_range or not self._y_range:
            return

        x_param = self._state.view.active_x_param
        y_param = self._state.view.active_y_param

        if temp_gate.x_param != x_param:
            return

        x_scale = self._axis_manager.get_scale(x_param)
        y_scale = self._axis_manager.get_scale(y_param) if y_param else None

        mapper = CoordinateMapper(x_scale, y_scale)

        try:
            import numpy as np

            x_min_disp = mapper.transform_x(np.array([self._x_range[0]]))[0]
            x_max_disp = mapper.transform_x(np.array([self._x_range[1]]))[0]
            x_disp_span = x_max_disp - x_min_disp

            y_min_disp, y_max_disp, y_disp_span = 0, 0, 1
            if y_scale and self._y_range:
                y_min_disp = mapper.transform_y(np.array([self._y_range[0]]))[0]
                y_max_disp = mapper.transform_y(np.array([self._y_range[1]]))[0]
                y_disp_span = y_max_disp - y_min_disp

            overlay = self._base_pixmap.copy()
            w, h = overlay.width(), overlay.height()

            def to_px(x_data, y_data):
                xd = mapper.transform_x(np.array([x_data]))[0]
                px = (xd - x_min_disp) / x_disp_span * w
                if y_scale:
                    yd = mapper.transform_y(np.array([y_data]))[0]
                    # Qt Y goes down, so we invert
                    py = h - ((yd - y_min_disp) / y_disp_span * h)
                else:
                    py = 0
                return px, py

            painter = QPainter(overlay)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor("#800080"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)

            if hasattr(temp_gate, "vertices"):
                pts = [QPointF(*to_px(v[0], v[1])) for v in temp_gate.vertices]
                if len(pts) > 1:
                    painter.drawPolyline(pts)
                if len(pts) > 2:
                    painter.drawLine(pts[-1], pts[0])  # Close polygon
            elif hasattr(temp_gate, "x_min"):
                px1, py1 = to_px(temp_gate.x_min, temp_gate.y_max)  # top-left
                px2, py2 = to_px(temp_gate.x_max, temp_gate.y_min)  # bottom-right
                painter.drawRect(int(px1), int(py1), int(px2 - px1), int(py2 - py1))
            elif hasattr(temp_gate, "center"):
                cx, cy = temp_gate.center
                cpx, cpy = to_px(cx, cy)

                # Approximate width/height in pixels
                x2, _ = to_px(cx + temp_gate.width / 2, cy)
                _, y2 = to_px(cx, cy + temp_gate.height / 2)

                painter.drawEllipse(QPointF(cpx, cpy), abs(x2 - cpx), abs(y2 - cpy))
            elif hasattr(temp_gate, "low"):
                px1, _ = to_px(temp_gate.low, 0)
                px2, _ = to_px(temp_gate.high, 0)
                painter.drawLine(int(px1), 0, int(px1), h)
                painter.drawLine(int(px2), 0, int(px2), h)

            painter.end()
            self._img.setPixmap(overlay)
            self._img.update()
        except Exception as e:
            logger.error(f"Overlay drawing failed: {e}")

    def request_render(
        self,
        active_sample_id: str | None = None,
        active_node_id: str | None = None,
        peer_node_id: str | None = None,
    ):
        """Submit a background render task for this thumbnail."""
        x_param = self._state.view.active_x_param
        y_param = self._state.view.active_y_param
        plot_type = self._state.view.active_plot_type

        # Use AxisManager to get current scales (synced with main canvas)
        x_scale = self._axis_manager.get_scale(x_param, active_sample_id)
        y_scale = self._axis_manager.get_scale(y_param, active_sample_id)

        x_range = (
            (x_scale.min_val, x_scale.max_val) if x_scale.min_val is not None else None
        )
        y_range = (
            (y_scale.min_val, y_scale.max_val) if y_scale.min_val is not None else None
        )

        gate_id = None

        # Collect gates to render (children of the active sample's current node + temp gate)
        gates_to_show = []
        if active_sample_id:
            if active_node_id:
                active_node = self._population_service.find_node(
                    active_sample_id, active_node_id
                )
            else:
                active_node = self._population_service.get_root_node(active_sample_id)

            if active_node:
                logger.info(
                    f"GroupPreviewPanel: active_node={active_node.name}, children={len(active_node.children)}"
                )
                for child in active_node.children:
                    if child.gate:
                        gates_to_show.append(child.gate)
                        logger.info(
                            f"GroupPreviewPanel: added gate {child.gate.gate_id} ({child.gate.x_param}/{child.gate.y_param}) to gates_to_show (current axes: {x_param}/{y_param})"
                        )

        logger.info(
            f"GroupPreviewPanel: submitting RenderTask for {self._sample_id} with {len(gates_to_show)} gates"
        )

        # Cache invalidation check
        geom_key = None
        scale_key = (x_scale.min_val, x_scale.max_val, y_scale.min_val, y_scale.max_val)
        gate_ids_key = tuple(g.gate_id for g in gates_to_show)
        fmo_sample_id = self._state.view.active_fmo_sample_id

        # We need the render config in the cache key so changes to UI settings (like FMO colors) invalidate the cache
        rc = self._state.view.render_config
        rc_key = str(rc.to_dict())

        current_params = (
            x_param,
            y_param,
            peer_node_id,
            gate_id,
            geom_key,
            scale_key,
            plot_type,
            active_sample_id,
            active_node_id,
            gate_ids_key,
            fmo_sample_id,
            rc_key,
        )
        if current_params == self._last_params:
            return
        self._last_params = current_params

        # Configure and submit RenderTask
        from ..graph.render_task import RenderTask

        task = RenderTask()
        w, h = PREVIEW_THUMBNAIL_SIZE[0] * 2, PREVIEW_THUMBNAIL_SIZE[1] * 2

        # Pass quality settings to RenderTask
        rc = self._state.view.render_config

        # Subplots are much smaller than the main plot, so we scale down the maximum events
        # proportionally to maintain visual density parity with the main plot.
        # Use roughly 15% of the main plot's event limit.
        subplot_event_ratio = 0.15
        max_events = int(rc.max_events * subplot_event_ratio)

        # Point size 0.5 is usually good for thumbnails
        point_size = 0.5

        rc_dict = rc.to_dict()
        rc_dict["show_gate_labels"] = False
        rc_dict["show_axis_labels"] = False

        task.configure(
            sample_id=self._sample_id,
            peer_node_id=peer_node_id,
            x_param=x_param,
            y_param=y_param,
            x_scale=x_scale,
            y_scale=y_scale,
            x_range=x_range,
            y_range=y_range,
            width_px=w,
            height_px=h,
            plot_type=plot_type,
            max_events=max_events,
            quality_multiplier=1.0,  # Thumbnails always use 1.0 grid mult for speed
            gates=gates_to_show,
            selected_gate_id=self._state.view.current_gate_id,
            s=point_size,
            render_config=rc_dict,
            fmo_sample_id=self._state.view.active_fmo_sample_id,
        )

        worker = task_scheduler.submit(task, self._state)
        self._current_task_id = (
            worker.task_id
        )  # submit() returns the worker; the ID is on .task_id

    def _on_global_task_finished(self, tid: str, results: dict) -> None:
        if str(tid) == str(getattr(self, "_current_task_id", None)):
            self._on_render_done(results)

    def _on_global_task_error(self, tid: str, error_msg: str) -> None:
        if str(tid) == str(getattr(self, "_current_task_id", None)):
            logger.warning(f"Render error for {self._sample_id}: {error_msg}")

    def _on_render_done(self, results: dict) -> None:
        """Called on the UI thread when the off-thread render completes."""
        if "error" in results:
            logger.warning(f"Render error for {self._sample_id}: {results['error']}")
            return

        buf = results.get("image_data")
        if not buf:
            logger.warning(
                f"PreviewThumbnail: Received empty buffer for {self._sample_id}"
            )
            return

        w, h = results["width"], results["height"]
        logger.info(
            f"PreviewThumbnail: Received {len(buf)} bytes for {self._sample_id} ({w}x{h})"
        )

        # Force a copy of the buffer so it doesn't get garbage collected
        try:
            # Use RGBA8888 to correctly map the RGBA buffer from Matplotlib
            # (RGB32 incorrectly swaps red and blue channels on little-endian systems)
            qimg = QImage(buf, w, h, QImage.Format.Format_RGBA8888).copy()
            self._base_pixmap = QPixmap.fromImage(qimg)
            self._img.setPixmap(self._base_pixmap)

            # Save range for fast QPainter overlay
            self._x_range = results.get("x_range")
            self._y_range = results.get("y_range")

            self._img.update()
        except Exception as e:
            logger.error(f"Failed to load image buffer for {self._sample_id}: {e}")


class GroupPreviewPanel(QWidget):
    """Panel showing previews for all samples in a group."""

    def __init__(
        self,
        state: FlowState,
        sample_id: str | None = None,
        axis_manager: Any = None,
        population_service: Any = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._axis_manager = axis_manager
        self._population_service = population_service
        self._current_sample_id: str | None = sample_id
        self._current_node_id: str | None = None
        self._thumbnails: dict[str, PreviewThumbnail] = {}
        self._setup_ui()
        self._setup_events()

        # Throttle timer for real-time gate previews
        from ...analysis.constants import PREVIEW_THROTTLE_MS

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(PREVIEW_THROTTLE_MS)
        self._preview_timer.timeout.connect(self._do_throttled_refresh)
        self._pending_temp_gate = None

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        hdr = QLabel("👥 Group Preview")
        hdr.setStyleSheet(
            f"color: {Colors.FG_SECONDARY}; font-size: 10px; font-weight: 700;"
        )
        layout.addWidget(hdr)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(f"background: {Colors.BG_DARKEST};")

        self._container = QWidget()
        self._container.setStyleSheet(f"background: {Colors.BG_DARKEST};")
        self._grid = QGridLayout(self._container)
        self._grid.setContentsMargins(4, 4, 4, 4)
        self._grid.setSpacing(12)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll)
        self.setMinimumHeight(200)
        self.setObjectName("GroupPreviewPanel")

        self.refresh_styles()

    def refresh_styles(self) -> None:
        """Dynamically refresh colors when theme changes."""
        self._scroll.setStyleSheet(f"background: {Colors.BG_DARKEST};")
        self._container.setStyleSheet(f"background: {Colors.BG_DARKEST};")
        for thumb in self._thumbnails.values():
            thumb.refresh_styles()

    def _setup_events(self) -> None:
        CentralEventBus.subscribe(
            events.AXIS_PARAMS_CHANGED, lambda _: self._refresh_all()
        )
        CentralEventBus.subscribe(
            events.AXIS_RANGE_CHANGED, lambda _: self._refresh_all()
        )
        CentralEventBus.subscribe(
            events.TRANSFORM_CHANGED, lambda _: self._refresh_all()
        )
        CentralEventBus.subscribe(events.GATE_CREATED, lambda _: self._rebuild())
        CentralEventBus.subscribe(events.GATE_MODIFIED, lambda _: self._refresh_all())
        CentralEventBus.subscribe(events.GATE_DELETED, lambda _: self._rebuild())
        CentralEventBus.subscribe(
            events.DISPLAY_MODE_CHANGED, lambda _: self._refresh_all()
        )
        CentralEventBus.subscribe(events.FMO_CHANGED, lambda _: self._refresh_all())
        CentralEventBus.subscribe(
            events.RENDER_CONFIG_CHANGED, lambda _: self._refresh_all()
        )
        CentralEventBus.subscribe(events.GATE_PREVIEW, self._on_gate_preview)

    def _on_gate_preview(self, data: dict) -> None:
        """Handle real-time gate drawing preview."""
        self._pending_temp_gate = data.get("gate")
        if not self._preview_timer.isActive():
            self._preview_timer.start()

    def _do_throttled_refresh(self) -> None:
        """Execute the refresh with the latest pending preview gate."""
        if self._pending_temp_gate:
            # Fast path overlay via QPainter
            for thumb in self._thumbnails.values():
                thumb.preview_temp_gate(self._pending_temp_gate)
        else:
            # Full rebuild needed
            self._refresh_all()

        self._pending_temp_gate = None

    def update_context(self, sample_id: str, node_id: str | None) -> None:
        if sample_id == self._current_sample_id and node_id == self._current_node_id:
            self._refresh_all()
            return
        self._current_sample_id = sample_id
        self._current_node_id = node_id
        self._rebuild()

    def _rebuild(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._thumbnails.clear()

        if not self._current_sample_id:
            return

        sample = self._state.data.experiment.samples.get(self._current_sample_id)
        if not sample:
            return

        peers = []
        gid = None
        if sample.group_ids:
            gid = list(sample.group_ids)[0]
            peers = [
                s
                for s in self._state.data.experiment.samples.values()
                if gid in s.group_ids and s.sample_id != self._current_sample_id
            ]

        # Fallback: if no group peers, show all other samples in experiment
        if not peers:
            logger.info(
                "GroupPreviewPanel._rebuild: no group peers found, falling back to all samples."
            )
            peers = [
                s
                for s in self._state.data.experiment.samples.values()
                if s.sample_id != self._current_sample_id
            ]

        logger.info(
            f"GroupPreviewPanel._rebuild: found {len(peers)} samples to preview (group={gid})"
        )
        for i, p in enumerate(peers):
            thumb = PreviewThumbnail(
                p.sample_id,
                self._state,
                axis_manager=self._axis_manager,
                population_service=self._population_service,
            )
            self._thumbnails[p.sample_id] = thumb
            self._grid.addWidget(thumb, i // 2, i % 2)
            peer_node_id = self._get_parallel_node(
                self._current_sample_id, self._current_node_id, p.sample_id
            )
            thumb.request_render(
                self._current_sample_id, self._current_node_id, peer_node_id
            )

    def _refresh_all(self) -> None:
        for thumb in self._thumbnails.values():
            peer_node_id = self._get_parallel_node(
                self._current_sample_id, self._current_node_id, thumb._sample_id
            )
            thumb.request_render(
                self._current_sample_id, self._current_node_id, peer_node_id
            )

    def _get_parallel_node(
        self,
        source_sample_id: str | None,
        source_node_id: str | None,
        target_sample_id: str,
    ) -> str | None:
        """Find the equivalent gate node ID in another sample by name path."""
        if not source_sample_id or not source_node_id:
            return None

        source_sample = self._state.data.experiment.samples.get(source_sample_id)
        target_sample = self._state.data.experiment.samples.get(target_sample_id)
        if not source_sample or not target_sample:
            return None

        curr_node = source_sample.gate_tree.find_node_by_id(source_node_id)
        if not curr_node:
            return None

        path = []
        c = curr_node
        while c and not c.is_root:
            path.append(c.name)
            c = c.parents[0] if c.parents else None
        path.reverse()

        t_node = target_sample.gate_tree
        for p_name in path:
            matched = False
            for child in t_node.children:
                if child.name == p_name:
                    t_node = child
                    matched = True
                    break
            if not matched:
                break

        if t_node and not t_node.is_root:
            return t_node.node_id
        return None
