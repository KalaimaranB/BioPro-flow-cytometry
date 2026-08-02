"""ZoomHandler — handles scroll zoom events for the canvas."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ..flow_canvas import FlowCanvas


class ZoomHandler:
    """Manages scroll-based zooming."""

    def __init__(self, canvas: FlowCanvas) -> None:
        self.canvas = canvas

    def handle_scroll(self, event) -> None:
        """Handle scroll wheel to zoom in and out."""
        if not event.inaxes:
            return

        base_scale = 1.2
        if event.button == "up":
            scale_factor = 1 / base_scale
        elif event.button == "down":
            scale_factor = base_scale
        else:
            return

        mapper = self.canvas._coordinate_mapper
        x_scale = self.canvas._x_scale
        y_scale = self.canvas._y_scale

        # Calculate new ranges in visual space
        x_min_vis = mapper.transform_x(np.array([x_scale.min_val]))[0]
        x_max_vis = mapper.transform_x(np.array([x_scale.max_val]))[0]
        y_min_vis = mapper.transform_y(np.array([y_scale.min_val]))[0]
        y_max_vis = mapper.transform_y(np.array([y_scale.max_val]))[0]

        # Apply zoom in visual space
        new_width = (x_max_vis - x_min_vis) * scale_factor
        new_height = (y_max_vis - y_min_vis) * scale_factor

        relx = (
            (x_max_vis - event.xdata) / (x_max_vis - x_min_vis)
            if x_max_vis != x_min_vis
            else 0.5
        )
        rely = (
            (y_max_vis - event.ydata) / (y_max_vis - y_min_vis)
            if y_max_vis != y_min_vis
            else 0.5
        )

        new_x_min = event.xdata - new_width * (1 - relx)
        new_x_max = event.xdata + new_width * relx
        new_y_min = event.ydata - new_height * (1 - rely)
        new_y_max = event.ydata + new_height * rely

        # Transform back to real values
        new_real_x_min = mapper.inverse_transform_x(np.array([new_x_min]))[0]
        new_real_x_max = mapper.inverse_transform_x(np.array([new_x_max]))[0]
        new_real_y_min = mapper.inverse_transform_y(np.array([new_y_min]))[0]
        new_real_y_max = mapper.inverse_transform_y(np.array([new_y_max]))[0]

        # Apply reasonably clamped values to scale
        parent = self.canvas.parent()
        while parent and not hasattr(parent, "_notify_axis_change"):
            parent = parent.parent()

        if parent:
            # Enforce some sanity limits (don't zoom out infinitely)
            parent._x_scale.min_val = max(-1e6, new_real_x_min)
            parent._x_scale.max_val = min(1e7, new_real_x_max)
            parent._y_scale.min_val = max(-1e6, new_real_y_min)
            parent._y_scale.max_val = min(1e7, new_real_y_max)

            # Avoid divide-by-zero on extreme zooms
            if parent._x_scale.max_val <= parent._x_scale.min_val:
                parent._x_scale.max_val = parent._x_scale.min_val + 1.0
            if parent._y_scale.max_val <= parent._y_scale.min_val:
                parent._y_scale.max_val = parent._y_scale.min_val + 1.0

            self.canvas._canvas_bitmap_cache = None
            parent._notify_axis_change()
            self.canvas.redraw()
