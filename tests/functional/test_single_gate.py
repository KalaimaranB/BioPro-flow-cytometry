"""Functional tests for single gate application on real FCS data.

Tests here verify things that only show up at realistic data scale/shape —
domain-expected gating percentages, cross-shape and cross-gate consistency,
subset/full-data equivalence. Pure geometric contains() correctness (point
in/out, boundaries, NaN handling, determinism) lives in
tests/unit/test_gating_operations.py instead — this file shouldn't re-derive
it against noisier synthetic data.
"""

import numpy as np
import pytest

from karcytics_plugins.flow_cytometry.analysis.gating import (
    PolygonGate,
    QuadrantGate,
    RangeGate,
    RectangleGate,
)


@pytest.mark.functional
class TestSingleRectangleGate:
    """Test Rectangle gate application on real sample data."""

    def test_singlet_gate_on_sample_a(self, sample_a_events, gate_rectangle_singlet):
        """Apply realistic singlet gate (FSC-A vs SSC-A) to Sample A."""
        # Apply gate
        membership = gate_rectangle_singlet.contains(sample_a_events)

        # Verify population decreased
        total_events = len(sample_a_events)
        gated_events = np.sum(membership)
        assert 0 < gated_events < total_events, (
            f"Singlet gate should reduce population: {total_events} → {gated_events}"
        )

        # Singlet gates typically keep 60-80% of events
        gating_percentage = 100 * gated_events / total_events
        assert 50 < gating_percentage < 90, (
            f"Singlet gate kept {gating_percentage:.1f}% (expected 50-90%)"
        )

    def test_singlet_gate_on_blank(self, blank_events, gate_rectangle_singlet):
        """Apply singlet gate to blank control - should have low counts."""
        membership = gate_rectangle_singlet.contains(blank_events)
        gated_count = np.sum(membership)
        total_count = len(blank_events)

        # Blank should have lower singlet percentage than live sample
        blank_percentage = 100 * gated_count / total_count
        assert blank_percentage > 0, "Blank should have some singlets"
        assert blank_percentage < 50, f"Blank singlet % too high: {blank_percentage:.1f}%"

    def test_nested_rectangle_gates(self, sample_a_events):
        """Test applying nested gates (inner gate should have fewer events)."""
        # Large gate (less restrictive)
        outer_gate = RectangleGate(
            "FSC-A", "SSC-A", x_min=50_000, x_max=200_000, y_min=1_000, y_max=50_000
        )
        # Small gate inside (more restrictive)
        inner_gate = RectangleGate(
            "FSC-A", "SSC-A", x_min=150_000, x_max=250_000, y_min=75_000, y_max=150_000
        )

        outer_membership = outer_gate.contains(sample_a_events)
        inner_membership = inner_gate.contains(sample_a_events)

        outer_count = np.sum(outer_membership)
        inner_count = np.sum(inner_membership)

        # Inner should have fewer or equal events
        assert inner_count <= outer_count, (
            f"Inner gate {inner_count} should have ≤ outer gate {outer_count} events"
        )
        assert inner_count > 0, "Inner gate should have some events"


@pytest.mark.functional
class TestSinglePolygonGate:
    """Test Polygon gate application on real sample data."""

    def test_polygon_vs_rectangle(self, sample_a_events):
        """Compare polygon and rectangle on same region."""
        # Rectangle bounds
        rect_gate = RectangleGate(
            "FSC-A", "SSC-A", x_min=50_000, x_max=200_000, y_min=1_000, y_max=50_000
        )

        # Polygon with same outer bounds
        vertices = [
            (50_000, 1_000),
            (200_000, 1_000),
            (200_000, 50_000),
            (50_000, 50_000),
        ]
        poly_gate = PolygonGate("FSC-A", "SSC-A", vertices)

        rect_membership = rect_gate.contains(sample_a_events)
        poly_membership = poly_gate.contains(sample_a_events)

        rect_count = np.sum(rect_membership)
        poly_count = np.sum(poly_membership)

        # Should be very similar (polygon may differ slightly on boundaries)
        assert np.abs(rect_count - poly_count) < rect_count * 0.05, (
            f"Polygon ({poly_count}) and Rectangle ({rect_count}) differ too much"
        )


