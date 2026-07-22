"""Gate layer rendering for FlowCanvas."""

from __future__ import annotations

from typing import TYPE_CHECKING

from biopro_sdk.plugin import get_logger

if TYPE_CHECKING:
    from ..flow_canvas import FlowCanvas

logger = get_logger(__name__, "flow_cytometry")


class GateLayerRenderer:
    """Handles rendering of gate overlays and labels."""

    def __init__(self, canvas: FlowCanvas) -> None:
        self.canvas = canvas

    def render(self) -> None:
        """Draw gate overlays on top of the cached data layer."""
        canvas = self.canvas
        # Remove previous gate artists
        for artist in canvas._gate_artists:
            try:
                artist.remove()
            except (ValueError, AttributeError, NotImplementedError):
                pass
        canvas._gate_artists.clear()
        canvas._gate_patches.clear()

        # Draw new gate overlays
        self._redraw_gate_overlays()

        # Re-show instruction text if a tool is active
        from ..flow_canvas import GateDrawingMode

        if canvas._drawing_mode != GateDrawingMode.NONE:
            canvas._show_instruction(canvas._drawing_mode)

        canvas.draw_idle()

    def _redraw_gate_overlays(self) -> None:
        """Draw all active gate overlays on the axes."""
        canvas = self.canvas
        ax = canvas._ax
        canvas._gate_patches.clear()
        canvas._gate_overlay_artists.clear()

        recorded_geometries = set()
        from ..flow_canvas import _GATE_PALETTE, _GATE_SELECTED_EDGE, DisplayMode

        # Determine if we are in a 1D display mode
        _1d_modes = (DisplayMode.HISTOGRAM, DisplayMode.CDF)
        is_1d_mode = canvas._display_mode in _1d_modes

        # Only RangeGate makes sense on a 1D plot. Import lazily to avoid circular deps.
        from ....analysis.gating import RangeGate

        for i, gate in enumerate(canvas._active_gates):
            # On 1D plots, skip any gate that isn't a RangeGate
            if is_1d_mode and not isinstance(gate, RangeGate):
                continue

            # Only draw gates that belong on these axes
            if gate.x_param != canvas._x_param:
                continue
            # For 2D gates also check y_param
            if (
                not is_1d_mode
                and hasattr(gate, "y_param")
                and gate.y_param != canvas._y_param
            ):
                continue

            # If it's a subgate, we track its parent to avoid drawing the same crosshairs 4 times
            geometry_id = (
                gate.parent.gate_id if hasattr(gate, "parent") else gate.gate_id
            )
            if geometry_id in recorded_geometries:
                continue
            recorded_geometries.add(geometry_id)

            # If it's a subgate, selection of ANY of the 4 quadrants should highlight the crosshairs?
            # Wait, if we select Q1, it highlights. If we select Q2, it highlights.
            # But the gate_id in canvas._selected_gate_id is the QuadrantSubGate's ID.
            is_selected = gate.gate_id == canvas._selected_gate_id

            # Check if any sharing nodes are selected (to cover all subgates of the same parent)
            if hasattr(gate, "parent"):
                # if ANY child of the parent is selected, highlight the crosshairs
                parent_subgate_ids = [
                    f"{geometry_id}_{q}" for q in ["Q1", "Q2", "Q3", "Q4"]
                ]
                if canvas._selected_gate_id in parent_subgate_ids:
                    is_selected = True

            color = _GATE_PALETTE[i % len(_GATE_PALETTE)]
            edge_color = _GATE_SELECTED_EDGE if is_selected else color

            sharing_nodes = [
                n
                for n in canvas._gate_nodes
                if n.gate and n.gate.gate_id == gate.gate_id
            ]
            if not sharing_nodes:
                continue

            # Use the new GateOverlayRenderer service
            artists = canvas._gate_overlay_renderer.render_gate(
                ax, gate, is_selected, edge_color
            )

            if artists:
                canvas._gate_overlay_artists[gate.gate_id] = {
                    "patch": artists.patch,
                    "gate": gate,
                    "artists": artists,
                }
                if artists.patch:
                    canvas._gate_artists.append(artists.patch)
                if artists.label_text:
                    canvas._gate_artists.append(artists.label_text)
                if artists.handles:
                    for h in artists.handles.values():
                        canvas._gate_artists.append(h)
