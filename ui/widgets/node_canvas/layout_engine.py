"""Auto-layout algorithms for the Node Canvas."""

from __future__ import annotations
from collections import defaultdict, deque
from typing import Any


class LayoutEngine:
    """Computes X/Y coordinates for a tree of nodes.

    Uses a BFS max-depth approach with Sugiyama-style column ordering:
    - Each node gets the *maximum* depth across all paths from root, ensuring
      all parents always sit to the left of their children (DAG-safe).
    - Within each column, nodes are sorted by the average Y coordinate of their
      parents (left-to-right pass). This keeps sibling groups visually adjacent
      and prevents wires from passing through unrelated nodes.
    """

    X_SPACING = 320
    Y_SPACING = 330

    @classmethod
    def compute_layout(cls, root_node: Any, items_dict: dict[str, Any]) -> None:
        if not root_node or not root_node.children:
            if root_node and root_node.node_id in items_dict:
                items_dict[root_node.node_id].setPos(0, 0)
            return

        # ── Pass 1: BFS to compute max-depth for every reachable node ────────
        depth: dict[str, int] = {root_node.node_id: 0}
        all_nodes: dict[str, Any] = {}   # node_id -> GateNode
        queue: deque = deque([root_node])
        visited: set = set()

        while queue:
            node = queue.popleft()
            if node.node_id in visited:
                continue
            visited.add(node.node_id)
            all_nodes[node.node_id] = node
            current_depth = depth[node.node_id]
            for child in node.children:
                child_depth = current_depth + 1
                if child.node_id not in depth or child_depth > depth[child.node_id]:
                    depth[child.node_id] = child_depth
                queue.append(child)

        # ── Pass 2: Group nodes by depth ─────────────────────────────────────
        nodes_by_depth: dict[int, list[Any]] = defaultdict(list)
        for nid, node in all_nodes.items():
            nodes_by_depth[depth[nid]].append(node)

        # ── Pass 3: Assign Y positions column-by-column (left → right) ───────
        # For each column, sort nodes by the average Y of their parents so that
        # sibling subtrees stay vertically grouped and wires don't cross nodes.
        assigned_y: dict[str, float] = {}

        for d in sorted(nodes_by_depth.keys()):
            nodes = nodes_by_depth[d]

            if d == 0:
                # Root column — single node, center at 0
                for node in nodes:
                    assigned_y[node.node_id] = 0.0
            else:
                # Sort by mean parent Y so sibling groups are contiguous
                def parent_y_key(node: Any) -> float:
                    real_parents = [p for p in node.parents
                                    if p.node_id in assigned_y and not p.is_root
                                    or (p.is_root and p.node_id in assigned_y)]
                    if not real_parents:
                        # Fallback: use whatever parents have been assigned
                        ys = [assigned_y[p.node_id] for p in node.parents
                              if p.node_id in assigned_y]
                        return sum(ys) / len(ys) if ys else 0.0
                    ys = [assigned_y[p.node_id] for p in real_parents]
                    return sum(ys) / len(ys)

                nodes = sorted(nodes, key=parent_y_key)

                # Center the column around the mean parent Y of the whole column
                all_parent_ys = [parent_y_key(n) for n in nodes]
                col_center = sum(all_parent_ys) / len(all_parent_ys) if all_parent_ys else 0.0

                n = len(nodes)
                total_height = (n - 1) * cls.Y_SPACING
                start_y = col_center - total_height / 2.0

                for i, node in enumerate(nodes):
                    assigned_y[node.node_id] = start_y + i * cls.Y_SPACING

            # Apply X/Y to scene items
            for node in nodes_by_depth[d]:
                item = items_dict.get(node.node_id)
                if item:
                    item.setPos(d * cls.X_SPACING, assigned_y.get(node.node_id, 0.0))
