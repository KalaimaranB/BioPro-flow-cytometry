"""TDD tests for the redesigned gate hierarchy panel.

Phase 1: IcicleLayoutEngine  — pure Python, no Qt
Phase 2: AllSamplesModel     — pure Python, no Qt
Phase 3: GateHierarchy API   — surface-level Qt smoke tests
"""

from __future__ import annotations

import pytest

from flow_cytometry.analysis.gating.gate_node import GateNode
from flow_cytometry.analysis.gating.rectangle import RectangleGate


# ──────────────────────────────────────────────────────────────────────────────
# Helpers — build minimal gate trees without FCS data
# ──────────────────────────────────────────────────────────────────────────────

def _make_rect_gate(x1=0.0, x2=0.5, y1=0.0, y2=0.5,
                    x_param="FSC-A", y_param="SSC-A") -> RectangleGate:
    return RectangleGate(
        x_param=x_param, y_param=y_param,
        x_min=x1, x_max=x2, y_min=y1, y_max=y2,
    )


def _make_simple_tree() -> GateNode:
    """Root → Lymphocytes (74.2%) + Debris (25.8%)."""
    root = GateNode(name="All Events")
    lymph = root.add_child(_make_rect_gate(), name="Lymphocytes")
    lymph.statistics = {"count": 35795, "pct_parent": 74.2, "pct_total": 74.2}
    debris = root.add_child(_make_rect_gate(x1=0.6, x2=1.0), name="Debris")
    debris.statistics = {"count": 12425, "pct_parent": 25.8, "pct_total": 25.8}
    return root


def _make_deep_tree() -> GateNode:
    """Root → Lympho (74.2%) → CD3 (52.1%) → CD4 (38.8%) + CD8 (22.4%)
                             → CD19 (18.3%)
             → Debris (25.8%)
    """
    root = GateNode(name="All Events")

    lymph = root.add_child(_make_rect_gate(), name="Lymphocytes")
    lymph.statistics = {"count": 35795, "pct_parent": 74.2, "pct_total": 74.2}

    cd3 = lymph.add_child(_make_rect_gate(), name="CD3+ T Cells")
    cd3.statistics = {"count": 18649, "pct_parent": 52.1, "pct_total": 38.7}

    cd4 = cd3.add_child(_make_rect_gate(), name="CD4+ Helper")
    cd4.statistics = {"count": 7236, "pct_parent": 38.8, "pct_total": 15.0}

    cd8 = cd3.add_child(_make_rect_gate(), name="CD8+ Cytotoxic")
    cd8.statistics = {"count": 4177, "pct_parent": 22.4, "pct_total": 8.7}

    cd19 = lymph.add_child(_make_rect_gate(), name="CD19+ B Cells")
    cd19.statistics = {"count": 6551, "pct_parent": 18.3, "pct_total": 13.6}

    debris = root.add_child(_make_rect_gate(x1=0.6, x2=1.0), name="Debris")
    debris.statistics = {"count": 12425, "pct_parent": 25.8, "pct_total": 25.8}

    return root


# ──────────────────────────────────────────────────────────────────────────────
# Phase 1 — IcicleLayoutEngine
# ──────────────────────────────────────────────────────────────────────────────

class TestIcicleLayoutEngine:

    def _engine(self):
        from flow_cytometry.ui.widgets.gate_hierarchy.layout_engine import IcicleLayoutEngine
        return IcicleLayoutEngine()

    def test_root_rect_spans_full_normalized_width(self):
        """Root node rect x=0.0, width=1.0 (normalized)."""
        engine = self._engine()
        rects = engine.compute(_make_simple_tree(), row_height=50, panel_width=260)
        root_rects = [r for r in rects if r.name == "All Events"]
        assert len(root_rects) == 1
        assert root_rects[0].x == pytest.approx(0.0)
        assert root_rects[0].width == pytest.approx(1.0)

    def test_children_proportional_to_pct_parent(self):
        """Lymphocytes 74.2% and Debris 25.8% divide the panel width proportionally."""
        engine = self._engine()
        rects = engine.compute(_make_simple_tree(), row_height=50, panel_width=260)
        lymph = next(r for r in rects if r.name == "Lymphocytes")
        debris = next(r for r in rects if r.name == "Debris")
        assert lymph.width == pytest.approx(0.742, abs=0.001)
        assert debris.width == pytest.approx(0.258, abs=0.001)
        assert lymph.width + debris.width == pytest.approx(1.0, abs=0.001)

    def test_child_aligned_under_parent_x_offset(self):
        """A child's x-offset starts at the same x as its parent rect."""
        engine = self._engine()
        rects = engine.compute(_make_deep_tree(), row_height=50, panel_width=260)
        lymph = next(r for r in rects if r.name == "Lymphocytes")
        cd3 = next(r for r in rects if r.name == "CD3+ T Cells")
        # CD3+ is first child of Lymphocytes → same x origin
        assert cd3.x == pytest.approx(lymph.x, abs=0.001)

    def test_ungated_remainder_created_when_children_dont_fill(self):
        """When CD3 + CD19 sum to 70.4% of Lymphocytes, an ungated rect fills the rest."""
        engine = self._engine()
        rects = engine.compute(_make_deep_tree(), row_height=50, panel_width=260)
        # CD3 (52.1%) + CD19 (18.3%) = 70.4% of Lymphocytes — not 100%
        ungated = [r for r in rects if r.is_ungated and r.depth == 2]
        assert len(ungated) == 1
        assert ungated[0].width == pytest.approx(1.0 - 0.521 - 0.183, abs=0.005)

    def test_depth_3_nodes_have_correct_row_index(self):
        """CD4+ and CD8+ are depth-3, so their row should be depth=3."""
        engine = self._engine()
        rects = engine.compute(_make_deep_tree(), row_height=50, panel_width=260)
        cd4 = next(r for r in rects if r.name == "CD4+ Helper")
        cd8 = next(r for r in rects if r.name == "CD8+ Cytotoxic")
        assert cd4.depth == 3
        assert cd8.depth == 3

    def test_zero_pct_node_gets_minimum_width(self):
        """A node with 0.0% still gets a minimum nonzero normalized width."""
        root = GateNode(name="All Events")
        ghost = root.add_child(_make_rect_gate(), name="Ghost")
        ghost.statistics = {"count": 0, "pct_parent": 0.0, "pct_total": 0.0}
        engine = self._engine()
        rects = engine.compute(root, row_height=50, panel_width=260)
        ghost_rect = next(r for r in rects if r.name == "Ghost")
        assert ghost_rect.width > 0.0

    def test_empty_tree_returns_only_root_rect(self):
        """A gate tree with no children produces only the root rect."""
        root = GateNode(name="All Events")
        engine = self._engine()
        rects = engine.compute(root, row_height=50, panel_width=260)
        assert len(rects) == 1
        assert rects[0].name == "All Events"

    def test_sibling_rects_do_not_overlap(self):
        """Lymphocytes and Debris rects must not overlap (x + width <= debris.x)."""
        engine = self._engine()
        rects = engine.compute(_make_simple_tree(), row_height=50, panel_width=260)
        lymph = next(r for r in rects if r.name == "Lymphocytes")
        debris = next(r for r in rects if r.name == "Debris")
        assert lymph.x + lymph.width <= debris.x + 0.001


