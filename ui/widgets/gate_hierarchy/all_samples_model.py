"""AllSamplesModel — pure Python cross-sample statistics matrix.

Single Responsibility: assemble the (population × sample) data matrix
and the tree-branch connector strings. Zero Qt dependency — fully
unit-testable.

Dependency Inversion: the model reads from FlowState via attribute
access, but never stores a live reference beyond the build() call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ....analysis.gating.gate_node import GateNode


@dataclass
class PopulationRow:
    """One row in the All-Samples matrix."""

    node_id: str
    name: str
    depth: int
    branch_str: str          # e.g. "├─" or "└─" or "│  ├─"
    color_index: int         # matches IcicleLayoutEngine depth palette
    cells: dict[str, Optional[float]] = field(default_factory=dict)
    # cells[sample_id] = pct_parent float, or None if gate not applied


class AllSamplesModel:
    """Build and expose the population-×-sample statistics matrix.

    Usage::

        model = AllSamplesModel()
        model.build(state, reference_sample_id="s1")
        for row in model.rows:
            for sid in model.sample_ids:
                value = row.cells[sid]  # float or None
    """

    def __init__(self) -> None:
        self.rows: list[PopulationRow] = []
        self.sample_ids: list[str] = []
        self.sample_display_names: dict[str, str] = {}

    def build(self, state, reference_sample_id: str) -> None:
        """Rebuild the matrix from current FlowState.

        Args:
            state:                 FlowState (read-only).
            reference_sample_id:  The sample whose gate tree defines row order.
        """
        self.rows = []
        self.sample_ids = list(state.experiment.samples.keys())
        self.sample_display_names = {
            sid: s.display_name
            for sid, s in state.experiment.samples.items()
        }

        ref_sample = state.experiment.samples.get(reference_sample_id)
        if ref_sample is None:
            return

        ref_tree = ref_sample.gate_tree

        # Depth-first walk of the reference tree to establish row order
        self._walk(ref_tree.children, state, prefix="", is_last_flags=[], depth=1)

    # ── Private ──────────────────────────────────────────────────────────

    def _walk(
        self,
        nodes: list[GateNode],
        state,
        prefix: str,
        is_last_flags: list[bool],
        depth: int,
    ) -> None:
        gated = [n for n in nodes if n.gate is not None]
        for i, node in enumerate(gated):
            is_last = (i == len(gated) - 1)
            branch_str = self._make_branch(is_last_flags, is_last)
            color_idx = min(depth - 1, 5)

            # Collect per-sample stats
            cells: dict[str, Optional[float]] = {}
            for sid, sample in state.experiment.samples.items():
                matched = sample.gate_tree.find_node_by_id(node.node_id)
                if matched is None:
                    # Try matching by name (handles propagated trees with new node_ids)
                    matched = self._find_by_name(sample.gate_tree, node.name, depth)
                if matched is not None and matched.statistics:
                    cells[sid] = float(matched.statistics.get("pct_parent", 0.0))
                else:
                    cells[sid] = None

            self.rows.append(PopulationRow(
                node_id=node.node_id,
                name=node.name,
                depth=depth,
                branch_str=branch_str,
                color_index=color_idx,
                cells=cells,
            ))

            # Recurse
            self._walk(
                node.children,
                state,
                prefix=prefix,
                is_last_flags=is_last_flags + [is_last],
                depth=depth + 1,
            )

    @staticmethod
    def _make_branch(is_last_flags: list[bool], is_last: bool) -> str:
        """Build the ├─ / └─ connector with │ continuation lines."""
        parts = []
        for flag in is_last_flags:
            parts.append("   " if flag else "│  ")
        parts.append("└─" if is_last else "├─")
        return "".join(parts)

    @staticmethod
    def _find_by_name(tree: GateNode, name: str, target_depth: int) -> Optional[GateNode]:
        """Fallback: search tree by name at the expected depth."""
        def _search(node: GateNode, current_depth: int) -> Optional[GateNode]:
            if current_depth == target_depth and node.name == name:
                return node
            for child in node.children:
                found = _search(child, current_depth + 1)
                if found:
                    return found
            return None
        return _search(tree, 0)