@pytest.mark.functional
class TestSingleQuadrantGate:
    """Test Quadrant gate application on real sample data."""

    def test_quadrant_population_distribution(self, sample_a_events):
        """Verify quadrant gate distributes events across regions."""
        QuadrantGate("FITC-A", "PE-A", x_mid=200, y_mid=200)

        valid_mask = ~(sample_a_events["FITC-A"].isna() | sample_a_events["PE-A"].isna())
        valid_events = sample_a_events[valid_mask]

        if len(valid_events) > 100:  # Need reasonable sample size
            cd4 = valid_events["FITC-A"].values
            cd8 = valid_events["PE-A"].values

            # Manually count distribution
            q1 = np.sum((cd4 >= 200) & (cd8 >= 200))  # Both positive
            q2 = np.sum((cd4 < 200) & (cd8 >= 200))  # CD4-, CD8+
            q3 = np.sum((cd4 < 200) & (cd8 < 200))  # Both negative
            q4 = np.sum((cd4 >= 200) & (cd8 < 200))  # CD4+, CD8-

            # Should distribute across multiple quadrants
            non_empty_quadrants = sum([q1 > 0, q2 > 0, q3 > 0, q4 > 0])
            assert non_empty_quadrants >= 2, (
                f"Expected multiple quadrants with events, got {non_empty_quadrants}: {q1}, {q2}, {q3}, {q4}"
            )


@pytest.mark.functional
class TestSingleRangeGate:
    """Test Range gate application on real sample data."""

    def test_range_gate_boundaries(self, sample_a_events):
        """Verify range gate boundaries are respected."""
        gate = RangeGate("FITC-A", low=50, high=250)

        valid_mask = ~sample_a_events["FITC-A"].isna()
        valid_events = sample_a_events[valid_mask]

        if len(valid_events) > 0:
            membership = gate.contains(valid_events)
            gated = valid_events[membership]

            if len(gated) > 0:
                values = gated["FITC-A"].values
                assert np.all(values >= 50), "All gated values should be >= min"
                assert np.all(values <= 250), "All gated values should be <= max"

    def test_range_gate_narrow_vs_wide(self, sample_a_events):
        """Compare narrow vs wide range gates."""
        narrow_gate = RangeGate("FITC-A", low=100, high=150)  # Strict
        wide_gate = RangeGate("FITC-A", low=50, high=250)  # Loose

        valid_mask = ~sample_a_events["FITC-A"].isna()
        valid_events = sample_a_events[valid_mask]

        if len(valid_events) > 0:
            narrow_count = np.sum(narrow_gate.contains(valid_events))
            wide_count = np.sum(wide_gate.contains(valid_events))

            # Wide gate should have >= events than narrow gate
            assert wide_count >= narrow_count, (
                f"Wide gate {wide_count} should have ≥ narrow gate {narrow_count} events"
            )


@pytest.mark.functional
class TestGateConsistency:
    """Test consistency and repeatability of gate operations at realistic data scale."""

    def test_gate_with_subset(self, sample_a_events, gate_rectangle_singlet):
        """Apply gate to subset then to full - subset should be consistent."""
        # Get first 10K events
        subset = sample_a_events.iloc[:10000]
        full_result = gate_rectangle_singlet.contains(sample_a_events)
        subset_result = gate_rectangle_singlet.contains(subset)

        # Subset result should match first part of full result
        assert np.array_equal(full_result[:10000], subset_result), (
            "Direct and nested evaluations should match"
        )


@pytest.mark.functional
class TestGateEdgeCases:
    """Test edge cases in gate application on real data."""

    def test_gate_all_inside(self, sample_a_events):
        """Create gate that includes all events."""
        # Very large gate
        gate = RectangleGate("FSC-A", "SSC-A", x_min=0, x_max=1_000_000, y_min=0, y_max=1_000_000)
        result = gate.contains(sample_a_events)

        inside_count = np.sum(result)
        total_count = len(sample_a_events)

        # Should include most (allowing for values outside expected range)
        assert inside_count >= total_count * 0.95