# ──────────────────────────────────────────────────────────────────────────────
# Phase 2 — AllSamplesModel
# ──────────────────────────────────────────────────────────────────────────────

class TestAllSamplesModel:

    def _model(self):
        from flow_cytometry.ui.widgets.gate_hierarchy.all_samples_model import AllSamplesModel
        return AllSamplesModel()

    def _make_state_two_samples(self):
        """Build a minimal FlowState with two samples sharing the same gate tree."""
        from unittest.mock import MagicMock
        from flow_cytometry.analysis.state import FlowState
        from flow_cytometry.analysis.experiment import Experiment, Sample

        state = FlowState()
        state.experiment = Experiment()

        tree = _make_simple_tree()

        for sid, name, pcts in [
            ("s1", "Sample 1", {"Lymphocytes": 74.2, "Debris": 25.8}),
            ("s2", "Sample 2", {"Lymphocytes": 68.0, "Debris": 32.0}),
        ]:
            s = Sample(sample_id=sid, display_name=name)
            s.fcs_data = MagicMock()
            # Build per-sample tree with different stats
            s_tree = GateNode(name="All Events")
            for child in tree.children:
                node = s_tree.add_child(child.gate, name=child.name)
                node.statistics = {
                    "count": 1000,
                    "pct_parent": pcts[child.name],
                    "pct_total": pcts[child.name],
                }
            s.gate_tree = s_tree
            state.experiment.samples[sid] = s

        return state

    def test_rows_match_reference_sample_depth_first_order(self):
        """Rows follow depth-first order of the reference sample's tree."""
        state = self._make_state_two_samples()
        model = self._model()
        model.build(state, reference_sample_id="s1")
        row_names = [row.name for row in model.rows]
        assert row_names == ["Lymphocytes", "Debris"]

    def test_cell_value_is_pct_parent(self):
        """Cell value for (Lymphocytes, s2) equals s2's pct_parent for Lymphocytes."""
        state = self._make_state_two_samples()
        model = self._model()
        model.build(state, reference_sample_id="s1")
        lymph_row = next(r for r in model.rows if r.name == "Lymphocytes")
        assert lymph_row.cells["s2"] == pytest.approx(68.0, abs=0.1)

    def test_ungated_sample_cell_is_none(self):
        """A sample without a matching population returns None, not 0."""
        state = self._make_state_two_samples()
        # Remove Lymphocytes gate from s2
        state.experiment.samples["s2"].gate_tree = GateNode(name="All Events")
        model = self._model()
        model.build(state, reference_sample_id="s1")
        lymph_row = next(r for r in model.rows if r.name == "Lymphocytes")
        assert lymph_row.cells["s2"] is None

    def test_tree_branch_last_child_uses_elbow(self):
        """Last child of a parent uses the └─ connector string."""
        state = self._make_state_two_samples()
        model = self._model()
        model.build(state, reference_sample_id="s1")
        debris_row = next(r for r in model.rows if r.name == "Debris")
        assert "└" in debris_row.branch_str

    def test_tree_branch_non_last_child_uses_tee(self):
        """Non-last child of a parent uses the ├─ connector string."""
        state = self._make_state_two_samples()
        model = self._model()
        model.build(state, reference_sample_id="s1")
        lymph_row = next(r for r in model.rows if r.name == "Lymphocytes")
        assert "├" in lymph_row.branch_str

    def test_rebuild_on_reference_change(self):
        """Changing the reference sample ID and rebuilding updates rows."""
        state = self._make_state_two_samples()
        model = self._model()
        model.build(state, reference_sample_id="s1")
        first_order = [r.name for r in model.rows]
        model.build(state, reference_sample_id="s2")
        second_order = [r.name for r in model.rows]
        # Same names since both samples share same gate names; just verify no crash
        assert set(first_order) == set(second_order)

    def test_sample_ids_match_experiment(self):
        """model.sample_ids matches the keys in the experiment."""
        state = self._make_state_two_samples()
        model = self._model()
        model.build(state, reference_sample_id="s1")
        assert set(model.sample_ids) == {"s1", "s2"}
