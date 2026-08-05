"""BioPro Flow Cytometry — Academy Courses.

Step conventions:
  InfoStep              — teaches a concept; user clicks Next → to continue.
  InteractionStep       — user must click/interact with a named widget to auto-advance.
  VerificationStep      — auto-polls a validator every ~2 s and advances automatically.
                          Set allow_interaction=True only if the user also needs to freely
                          interact with the UI before clicking the manual 'Check ✓' button.
  BranchingStep         — presents options that route to different next steps (quizzes).
  ForcedInteractionStep — requires ALL of its sub_tasks to complete before advancing.

Spotlight convention:
  target_widget_name  — single objectName for InteractionStep highlight.
  target_widget_names — list of objectNames for multi-target InfoStep spotlights.

Panel reference (confirmed from the tutorial FCS file headers, $PnN/$PnS):
  CD45 = APC-A          | FMO APC
  CD3  = Pacific Blue-A | FMO e450 (this dataset names the Pacific-Blue FMO control "e450")
  CD4  = PE-A           | FMO PE
  CD8  = APC-Cy7-A      | FMO APCCy7
  B220 = FITC-A         | FMO FITC
  PI   = PerCP-Cy5-5-A  | (viability, single stain)
"""

from biopro.core.models.tutorial_models import (
    BranchingStep,
    Course,
    ForcedInteractionStep,
    InfoStep,
    InteractionStep,
    SubTask,
    VerificationStep,
)

from .validators import (
    AxisChannelValidator,
    Course1StateValidator,
    ExactSampleOpenValidator,
    GateAbsentValidator,
    GateActiveValidator,
    GateExistsValidator,
    LearningCompensationCompleteValidator,
    PipelineOrientationValidator,
    SpectralFluorsLoadedValidator,
    TabActiveValidator,
)

# ==============================================================================
# Course 2 — Immunophenotyping, Pipeline & Spectral Mastery
# Finale of the intro content: gate T-cells, B-cells, and split T-cells into
# CD4/CD8. End goal is a preliminary call on what Samples A/B/C are — Course 3
# formally proves it with statistics and population analysis.
# ==============================================================================

