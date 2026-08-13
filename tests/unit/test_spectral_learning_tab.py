"""Smoke + math coverage for the Learning Compensation slide-deck.

Exercises the pure helpers directly, and drives a real ``SpectralLearningTab``
instance through all 7 slides via synthetic fluor data, simulating each
interaction (drag, click, type, slider) the way the UI would.
"""

import sys
import types

import numpy as np
import pytest
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

from karcytics_plugins.flow_cytometry.ui.widgets.spectral_learning_tab import (  # noqa: E402
    SpectralLearningTab,
    best_overlap_pairs,
    point_in_rect,
    rise_run_slope,
)


def flush_deferred():
    """Processes the event loop so a `QTimer.singleShot(0, ...)` (used to
    defer widget-destroying rebuilds out of the triggering widget's own
    signal handler — see SpectralLearningTab._defer) actually runs.
    """
    QTest.qWait(20)


def make_em_data(peak_nm, width=40, n=200):
    x = np.linspace(300, 800, n)
    y = np.exp(-0.5 * ((x - peak_nm) / width) ** 2)
    return np.column_stack([x, y])


@pytest.fixture
def fluors():
    return {
        "cd45": {"em_data": make_em_data(525), "display_label": "CD45", "color": "#58a6ff"},
        "cd3": {"em_data": make_em_data(575), "display_label": "CD3", "color": "#3fb950"},
        "cd4": {"em_data": make_em_data(660), "display_label": "CD4", "color": "#d2a8ff"},
        "cd8": {"em_data": make_em_data(700), "display_label": "CD8", "color": "#d29922"},
        "b220": {"em_data": make_em_data(450), "display_label": "B220", "color": "#ff7b72"},
        "pi": {"em_data": make_em_data(617), "display_label": "PI", "color": "#f0f6fc"},
    }


@pytest.fixture
def tab(fluors):
    viewer = types.SimpleNamespace(_active_fluors=fluors)
    return SpectralLearningTab(viewer=viewer)


class FakeEvent:
    def __init__(self, x, y, inaxes=True):
        self.xdata = x
        self.ydata = y
        self.inaxes = inaxes


def test_rise_run_slope():
    rise, run, slope = rise_run_slope(0, 0, 800, 200)
    assert rise == 200
    assert run == 800
    assert slope == pytest.approx(0.25)


def test_point_in_rect():
    assert point_in_rect(600, 600, 300, 300, 900, 900)
    assert not point_in_rect(100, 100, 300, 300, 900, 900)


def test_best_overlap_pairs_ordered_and_adjacent_dyes_overlap_more(fluors):
    pairs = best_overlap_pairs(fluors)
    assert pairs == sorted(pairs, key=lambda p: p[2], reverse=True)
    # cd45 (525nm) and cd3 (575nm) are close together and should overlap
    # more than cd45 and pi (617nm), which are further apart.
    by_pair = {frozenset((a, b)): pct for a, b, pct in pairs}
    assert by_pair[frozenset(("cd45", "cd3"))] > by_pair[frozenset(("cd45", "pi"))]


def test_slide_1_physics(tab):
    tab.update_view()
    tab._filter_center = tab._target_peak_x
    tab._slide1_filter_done = True
    tab.update_view()
    assert hasattr(tab, "_slide1_markers")

    # A click a few nm off the marker's exact x, but at the right height,
    # must still count — markers all share one x by construction, so an x/y
    # Euclidean distance would make this nearly unclickable in practice.
    mx, my = tab._slide1_markers[tab._slide1_correct_dye]
    tab._handle_slide1_click(FakeEvent(mx + 5, my))
    assert 0 in tab._completed_steps


def test_slide_1_wrong_click_gives_a_hint_without_corrupting_state(tab):
    tab.update_view()
    tab._filter_center = tab._target_peak_x
    tab._slide1_filter_done = True
    tab.update_view()

    wrong_names = [n for n in tab._slide1_markers if n != tab._slide1_correct_dye]
    assert wrong_names, "need at least one distractor marker to test a wrong click"
    wx, wy = tab._slide1_markers[wrong_names[0]]
    tab._handle_slide1_click(FakeEvent(wx, wy))
    assert 0 not in tab._completed_steps
    assert tab._slide1_wrong_hint is not None

    # A subsequent correct click still succeeds — one bad guess shouldn't
    # leave the slide stuck (this was the "infinitely stuck" bug: a broken
    # x/y distance metric made the correct marker nearly unhittable).
    mx, my = tab._slide1_markers[tab._slide1_correct_dye]
    tab._handle_slide1_click(FakeEvent(mx, my))
    assert 0 in tab._completed_steps
    assert tab._slide1_wrong_hint is None


