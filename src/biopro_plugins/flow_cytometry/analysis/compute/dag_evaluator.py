"""DAG Evaluator.

Handles evaluating boolean logic and subsetting for gate populations.
"""

import numpy as np
import pandas as pd
from biopro_sdk.plugin import get_logger

from ..gating import GateNode

logger = get_logger(__name__, "flow_cytometry")


class DagEvaluator:
    """Evaluates the boolean gating DAG over a set of events."""

    @staticmethod
    def evaluate(root: GateNode, events: pd.DataFrame) -> dict[str, dict]:  # noqa: C901, PLR0912, PLR0915
        """Evaluates the gate tree DAG and returns statistics for each node.

        Args:
            root: The root GateNode of the tree.
            events: A pandas DataFrame containing event data.

        Returns:
            A dictionary mapping node_id to statistics.
        """
        stats_out = {}
        all_nodes = []
        visited = set()

        def _collect(n: GateNode):
            if n.node_id in visited:
                return
            visited.add(n.node_id)
            all_nodes.append(n)
            for child in n.children:
                _collect(child)

        _collect(root)

        in_degrees = {n.node_id: len(n.parents) for n in all_nodes}
        ready = [n for n in all_nodes if in_degrees[n.node_id] == 0]
        total_count = len(events)
        evaluated_masks = {}

        while ready:
            node = ready.pop(0)

            if not node.parents:
                mask = np.ones(total_count, dtype=bool)
                parent_count = total_count
            else:
                parent_masks = [evaluated_masks[p.node_id] for p in node.parents]
                if node.logic_operator == "AND":
                    mask = parent_masks[0].copy()
                    for pm in parent_masks[1:]:
                        mask &= pm
                elif node.logic_operator == "OR":
                    mask = parent_masks[0].copy()
                    for pm in parent_masks[1:]:
                        mask |= pm
                elif node.logic_operator == "NOT":
                    mask = ~parent_masks[0]
                else:
                    mask = np.ones(total_count, dtype=bool)

                parent_count = np.sum(mask)

            if node.gate:
                try:
                    subset_events = events[mask].copy()
                    subset_mask = node.gate.contains(subset_events)
                    if getattr(node, "negated", False):
                        subset_mask = ~subset_mask

                    full_gate_mask = np.zeros(total_count, dtype=bool)
                    full_gate_mask[mask] = subset_mask
                    mask = full_gate_mask
                except Exception as e:
                    logger.warning("Gate evaluation failed for %s: %s", node.name, e)
                    mask = np.zeros(total_count, dtype=bool)

            evaluated_masks[node.node_id] = mask

            count = np.sum(mask)
            pct_parent = (count / parent_count * 100.0) if parent_count > 0 else 0.0
            pct_total = (count / total_count * 100.0) if total_count > 0 else 0.0

            node.statistics = {
                "count": int(count),
                "pct_parent": round(pct_parent, 2),
                "pct_total": round(pct_total, 2),
            }
            stats_out[node.node_id] = node.statistics

            for child in node.children:
                in_degrees[child.node_id] -= 1
                if in_degrees[child.node_id] == 0:
                    ready.append(child)

        return stats_out