course_2_gating = Course(
    id="flow_course_2_gating",
    title="Immunophenotyping, Pipeline & Spectral Mastery",
    description=(
        "Identify T-cells and B-cells inside your Leukocytes, split T-cells into "
        "CD4/CD8 with a Quadrant gate, master the Pipeline view, and understand "
        "spillover and compensation theory."
    ),
    estimated_minutes=45,
    badge_reward="Immunophenotyper",
    badge_icon="🧬",
    prerequisite_course_ids=["flow_course_1_fundamentals"],
    steps=[
        # ── Checkpoint ───────────────────────────────────────────────────────
        VerificationStep(
            id="c2_s00_verify",
            validator=Course1StateValidator(),
            text=(
                "Checking your workspace...\n\n"
                "Making sure all 10 samples are loaded, roles are assigned, and the "
                "base gates (Cells → Live Cells → Leukocytes) exist."
            ),
            allow_interaction=False,
            cyto_emotion="thinking",
            next_step_id="c2_s01_intro",
        ),
        InfoStep(
            id="c2_s01_intro",
            text=(
                "Welcome to Course 2! 🎯\n\n"
                "Our Leukocytes are gated. Now let's identify who's actually inside "
                "that population: T-cells, B-cells, and — critically — whether those "
                "T-cells are CD4+ helpers, CD8+ killers, or both.\n\n"
                "By the end of this course you'll make your own call on what Samples "
                "A, B, and C actually are. Course 3 will prove it with hard numbers."
            ),
            cyto_emotion="happy",
            cyto_animation="cheering",
            next_step_id="c2_s02_open_sample",
        ),
        VerificationStep(
            id="c2_s02_open_sample",
            text="Double-click 'Sample A' in the Data hierarchy to open it in a Graph Window.",
            validator=ExactSampleOpenValidator("sample a"),
            allow_interaction=True,
            cyto_emotion="pointing",
            target_widget_names=["SampleList"],
            on_success_step_id="c2_s03_tcell_intro",
        ),
        # ── T-cells (traditional 2-axis technique, reusing Course 1's skill) ────
        InfoStep(
            id="c2_s03_tcell_intro",
            text=(
                "Gate 1: T-cells (CD3+) 🧬\n\n"
                "CD3 is the pan-T-cell marker. We'll gate it exactly the way you "
                "gated Leukocytes in Course 1: CD3 vs SSC-A, FMO-anchored, Rectangle tool.\n\n"
                "First, open the FMO control for CD3 to see the true background."
            ),
            cyto_emotion="talking",
            next_step_id="c2_s04_open_fmo_pb",
        ),
        InteractionStep(
            id="c2_s04_open_fmo_pb",
            text=(
                "Double-click 'FMO e450' in the Sample List to open it.\n\n"
                "In this panel, CD3 sits on the Pacific Blue-A detector — the tutorial "
                "files just label that FMO control 'e450' (same violet-laser channel family)."
            ),
            target_widget_name="SampleList",
            target_widget_names=["SampleList"],
            event_trigger="sample_double_clicked",
            cyto_emotion="pointing",
            next_step_id="c2_s04b_verify_fmo",
        ),
        VerificationStep(
            id="c2_s04b_verify_fmo",
            text="Checking opened sample...",
            cyto_emotion="scanning",
            hide_next_button=True,
            allow_interaction=False,
            validator=ExactSampleOpenValidator("FMO e450"),
            on_success_step_id="c2_s05_set_axis_pb",
            on_fail_step_id="c2_s04c_fmo_fail",
        ),
        InteractionStep(
            id="c2_s04c_fmo_fail",
            text="Oops! Please double-click the 'FMO e450' sample to open it.",
            cyto_emotion="surprised",
            target_widget_name="SampleList",
            target_widget_names=["SampleList"],
            event_trigger="sample_double_clicked",
            next_step_id="c2_s04b_verify_fmo",
        ),
        VerificationStep(
            id="c2_s05_set_axis_pb",
            text=(
                "Set the X axis to 'Pacific Blue-A' (the CD3 detector).\n\n"
                "All events should be bunched near zero — that's pure background, "
                "since this file has every dye except the CD3 antibody."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["AxisSelectorX"],
            validator=AxisChannelValidator("pacific blue"),
            on_success_step_id="c2_s06_reopen_a",
        ),
        InteractionStep(
            id="c2_s06_reopen_a",
            text=(
                "Now double-click 'Sample A' again.\n\n"
                "BioPro preserves your gating context and axis — you'll land right "
                "back on CD3 vs SSC-A, inside Leukocytes, on the full panel this time."
            ),
            target_widget_name="SampleList",
            target_widget_names=["SampleList"],
            event_trigger="sample_double_clicked",
            cyto_emotion="pointing",
            next_step_id="c2_s07_draw_tcell",
        ),
        VerificationStep(
            id="c2_s07_draw_tcell",
            text=(
                "Draw the T-cells gate:\n\n"
                "1. Select the 'Rect' tool.\n"
                "2. Start just past where the FMO background ended (~X=10²) and drag "
                "all the way right, covering the full SSC-A height — the same move "
                "you used for Leukocytes in Course 1.\n"
                "3. Name it 'T-cells'.\n\n"
                "BioPro is scanning automatically..."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["Tool_rectangle", "FlowCanvas"],
            validator=GateExistsValidator("t-cells"),
            on_success_step_id="c2_s08_tcell_done",
        ),
        InfoStep(
            id="c2_s08_tcell_done",
            text=(
                "T-cells gated! ✅\n\n"
                "That's the 'traditional' technique — the same FMO-anchored, "
                "2-axis Rectangle gate you already know. B-cells will use a "
                "different, faster technique."
            ),
            cyto_emotion="happy",
            next_step_id="c2_s09_bcell_intro",
        ),
        # ── B-cells (Histogram + FMO Overlay technique) ─────────────────────────
        InfoStep(
            id="c2_s09_bcell_intro",
            text=(
                "Gate 2: B-cells (B220+) 🎨\n\n"
                "B220 is the pan-B-cell marker. This time we'll use a faster "
                "technique: a Histogram with a live FMO overlay and an "
                "auto-computed threshold line — no need to eyeball anything.\n\n"
                "First, go back up to the Leukocytes population — B-cells are a "
                "sibling of T-cells, not nested inside it."
            ),
            cyto_emotion="talking",
            next_step_id="c2_s10_back_to_leuko",
        ),
        VerificationStep(
            id="c2_s10_back_to_leuko",
            text=(
                "Click 'Leukocytes' in the Gating Hierarchy panel (highlighted) to "
                "make it the active population again."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["GatingHierarchySampleView"],
            validator=GateActiveValidator("leukocytes"),
            on_success_step_id="c2_s11_histogram_mode",
        ),
        InteractionStep(
            id="c2_s11_histogram_mode",
            text=(
                "Switch the Display Mode dropdown (above the plot) from "
                "'Pseudocolor' to 'Histogram'."
            ),
            target_widget_name="DisplayModeCombo",
            target_widget_names=["DisplayModeCombo"],
            event_trigger="activated",
            cyto_emotion="pointing",
            next_step_id="c2_s12_set_x_b220",
        ),
        VerificationStep(
            id="c2_s12_set_x_b220",
            text="Set the X axis to 'FITC-A' — the B220 detector.",
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["AxisSelectorX"],
            validator=AxisChannelValidator("fitc"),
            on_success_step_id="c2_s13_fmo_overlay",
        ),
        InteractionStep(
            id="c2_s13_fmo_overlay",
            text=(
                "Now use the 'FMO Overlay:' dropdown (next to the axis selectors) "
                "and select the FMO FITC control.\n\n"
                "Watch what happens: the FMO's histogram appears in gray behind "
                "your real data in blue, and BioPro auto-switches your drawing "
                "tool to 'Range' for you."
            ),
            target_widget_name="AxisSelectorFMO",
            target_widget_names=["AxisSelectorFMO"],
            event_trigger="currentTextChanged",
            cyto_emotion="pointing",
            next_step_id="c2_s14_threshold_info",
        ),
        InfoStep(
            id="c2_s14_threshold_info",
            text=(
                "Behind the Scenes: The 99th-Percentile Threshold 📏\n\n"
                "See the red dashed line labeled '99th %tile (Gate Threshold)'? "
                "BioPro computed that automatically from the FMO control's "
                "distribution — 99% of the true background sits to its left.\n\n"
                "That line is your scientifically defensible cutoff: anything to "
                "the right is real B220 signal, not spillover noise."
            ),
            cyto_emotion="talking",
            next_step_id="c2_s15_draw_bcell",
        ),
        VerificationStep(
            id="c2_s15_draw_bcell",
            text=(
                "Click and drag horizontally starting at (or just past) the red "
                "threshold line, capturing the bright B220+ peak.\n\n"
                "Name the gate 'B-cells'."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["FlowCanvas"],
            validator=GateExistsValidator("b-cells"),
            on_success_step_id="c2_s16_bcell_done",
        ),
        InfoStep(
            id="c2_s16_bcell_done",
            text=(
                "B-cells gated! ✅\n\n"
                "Two different techniques, same rigor: both are anchored to their "
                "FMO control's true background, not a guess."
            ),
            cyto_emotion="happy",
            next_step_id="c2_s17_quadrant_intro",
        ),
        # ── CD4/CD8 Quadrant split — Course 2 finale ────────────────────────────
        InfoStep(
            id="c2_s17_quadrant_intro",
            text=(
                "Finale: Splitting T-cells by CD4/CD8 ✂️\n\n"
                "Not all T-cells are equal — CD4+ helpers, CD8+ killers, and (in "
                "some tissues) cells that are BOTH CD4+ and CD8+ 'Double Positive' "
                "(DP), or neither, 'Double Negative' (DN).\n\n"
                "A single Quadrant gate splits a plot into all 4 regions at once."
            ),
            cyto_emotion="thinking",
            next_step_id="c2_s18_open_tcells",
        ),
        VerificationStep(
            id="c2_s18_open_tcells",
            text="Click 'T-cells' in the Gating Hierarchy panel to make it the active population.",
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["GatingHierarchySampleView"],
            validator=GateActiveValidator("t-cells"),
            on_success_step_id="c2_s19_axes_fmo_info",
        ),
        InfoStep(
            id="c2_s19_axes_fmo_info",
            text=(
                "Set X = 'PE-A' (CD4) and Y = 'APC-Cy7-A' (CD8).\n\n"
                "As usual, briefly open FMO PE and FMO APCCy7 to see where each "
                "marker's true background sits before you draw — same anchoring "
                "habit you've now used three times."
            ),
            cyto_emotion="talking",
            allow_interaction=True,
            target_widget_names=["AxisSelectorX", "AxisSelectorY"],
            next_step_id="c2_s20_draw_quadrant",
        ),
        InteractionStep(
            id="c2_s20_draw_quadrant",
            text=(
                "Click the 'Quadrant' tool (highlighted), then click once on the "
                "plot where the CD4-/CD8- and CD4+/CD8+ boundaries should sit, "
                "anchored just past the FMO backgrounds on each axis."
            ),
            target_widget_name="Tool_quadrant",
            event_trigger="clicked",
            cyto_emotion="thinking",
            next_step_id="c2_s21_rename_info",
        ),
        InfoStep(
            id="c2_s21_rename_info",
            text=(
                "Behind the Scenes: Quadrant Naming ⚠️\n\n"
                "The 4 new leaves in your Gating Hierarchy are named 'Q1'–'Q4' — "
                "whatever you typed in the naming popup only labels the parent "
                "Quadrant gate itself, not the 4 regions.\n\n"
                "With X=CD4, Y=CD8, the geometry is fixed:\n"
                "  Q1 (upper-left)  = CD4− CD8+  → 'CD8+ only'\n"
                "  Q2 (upper-right) = CD4+ CD8+  → 'DP'\n"
                "  Q3 (lower-left)  = CD4− CD8−  → 'DN'\n"
                "  Q4 (lower-right) = CD4+ CD8−  → 'CD4+ only'\n\n"
                "Click each leaf in the Gating Hierarchy (or on the Pipeline "
                "canvas), then rename it using the Name field in the Properties "
                "Panel on the right."
            ),
            cyto_emotion="talking",
            target_widget_names=["GatingHierarchySampleView", "PropertiesPanel"],
            next_step_id="c2_s22_rename_quadrants",
        ),
        ForcedInteractionStep(
            id="c2_s22_rename_quadrants",
            text=(
                "Rename all 4 quadrant leaves. Watch the DP count especially — "
                "it's going to be very different across the three mystery samples!"
            ),
            cyto_emotion="thinking",
            allow_interaction=True,
            target_widget_names=["PropertiesPanel"],
            sub_tasks=[
                SubTask(
                    id="rename_q4_cd4",
                    instruction="Select 'Q4' (lower-right) and rename it to 'CD4+ only'.",
                    target_widget_name="PropertiesPanel",
                    event_trigger="editingFinished",
                    validator=GateExistsValidator("cd4+ only"),
                ),
                SubTask(
                    id="rename_q1_cd8",
                    instruction="Select 'Q1' (upper-left) and rename it to 'CD8+ only'.",
                    target_widget_name="PropertiesPanel",
                    event_trigger="editingFinished",
                    validator=GateExistsValidator("cd8+ only"),
                ),
                SubTask(
                    id="rename_q2_dp",
                    instruction="Select 'Q2' (upper-right) and rename it to 'DP'.",
                    target_widget_name="PropertiesPanel",
                    event_trigger="editingFinished",
                    validator=GateExistsValidator("dp"),
                ),
                SubTask(
                    id="rename_q3_dn",
                    instruction="Select 'Q3' (lower-left) and rename it to 'DN'.",
                    target_widget_name="PropertiesPanel",
                    event_trigger="editingFinished",
                    validator=GateExistsValidator("dn"),
                ),
            ],
            next_step_id="c2_s23_quadrant_done",
        ),
        InfoStep(
            id="c2_s23_quadrant_done",
            text=(
                "Immunophenotyping complete! 🎉\n\n"
                "T-cells, B-cells, and 4 CD4/CD8 subsets, all FMO-anchored. Let's "
                "copy this entire strategy to Samples B and C for a fair comparison."
            ),
            cyto_emotion="happy",
            next_step_id="c2_s24_propagate",
        ),
        InteractionStep(
            id="c2_s24_propagate",
            text="Click '📋 Copy Gates' (highlighted) to propagate everything to Samples B and C.",
            target_widget_name="CopyGatesButton",
            event_trigger="clicked",
            cyto_emotion="pointing",
            next_step_id="c2_s25_hypothesis_intro",
        ),
        # ── Preliminary hypothesis ───────────────────────────────────────────────
        InfoStep(
            id="c2_s25_hypothesis_intro",
            text=(
                "Time to make a call. 🔍\n\n"
                "Open Sample B and Sample C in turn (or scroll the Group Preview "
                "thumbnails) and compare the DP (CD4+CD8+) percentage inside "
                "T-cells across all three samples.\n\n"
                "One tissue is famous for producing huge numbers of Double "
                "Positive cells as immune cells mature there — that's your tell."
            ),
            cyto_emotion="thinking",
            allow_interaction=True,
            target_widget_names=["SampleList", "GroupPreviewPanel", "PropertiesPanel"],
            next_step_id="c2_s26_hypothesis_quiz",
        ),
        BranchingStep(
            id="c2_s26_hypothesis_quiz",
            text="Lock in your hypothesis: which sample is the Thymus?",
            options={
                "Sample A": "c2_s27_hypothesis_wrong",
                "Sample B": "c2_s28_pipeline_switch",
                "Sample C": "c2_s27_hypothesis_wrong",
            },
        ),
        InfoStep(
            id="c2_s27_hypothesis_wrong",
            text=(
                "Not quite! Look for the sample with a dramatically higher DP "
                "percentage than the other two — almost all its T-cells should "
                "be Double Positive."
            ),
            cyto_emotion="sad",
            next_step_id="c2_s26_hypothesis_quiz",
        ),
        # ── Pipeline mastery ─────────────────────────────────────────────────────
        InteractionStep(
            id="c2_s28_pipeline_switch",
            text=(
                "Correct — Sample B is the Thymus! 🎉\n\n"
                "Course 3 will prove this with hard numbers, and untangle Spleen "
                "from Bone Marrow too. For now, click the 'Pipeline' tab at the top."
            ),
            cyto_emotion="cheering",
            target_widget_name="MainTabBar",
            target_widget_names=["MainTabBar"],
            event_trigger="currentChanged",
            next_step_id="c2_s29_pipeline_read",
        ),
        InfoStep(
            id="c2_s29_pipeline_read",
            text=(
                "The Pipeline view 🌿\n\n"
                "Your entire gating strategy as a flowchart: Leukocytes splits "
                "into T-cells and B-cells, and T-cells splits into your 4 "
                "renamed quadrant leaves. Every node is the same gate object as "
                "in the tree view — just visualized differently."
            ),
            cyto_emotion="talking",
            target_widget_names=["PipelineCanvas"],
            next_step_id="c2_s30_orientation",
        ),
        VerificationStep(
            id="c2_s30_orientation",
            text=(
                "Change the 'Layout:' dropdown in the Pipeline ribbon from "
                "'Vertical' to 'Horizontal' and see the whole tree unfold sideways."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["PipelineOrientationCombo"],
            validator=PipelineOrientationValidator("horizontal"),
            on_success_step_id="c2_s31_delete_intro",
        ),
        InfoStep(
            id="c2_s31_delete_intro",
            text=(
                "Cleaning up a node 🗑️\n\n"
                "Suppose 'DN' (Double Negative) T-cells aren't useful for this "
                "analysis. You can delete any single node right here on the "
                "canvas: click it to select it, then press Delete or Backspace.\n\n"
                "This is the same underlying delete action as removing a gate "
                "from the tree panel — it's just a different way in."
            ),
            cyto_emotion="talking",
            target_widget_names=["PipelineCanvas"],
            next_step_id="c2_s32_delete_dn",
        ),
        VerificationStep(
            id="c2_s32_delete_dn",
            text="Click the 'DN' node on the canvas, then press Delete or Backspace.",
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["PipelineCanvas"],
            validator=GateAbsentValidator("dn"),
            on_success_step_id="c2_s33_pipeline_done",
        ),
        InfoStep(
            id="c2_s33_pipeline_done",
            text=(
                "Nicely done! 🌿\n\n"
                "You've navigated, re-oriented, and edited the Pipeline. There "
                "are also '+ AND / + OR / + NOT' buttons here for boolean gate "
                "combinations — we'll put those to real use in Course 3, when we "
                "validate manual gates against computed clusters."
            ),
            cyto_emotion="happy",
            next_step_id="c2_s34_spectral_switch",
        ),
        # ── Spectral & compensation theory ───────────────────────────────────────
        InteractionStep(
            id="c2_s34_spectral_switch",
            text="Click the 'Spectral' tab at the top.",
            cyto_emotion="pointing",
            target_widget_name="MainTabBar",
            target_widget_names=["MainTabBar"],
            event_trigger="currentChanged",
            next_step_id="c2_s35_verify_spectral_tab",
        ),
        VerificationStep(
            id="c2_s35_verify_spectral_tab",
            text="Checking tab...",
            cyto_emotion="scanning",
            hide_next_button=True,
            allow_interaction=False,
            validator=TabActiveValidator(5),
            on_success_step_id="c2_s36_spectral_intro",
            on_fail_step_id="c2_s35b_wrong_tab",
        ),
        InteractionStep(
            id="c2_s35b_wrong_tab",
            text="Oops! Click the 'Spectral' tab to proceed.",
            cyto_emotion="surprised",
            target_widget_name="MainTabBar",
            target_widget_names=["MainTabBar"],
            event_trigger="currentChanged",
            next_step_id="c2_s35_verify_spectral_tab",
        ),
        InfoStep(
            id="c2_s36_spectral_intro",
            text=(
                "The Spectral Viewer 🌈\n\n"
                "This shows the real light signatures of your fluorophores: "
                "AB (Absorbance), EX (Excitation), and EM (Emission) curves. "
                "Overlap between two dyes' EM curves is exactly why spillover "
                "happens — and why we compensate."
            ),
            cyto_emotion="talking",
            next_step_id="c2_s37_load_all_six",
        ),
        VerificationStep(
            id="c2_s37_load_all_six",
            text=(
                "In the 'Available Channels' list on the left, double-click all "
                "6 of your panel's markers (CD45, CD3, CD4, CD8, B220, PI) one by "
                "one to plot every fluorophore's emission curve at once."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["SpectralSourceList"],
            validator=SpectralFluorsLoadedValidator(min_count=6),
            on_success_step_id="c2_s38_overlap_theory",
        ),
        InfoStep(
            id="c2_s38_overlap_theory",
            text=(
                "Reading the Overlap 🔬\n\n"
                "Hover between two curves to see an 'Overlap integral %' — how "
                "much their emission spectra share. You'll find several "
                "overlapping pairs in this 6-dye panel. Not all of them matter "
                "equally!\n\n"
                "CD3 (Pacific Blue) and B220 (FITC) may show some spectral "
                "overlap, but it's harmless in practice: a cell is essentially "
                "never both a T-cell AND a B-cell, so even uncompensated "
                "spillover between those two channels can't create a "
                "biologically confusing double-positive population."
            ),
            cyto_emotion="thinking",
            next_step_id="c2_s39_overlap_theory2",
        ),
        InfoStep(
            id="c2_s39_overlap_theory2",
            text=(
                "Now compare CD4 (PE) and CD8 (APC-Cy7) — their overlap "
                "genuinely matters. Unlike CD3/B220, thymocytes really can "
                "co-express BOTH CD4 and CD8 (that's the Double Positive "
                "population you just gated!).\n\n"
                "So overlap between markers that CAN legitimately co-occur on "
                "one cell needs careful compensation, while overlap between "
                "markers on mutually-exclusive lineages usually doesn't. That's "
                "the real lesson: spillover risk depends on biology, not just "
                "spectral distance.\n\n"
                "Now let's see the actual math that fixes it."
            ),
            cyto_emotion="talking",
            next_step_id="c2_s40_learning_switch",
        ),
        InfoStep(
            id="c2_s40_learning_switch",
            text="Click the 'Learning Compensation' sub-tab inside this viewer.",
            cyto_emotion="pointing",
            allow_interaction=True,
            target_widget_names=["SpectralTabs"],
            next_step_id="c2_s41_slideshow",
        ),
        VerificationStep(
            id="c2_s41_slideshow",
            text=(
                "The Compensation Masterclass\n\n"
                "Work your way through the interactive slideshow. It's a "
                "step-by-step journey through spillover, single-stain controls, "
                "the spillover matrix, and matrix inversion.\n\n"
                "I'll be waiting here until you reach the final slide!"
            ),
            validator=LearningCompensationCompleteValidator(),
            allow_interaction=True,
            cyto_emotion="thinking",
            on_success_step_id="c2_s42_graduation",
        ),
        InfoStep(
            id="c2_s42_graduation",
            text=(
                "Incredible job! 🎉\n\n"
                "You've gated T-cells and B-cells with two different techniques, "
                "split T-cells by CD4/CD8, mastered the Pipeline view, and "
                "understand exactly why and when spillover matters.\n\n"
                "Your hypothesis: Sample B is the Thymus. Course 3 will prove it "
                "— and identify Spleen and Bone Marrow — with real statistics.\n\n"
                "Course 2 is complete — you're officially an Immunophenotyper! 🏆"
            ),
            cyto_emotion="cheering",
            cyto_animation="cheering",
        ),
    ],
)