def test_slide_2_unstained(tab):
    tab._current_step = 1
    tab.update_view()
    tab._on_html_link_clicked(types.SimpleNamespace(toString=lambda: "predict_correct"))
    tab.update_view()

    x0 = tab._slide2_crosshair.get_xdata()[0]
    y0 = tab._slide2_crosshair.get_ydata()[0]
    tab._on_canvas_click(FakeEvent(x0, y0))
    assert tab._drag_state == "crosshair"
    tab._on_canvas_mouse_move(FakeEvent(200, 200))
    tab._on_canvas_mouse_release(FakeEvent(200, 200))
    assert 1 in tab._completed_steps


def test_slide_3_ruler_and_typed_pct(tab):
    tab._current_step = 2
    tab.update_view()
    true_pct = tab._slide3_true_pct

    # The single-stain population clusters around x=800±70 (see
    # leaked_single_stain) — these are realistic "left/right side of the
    # cloud" clicks, not points near x=100 that no real data is anywhere
    # near (the ruler now snaps y to the real population, so x must be
    # somewhere the population actually is).
    tab._on_canvas_click(FakeEvent(650, 0))
    tab._on_canvas_mouse_move(FakeEvent(950, 0))
    tab._on_canvas_mouse_release(FakeEvent(950, 0))
    assert tab._ruler_ok
    tab.update_view()

    tab._answer_input.setText(f"{true_pct:.1f}")
    tab._check_slide3_pct()
    flush_deferred()
    assert 2 in tab._completed_steps


def test_slide_3_ruler_tolerates_imprecise_clicks(tab):
    """Regression: the ruler used to use the raw clicked (x, y) verbatim, so
    two clicks a few px apart on a noisy population could swing the measured
    slope well past the tolerance. Nearby x's snapped to the population's
    local median should all read out approximately the same slope.
    """
    tab._current_step = 2
    tab.update_view()

    for x0, x1 in [(640, 940), (660, 960), (650, 900)]:
        tab._ruler_points = []
        tab._ruler_ok = False
        tab._on_canvas_click(FakeEvent(x0, 0))
        tab._on_canvas_mouse_move(FakeEvent(x1, 0))
        tab._on_canvas_mouse_release(FakeEvent(x1, 0))
        assert tab._ruler_ok, f"ruler should tolerate a click at ({x0}, {x1})"


def test_snap_ruler_point_uses_only_nearby_points_not_the_whole_population(tab):
    """Regression: an earlier version fit ONE line through the entire
    population, so the ruler's reading never actually depended on where you
    clicked — only the x-separation did, meaning it always output the exact
    right answer and wasn't really "measuring" anything. Corrupting data far
    from the click must not move a snap point that's genuinely local.
    """
    tab._current_step = 2
    tab.update_view()

    near_x = 700.0
    baseline_y = tab._snap_ruler_point(near_x)[1]

    far_mask = np.abs(tab._slide3_x - near_x) > 200
    assert far_mask.any(), "need at least one far point for this test to mean anything"
    tab._slide3_y = tab._slide3_y.copy()
    tab._slide3_y[far_mask] += 5000.0

    corrupted_y = tab._snap_ruler_point(near_x)[1]
    assert corrupted_y == pytest.approx(baseline_y, abs=1.0)


def test_slide_3_ruler_rejects_endpoints_too_close_together(tab):
    tab._current_step = 2
    tab.update_view()

    tab._on_canvas_click(FakeEvent(700, 0))
    tab._on_canvas_mouse_move(FakeEvent(730, 0))
    tab._on_canvas_mouse_release(FakeEvent(730, 0))
    assert not tab._ruler_ok
    assert tab._ruler_hint is not None


def test_slide_4_predict_then_slider(tab):
    tab._current_step = 3
    tab.update_view()
    tab._on_canvas_click(FakeEvent(800, 10))
    assert tab._predicted_point is not None
    tab.update_view()

    _a, _b, pct = tab._teaching_pair()
    tab._slider_pct = pct
    tab._on_slide4_slider_release()
    flush_deferred()
    assert 3 in tab._completed_steps


