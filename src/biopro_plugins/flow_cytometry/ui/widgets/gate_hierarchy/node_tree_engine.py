"""NodeTreeEngine — pure Python layout engine for Horizontal Flowcharts.

Calculates the x, y coordinates for a GateNode tree to be rendered
as a horizontal node-link diagram.
"""

from __future__ import annotations

from dataclasses import dataclass

from biopro_plugins.flow_cytometry.analysis.gating.gate_node import GateNode

# Depth-level color palette indices
_DEPTH_COLORS = [
    0,  # depth 0 root  → purple
    1,  # depth 1       → teal
    2,  # depth 2       → blue
    3,  # depth 3       → orange
    4,  # depth 4       → pink
    5,  # depth 5+      → green
]


@dataclass
class TreeNodeRect:
    """Geometry and metadata for one node in the flowchart."""

    node_id: str
    name: str
    depth: int
    x: float  # center x pixel
    y: float  # center y pixel
    width: float  # node width in pixels
    height: float  # node height in pixels
    parent_id: str | None = None
    color_index: int = 0

    # Statistics for HoverCard
    count: int = 0
    pct_parent: float = 0.0
    pct_total: float = 0.0
    gate_type: str = ""
    x_param: str = ""
    y_param: str = ""


class NodeTreeEngine:
    """Computes a leaf-driven horizontal tree layout."""

    def __init__(self):
        self.node_width = 110
        self.node_height = 50
        self.horizontal_spacing = 10
        self.vertical_spacing = 60

    def compute(self, root: GateNode, total_events: int = 0) -> list[TreeNodeRect]:
        """Compute the tree layout, centered horizontally.

        Args:
            root: Root GateNode.
            total_events: Fallback count for the root node if it has no statistics.

        Returns:
            List of TreeNodeRects, with X centered and a 20 px top margin.
        """
        self._leaf_counter = 0
        self._rects: list[TreeNodeRect] = []
        self._total_events_fallback = total_events

        # Pass 1: compute raw positions (X starts from 0, Y starts from 0)
        self._compute_post_order(root, depth=0, parent_id=None)

        if not self._rects:
            return self._rects

        # Pass 2: apply top padding + horizontal centering offset
        TOP_PADDING = 20
        all_x_left = [r.x - r.width / 2 for r in self._rects]
        all_x_right = [r.x + r.width / 2 for r in self._rects]
        max(all_x_right) - min(all_x_left)
        x_min = min(all_x_left)

        # We don't know the widget width here, so we store a (0-based) centered
        # layout by shifting so the tree's own left edge is at 0.
        # SampleViewWidget will add an additional centering offset in paintEvent.
        x_offset = -x_min  # shift so leftmost node starts at x=0

        for r in self._rects:
            r.x += x_offset
            r.y += TOP_PADDING

        return self._rects

    def _compute_post_order(self, node: GateNode, depth: int, parent_id: str | None) -> float:
        """Returns the X center of the current node."""
        gated_children = [c for c in node.children if c.gate is not None]

        if not gated_children:
            # It's a leaf node. Assign it the next available X slot.
            x_center = self._leaf_counter * (self.node_width + self.horizontal_spacing) + (
                self.node_width / 2
            )
            self._leaf_counter += 1
        else:
            # It has children. Its X center is the average of its children's X centers.
            child_x_centers = []
            for child in gated_children:
                child_x = self._compute_post_order(child, depth + 1, parent_id=node.node_id)
                child_x_centers.append(child_x)
            x_center = sum(child_x_centers) / len(child_x_centers)

        y_center = depth * (self.node_height + self.vertical_spacing) + (self.node_height / 2)

        gate = node.gate
        gate_type = type(gate).__name__.replace("Gate", "") if gate else ""
        x_param = getattr(gate, "x_param", "") if gate else ""
        y_param = getattr(gate, "y_param", "") if gate else ""

        # Fallback for root node if statistics haven't been computed yet
        count = int(node.statistics.get("count", 0))
        pct_parent = node.statistics.get("pct_parent", 0.0)
        pct_total = node.statistics.get("pct_total", 0.0)

        # If this is the root node and it has no stats (or default stats), grab count from fallback
        if node.is_root and count == 0 and pct_total >= 0.0:
            count = self._total_events_fallback
            pct_parent = 100.0
            pct_total = 100.0

        rect = TreeNodeRect(
            node_id=node.node_id,
            name=node.name,
            depth=depth,
            x=x_center,
            y=y_center,
            width=self.node_width,
            height=self.node_height,
            parent_id=parent_id,
            color_index=_DEPTH_COLORS[min(depth, len(_DEPTH_COLORS) - 1)],
            count=count,
            pct_parent=pct_parent,
            pct_total=pct_total,
            gate_type=gate_type,
            x_param=x_param,
            y_param=y_param,
        )
        self._rects.append(rect)
        return x_center