def test_slide_4_slider_drag_does_not_stack_duplicate_controls(tab):
    """Regression: `_add_slider`/`_add_answer_input` nest their controls in a
    QHBoxLayout (addLayout, not addWidget); a shallow widget-only sweep in
    `_clear_interactive_widgets` left those rows behind, so dragging the
    slider (which re-renders on every valueChanged) stacked a fresh slider
    on top of the last one instead of replacing it.
    """
    tab._current_step = 3
    tab.update_view()
    tab._on_canvas_click(FakeEvent(800, 10))
    tab.update_view()
    assert tab._interactive_layout.count() == 1

    live_slider = tab._slider
    for value in (5, 15, 25, 35):
        tab._on_slider_moved(value)
        assert tab._interactive_layout.count() == 1
        # The crash: valueChanged used to trigger a full update_view(), which
        # destroys and rebuilds every interactive widget — including the
        # very slider mid-drag, while Qt still holds a mouse grab on it.
        # Dragging must move the SAME widget, never swap it out underneath
        # the live mouse grab.
        assert tab._slider is live_slider

    # Navigating to another slide must also fully clear slide 4's controls —
    # not leave them sitting underneath whatever the next slide adds.
    tab._current_step = 4
    tab.update_view()
    assert tab._interactive_layout.count() <= 1


def test_slide_4_slider_drag_moves_the_corrected_point(tab):
    tab._current_step = 3
    tab.update_view()
    tab._on_canvas_click(FakeEvent(800, 10))
    tab.update_view()

    _a, _b, pct = tab._teaching_pair()
    leak_y = 800.0 * pct / 100.0
    initial_y = tab._corrected_scatter.get_offsets()[0][1]
    assert initial_y == pytest.approx(leak_y)

    tab._on_slider_moved(round(pct))
    corrected_y = tab._corrected_scatter.get_offsets()[0][1]
    assert corrected_y == pytest.approx(0.0, abs=10.0)


def test_slide_4_slider_release_does_not_destroy_slider_synchronously(tab):
    """Regression: sliderReleased still fires from inside the slider's own
    event processing. Rebuilding _interactive_layout (which destroys this
    slider) *synchronously* inside that handler crashed on release, not just
    during the drag — the fix must defer the rebuild via QTimer.singleShot,
    so nothing should change until the event loop actually runs it.
    """
    tab._current_step = 3
    tab.update_view()
    tab._on_canvas_click(FakeEvent(800, 10))
    tab.update_view()

    _a, _b, pct = tab._teaching_pair()
    tab._slider_pct = pct
    live_slider = tab._slider

    tab._on_slide4_slider_release()
    # Nothing should have happened yet — the slider must still be intact.
    assert tab._slider is live_slider
    assert 3 not in tab._completed_steps

    flush_deferred()
    assert 3 in tab._completed_steps


def test_slide_5_predict_then_animate(tab):
    tab._current_step = 4
    tab.update_view()
    tab._on_canvas_click(FakeEvent(600, 100))
    assert tab._anim_prediction is not None
    tab._start_animation()
    for _ in range(60):
        tab._animate_step()
        if not tab._is_animating:
            break
    assert 4 in tab._completed_steps


def test_slide_6_gate(tab):
    tab._current_step = 5
    tab.update_view()
    tab._on_canvas_click(FakeEvent(400, 400))
    tab._on_canvas_mouse_move(FakeEvent(900, 900))
    tab._on_canvas_mouse_release(FakeEvent(900, 900))
    assert 5 in tab._completed_steps


def test_slide_7_wrong_mc_answer_gives_a_hint_without_advancing(tab):
    tab._current_step = 6
    tab.update_view()

    tab._on_html_link_clicked(types.SimpleNamespace(toString=lambda: "mc_both"))
    assert not tab._slide7_mc_correct
    assert tab._slide7_mc_hint is not None
    assert 6 not in tab._completed_steps


def test_slide_7_matrix_reasoning_requires_both_correct_answers(tab):
    """The final slide replaces the old capstone: it's a two-part reasoning
    task (which control isolates one dye's contribution, then how many total
    tubes a real panel needs) rather than a re-run of earlier mechanics.
    """
    tab._current_step = 6
    tab.update_view()
    n_dyes = len([d for d in tab._viewer._active_fluors.values() if "em_data" in d])

    tab._on_html_link_clicked(types.SimpleNamespace(toString=lambda: "mc_single"))
    assert tab._slide7_mc_correct
    assert 6 not in tab._completed_steps
    tab.update_view()

    tab._answer_input.setText(str(n_dyes))  # missing the unstained control
    tab._check_slide7_count()
    flush_deferred()
    assert not tab._slide7_count_correct
    assert 6 not in tab._completed_steps

    tab._answer_input.setText(str(n_dyes + 1))
    tab._check_slide7_count()
    flush_deferred()
    assert tab._slide7_count_correct
    assert 6 in tab._completed_steps
