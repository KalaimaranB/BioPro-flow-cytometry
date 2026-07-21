"""BioPro Flow Cytometry — Academy Courses.

Step conventions:
  InfoStep           — teaches a concept; user clicks Next → to continue.
  InteractionStep    — user must click/interact with a named widget to auto-advance.
  VerificationStep   — auto-polls a validator every ~2 s and advances automatically.
                       Set allow_interaction=True only if the user also needs to freely
                       interact with the UI before clicking the manual 'Check ✓' button.

Spotlight convention:
  target_widget_name  — single objectName for InteractionStep highlight.
  target_widget_names — list of objectNames for multi-target InfoStep spotlights.
"""

from biopro.core.models.tutorial_models import (
    ActionStep,
    BranchingStep,  # noqa: F401
    Course,
    ForcedInteractionStep,  # noqa: F401
    InfoStep,
    InteractionStep,
    SubTask,  # noqa: F401
    VerificationStep,
)

from .validators import (
    AxisChannelValidator,
    AxisOutlierValidator,
    CompensationAppliedValidator,
    ExactSampleOpenValidator,
    FlowImportValidator,
    FmoRoleValidator,
    GateExistsValidator,
    GateShapeValidator,
    LeukocyteGateExistsValidator,
    LiveGateExistsValidator,
    RoleAssignmentValidator,
    SampleOpenValidator,
    SingleStainRoleValidator,
    SpecificSampleOpenValidator,
    TabActiveValidator,
    UnstainedRoleValidator,
    WorkflowSavedValidator,
)

# ==============================================================================
# Course 1 — Flow Cytometry Fundamentals
# Three phases: Setup → Compensation → Gating
# ==============================================================================

course_1_fundamentals = Course(
    id="flow_course_1_fundamentals",
    title="Flow Cytometry Fundamentals",
    description=(
        "Your samples just arrived. We'll set up the experiment, "
        "clean the data with compensation, and gate our cell populations."
    ),
    estimated_minutes=50,
    badge_reward="Flow Fundamentalist",
    badge_icon="🔬",
    prerequisite_course_ids=[],
    steps=[
        # ── Intro ────────────────────────────────────────────────────────────
        InfoStep(
            id="c1_s1_intro",
            text=(
                "Welcome to BioPro Flow Cytometry! 🧬\n\n"
                "Today's mystery: 3 unknown samples — one is Spleen, "
                "one is Thymus, and one is Bone Marrow. By the end of "
                "this trio of courses you'll know exactly which is which.\n\n"
                "Let's start by loading our files. \n \n"
            ),
            cyto_emotion="happy",
            cyto_animation="cheering",
            next_step_id="c1_s2_import",
        ),
        # ── Phase 1 — Setup (Import & Roles) ─────────────────────────────────
        InteractionStep(
            id="c1_s2_import",
            text=(
                "Click the 'Add Samples' button (highlighted) to open "
                "the file picker. Select all 10 tutorial FCS files."
            ),
            target_widget_name="ImportDataButton",
            event_trigger="clicked",
            cyto_emotion="pointing",
            next_step_id="c1_s3_verify_import",
        ),
        VerificationStep(
            id="c1_s3_verify_import",
            text="Scanning files — checking all 10 samples loaded correctly…",
            cyto_emotion="scanning",
            cyto_animation="scanning",
            validator=FlowImportValidator(),
            on_success_step_id="c1_s4_roles_intro",
            on_fail_step_id="c1_s3_fail",
            max_retries=150,
            allow_interaction=True,
            target_widget_names=["ImportDataButton"],
        ),
        InfoStep(
            id="c1_s3_fail",
            text=(
                "Hmm — I couldn't find all 10 samples.\n\n"
                "Make sure you selected the Blank, PI, all 5 FMOs, "
                "and Samples A, B, C from the picker."
            ),
            cyto_emotion="sad",
            next_step_id="c1_s2_import",
            allow_interaction=True,
            target_widget_names=["ImportDataButton"],
        ),
        # Role assignment intro
        InfoStep(
            id="c1_s4_roles_intro",
            text=(
                "All 10 files are in! ✅\n\n"
                "BioPro needs to know the purpose of each file — "
                "we call this a 'Role'. The roles are:\n"
                "  • Blank → Unstained (no dye — baseline noise)\n"
                "  • PI → Single Stain (one dye for spillover calc)\n"
                "  • FMO_* → FMO Control (all dyes minus one)\n"
                "  • Samples A/B/C → Full Panel (experiment samples)\n\n"
                "We'll assign them one step at a time."
            ),
            cyto_emotion="talking",
            next_step_id="c1_s5_blank_role",
        ),
        # Blank → Unstained
        VerificationStep(
            id="c1_s5_blank_role",
            text=(
                "Step 1 of 4 — Blank sample.\n\n"
                "In the Sample List (left, highlighted), double click on 'Blank'. "
                "Then in the Properties Panel (right, highlighted), "
                "find the Role dropdown and set it to 'Unstained'.\n\n"
                "BioPro is watching and will advance automatically!"
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["SampleList", "PropertiesPanel"],
            validator=UnstainedRoleValidator(),
            on_success_step_id="c1_s7_pi_role",
        ),
        # PI → Single Stain
        VerificationStep(
            id="c1_s7_pi_role",
            text=(
                "Step 2 of 4 — PI file.\n\n"
                "PI (Propidium Iodide) is our viability dye — just one "
                "dye, which makes it the perfect single-stain control "
                "for its channel.\n\n"
                "Double click on the PI file in the Sample List and set its "
                "Role to 'Single Stain'. BioPro will detect it automatically."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["SampleList", "PropertiesPanel"],
            validator=SingleStainRoleValidator(),
            on_success_step_id="c1_s9_fmo_role",
        ),
        # FMOs → FMO Control
        VerificationStep(
            id="c1_s9_fmo_role",
            text=(
                "Step 3 of 4 — FMO controls.\n\n"
                "FMO = Fluorescence Minus One. Each FMO file has every "
                "dye *except* one, letting us see the maximum non-specific "
                "spread into that detector.\n\n"
                "Doing this one-by-one is tedious! Click '🏷️ Bulk Assign Roles' "
                "(highlighted in the ribbon).\n\n"
                "In the dialog, select all 5 FMO files, set them to the "
                "'FMO Control' role, and click Assign."
            ),
            cyto_emotion="talking",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["BulkAssignRoleButton"],
            validator=FmoRoleValidator(),
            on_success_step_id="c1_s10_set_all_roles",
        ),
        VerificationStep(
            id="c1_s10_set_all_roles",
            text=(
                "Step 4 of 4 — mystery samples.\n\n"
                "Use the '🏷️ Bulk Assign Roles' button again to select "
                "Samples A, B, and C and set their Role to 'Full Panel'.\n\n"
                "BioPro is scanning your progress... we'll advance when EVERY tube has a proper role."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["BulkAssignRoleButton"],
            validator=RoleAssignmentValidator(),
            on_success_step_id="c1_s11_role_summary",
        ),
        InfoStep(
            id="c1_s11_role_summary",
            text=(
                "Awesome! You've properly tagged every tube.\n\n"
                "Why do we do this? Because BioPro uses these tags intelligently:\n"
                "• Single Stains build the spillover math\n"
                "• Full Panels receive the math and get analyzed\n"
                "• FMOs guide your gating, but get excluded from final test statistics so they don't drag down your population averages."
            ),
            cyto_emotion="happy",
            next_step_id="c1_s12_comp_intro",
        ),
        # ── Phase 2 — Compensation ────────────────────────────────────────────
        InfoStep(
            id="c1_s12_comp_intro",
            text=(
                "Phase 2 — Compensation\n\n"
                "Fluorescent dyes spill light into adjacent detectors. "
                "Compensation removes this cross-talk mathematically.\n\n"
                "We'll verify if BioPro auto-loaded the embedded matrix."
            ),
            cyto_emotion="thinking",
            next_step_id="c1_s12b_check_auto_comp",
        ),
        VerificationStep(
            id="c1_s12b_check_auto_comp",
            text="Checking if BioPro auto-applied a compensation matrix on import…",
            cyto_emotion="scanning",
            validator=CompensationAppliedValidator(),
            on_success_step_id="c1_s12c_auto_applied_info",
            on_fail_step_id="c1_s12b_fail",
        ),
        InfoStep(
            id="c1_s12b_fail",
            text="Uh oh! No compensation matrix was found. We have a problem with the data file.",
            cyto_emotion="sad",
        ),
        InfoStep(
            id="c1_s12c_auto_applied_info",
            text=(
                "BioPro found a '$SPILL' keyword embedded in your Blank's "
                "FCS file header and auto-applied the compensation matrix "
                "to all samples when they were loaded! ✅\n\n"
                "However, it's important to know how to do this manually in case "
                "your files don't have embedded matrices. Let's practice extracting, "
                "viewing, and applying a matrix."
            ),
            cyto_emotion="happy",
            next_step_id="c1_s13_switch_comp_tab",
        ),
        InteractionStep(
            id="c1_s13_switch_comp_tab",
            text="First, click the 'Compensation' tab (highlighted) at the top.",
            cyto_emotion="pointing",
            target_widget_names=["MainTabBar"],
            target_widget_name="MainTabBar",
            event_trigger="currentChanged",
            next_step_id="c1_s13b_verify_comp_tab",
        ),
        VerificationStep(
            id="c1_s13b_verify_comp_tab",
            text="Checking tab...",
            cyto_emotion="scanning",
            hide_next_button=True,
            allow_interaction=False,
            validator=TabActiveValidator(1),
            on_success_step_id="c1_s14_extract_matrix",
            on_fail_step_id="c1_s13c_wrong_tab",
        ),
        InteractionStep(
            id="c1_s13c_wrong_tab",
            text="Oops! You clicked the wrong tab.\n\nPlease click the 'Compensation' tab to proceed.",
            cyto_emotion="surprised",
            target_widget_names=["MainTabBar"],
            target_widget_name="MainTabBar",
            event_trigger="currentChanged",
            next_step_id="c1_s13b_verify_comp_tab",
        ),
        InteractionStep(
            id="c1_s14_extract_matrix",
            text=(
                "Click '📄 Extract from FCS' (highlighted) in the ribbon.\n\n"
                "This reads the $SPILL keyword from the first file that has it."
            ),
            target_widget_name="ExtractFCSButton",
            event_trigger="clicked",
            cyto_emotion="pointing",
            next_step_id="c1_s15_view_matrix",
        ),
        InfoStep(
            id="c1_s15_view_matrix",
            text=(
                "A dialog has popped up showing the extracted matrix values!\n\n"
                "Take a moment to look at it. The diagonal is usually 1.0, and "
                "other numbers show how much light spills into adjacent detectors.\n\n"
                "Click 'OK' on the dialog to close it, then click Next here."
            ),
            cyto_emotion="talking",
            next_step_id="c1_s16_apply_matrix",
        ),
        InteractionStep(
            id="c1_s16_apply_matrix",
            text=(
                "Finally, click '✅ Apply to All' (highlighted).\n\n"
                "Since BioPro already auto-applied the matrix on import, this "
                "won't actually change anything right now, but this is exactly "
                "what you would do for uncompensated data.\n\n"
                "A popup will tell you that the samples were skipped because "
                "they are already compensated. You can close it."
            ),
            target_widget_name="ApplyAllButton",
            event_trigger="clicked",
            cyto_emotion="pointing",
            next_step_id="c1_s20_gating_intro",
        ),
        # ── Phase 3 — Gating ──────────────────────────────────────────────────
        InfoStep(
            id="c1_s20_gating_intro",
            text=(
                "Phase 3 — Gating 🎯\n\n"
                "Your data is clean and compensated. Gating means drawing "
                "regions on scatter plots to select specific cell populations.\n\n"
                "We'll build this hierarchy:\n"
                "  All Events → Cells → Live → Leukocytes\n\n"
                "First, switch to the 'Gating' tab."
            ),
            cyto_emotion="talking",
            next_step_id="c1_s21_switch_gating_tab",
        ),
        InteractionStep(
            id="c1_s21_switch_gating_tab",
            text=(
                "Click the 'Gating' tab (highlighted) at the top. "
                "This shows the polygon, rectangle, and range drawing tools."
            ),
            cyto_emotion="pointing",
            target_widget_names=["MainTabBar"],
            target_widget_name="MainTabBar",
            event_trigger="currentChanged",
            next_step_id="c1_s22_verify_gating_tab",
        ),
        VerificationStep(
            id="c1_s22_verify_gating_tab",
            text="Checking tab...",
            cyto_emotion="scanning",
            hide_next_button=True,
            allow_interaction=False,
            validator=TabActiveValidator(2),
            on_success_step_id="c1_s22b_open_sample",
            on_fail_step_id="c1_s22_fail",
        ),
        InteractionStep(
            id="c1_s22_fail",
            text=(
                "Oops! You clicked the wrong tab.\n\n"
                "Click 'Gating' in the tab bar at the top."
            ),
            cyto_emotion="sad",
            target_widget_names=["MainTabBar"],
            target_widget_name="MainTabBar",
            event_trigger="currentChanged",
            next_step_id="c1_s22_verify_gating_tab",
        ),
        # Open Blank Sample first — gate applies to whichever sample is open
        InteractionStep(
            id="c1_s22b_open_sample",
            text=(
                "Before drawing any gates, we start with the 'Blank' (Unstained) sample.\n\n"
                "In the Sample List, find the 'Blank' file and double-click it. "
                "This opens its scatter plot in the centre canvas.\n\n"
                "We use the unstained sample first because it has no dyes, making it "
                "the perfect baseline to find the physical cell population based purely on size and complexity."
            ),
            cyto_emotion="pointing",
            target_widget_names=["SampleList"],
            target_widget_name="SampleList",
            event_trigger="sample_double_clicked",
            next_step_id="c1_s22c_verify_sample_open",
        ),
        VerificationStep(
            id="c1_s22c_verify_sample_open",
            text="Checking opened sample...",
            cyto_emotion="scanning",
            hide_next_button=True,
            allow_interaction=False,
            validator=SampleOpenValidator(),
            on_success_step_id="c1_s23_cells_intro",
            on_fail_step_id="c1_s22b_fail",
        ),
        InteractionStep(
            id="c1_s22b_fail",
            text=(
                "Oops! You opened the wrong sample.\n\n"
                "Please double-click the 'Blank' sample to open it."
            ),
            cyto_emotion="surprised",
            target_widget_names=["SampleList"],
            target_widget_name="SampleList",
            event_trigger="sample_double_clicked",
            next_step_id="c1_s22c_verify_sample_open",
        ),
        # Cells gate
        InfoStep(
            id="c1_s23_cells_intro",
            text=(
                "Gate 1: Cells\n\n"
                "The current plot shows FSC-A (cell size) vs SSC-A "
                "(cell complexity). You'll see:\n"
                "  • 2 main clusters of cells\n"
                "  • A small debris cloud in the bottom-left corner\n"
                "  • A good chunk of splatter throughout the entire canvas\n\n"
                "We want to draw a gate that excludes the debris. "
                "This ensures all downstream analysis excludes junk events."
            ),
            cyto_emotion="talking",
            next_step_id="c1_s24_cells_gate",
        ),
        InteractionStep(
            id="c1_s24_cells_gate",
            text=(
                "Draw the gate:\n\n"
                "1. Click 'Polygon' in the Gating ribbon (highlighted above)\n"
                "2. Click each vertex around the oval cell cloud on the plot (highlighted)\n"
                "3. Double-click to close the polygon\n\n"
                "BioPro will evaluate your gate automatically once you finish drawing."
            ),
            cyto_emotion="pointing",
            target_widget_name="FlowCanvas",
            event_trigger="gate_created",
            target_widget_names=["Tool_polygon", "FlowCanvas"],
            guide_poly=[(8000, 38000), (248000, 34000), (248000, 500), (8000, 1000)],
            next_step_id="c1_s24_cells_gate_verify",
        ),
        VerificationStep(
            id="c1_s24_cells_gate_verify",
            text="BioPro is evaluating your gate...",
            cyto_emotion="scanning",
            allow_interaction=False,
            hide_next_button=True,
            target_widget_names=["FlowCanvas"],
            guide_poly=[(8000, 38000), (248000, 34000), (248000, 500), (8000, 1000)],
            validator=GateShapeValidator(
                target_bounds=(8000.0, 248000.0, 500.0, 38000.0),
                target_poly=[
                    (8000, 38000),
                    (248000, 34000),
                    (248000, 500),
                    (8000, 1000),
                ],
            ),
            on_success_step_id="c1_s24b_cells_hierarchy_intro",
            on_fail_step_id="c1_s24_cells_gate_fail",
        ),
        ActionStep(
            id="c1_s24_cells_gate_fail",
            text="Deleting poorly drawn gate...",
            action=lambda panel: panel._on_delete_selected_gate(),
            next_step_id="c1_s24_cells_gate_retry",
        ),
        InfoStep(
            id="c1_s24_cells_gate_retry",
            text=(
                "That gate didn't quite match the shape!\n\n"
                "I deleted it for you. Make sure you cover the main cluster of cells while excluding the debris at the bottom left.\n\n"
                "Try drawing it again."
            ),
            cyto_emotion="surprised",
            target_widget_names=["FlowCanvas"],
            guide_poly=[(8000, 38000), (248000, 34000), (248000, 500), (8000, 1000)],
            next_step_id="c1_s24_cells_gate",
        ),
        InfoStep(
            id="c1_s24b_cells_hierarchy_intro",
            text=(
                "Perfect shape! 🎯\n\n"
                "Notice that your new gate has appeared in the Gating Hierarchy panel on the left.\n\n"
                "This hierarchy tracks all populations. By default, the gates you apply to one sample will propagate to all other samples in the same group."
            ),
            cyto_emotion="happy",
            target_widget_names=["GatingHierarchySampleView"],
            next_step_id="c1_s24c_cells_rename",
        ),
        VerificationStep(
            id="c1_s24c_cells_rename",
            text=(
                "Let's name this population.\n\n"
                "Right-click the new gate in the Gating Hierarchy panel and rename it to 'Cells'.\n\n"
                "BioPro is scanning your progress automatically..."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["GatingHierarchySampleView"],
            validator=GateExistsValidator("Cells"),
            on_success_step_id="c1_s25_singlets_intro",
        ),
        InfoStep(
            id="c1_s25_singlets_intro",
            text=(
                "Great job! 🎯\n\n"
                "Typically, the next step is gating for 'Singlets' to remove clumps "
                "of cells (doublets). You'd do this by plotting FSC-A vs FSC-H and "
                "drawing a narrow diagonal gate down the center line.\n\n"
                "Doublets have a disproportionately larger Area than Height, so they "
                "appear as a separate population shifted to the right of the diagonal. "
                "You would filter them out by only keeping the events on the diagonal.\n\n"
                "Our dataset doesn't include the -H or -W parameters, so we won't "
                "gate for singlets today, but it's a crucial step in real experiments!"
            ),
            cyto_emotion="thinking",
            next_step_id="c1_s26_live_intro",
        ),
        # Live gate
        InfoStep(
            id="c1_s26_live_intro",
            text=(
                "Gate 2: Live\n\n"
                "Dead cells absorb PI dye and glow brightly (high signal). "
                "Live cells keep it out — they appear dim.\n\n"
                "We gate *inside* the Cells population to keep only "
                "live cells. This is called hierarchical gating."
            ),
            cyto_emotion="talking",
            next_step_id="c1_s27_open_pi",
        ),
        # ── Step 1: Open the PI single stain sample ─────────────────────────
        InteractionStep(
            id="c1_s27_open_pi",
            text=(
                "Time to gate live vs dead cells.\n\n"
                "Dead cells absorb PI dye and glow bright. Live cells keep "
                "it out and stay dim.\n\n"
                "First, double-click the 'Specimen_001_PI' Single Stain sample "
                "in the Sample List to open it. This sample has only the PI "
                "viability dye — perfect for clearly seeing dead vs live."
            ),
            cyto_emotion="pointing",
            target_widget_names=["SampleList"],
            target_widget_name="SampleList",
            event_trigger="sample_double_clicked",
            next_step_id="c1_s27_verify_pi",
        ),
        VerificationStep(
            id="c1_s27_verify_pi",
            text="Checking opened sample...",
            cyto_emotion="scanning",
            hide_next_button=True,
            allow_interaction=False,
            validator=SpecificSampleOpenValidator("SINGLE_STAIN"),
            on_success_step_id="c1_s27b_set_axis",
            on_fail_step_id="c1_s27_fail",
        ),
        InteractionStep(
            id="c1_s27_fail",
            text=(
                "Oops! You opened the wrong sample.\n\n"
                "Please double-click the 'Specimen_001_PI' sample to open it."
            ),
            cyto_emotion="surprised",
            target_widget_names=["SampleList"],
            target_widget_name="SampleList",
            event_trigger="sample_double_clicked",
            next_step_id="c1_s27_verify_pi",
        ),
        # ── Step 2: Change X axis to the PI channel ──────────────────────────
        VerificationStep(
            id="c1_s27b_set_axis",
            text=(
                "Now set the X axis to the PI channel.\n"
                "Click the 'X:' dropdown (highlighted) and select "
                "'PerCP-Cy5-5-A' — that is the PI detector channel.\n\n"
                "BioPro is scanning automatically..."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["AxisSelectorX"],
            validator=AxisChannelValidator("percp"),
            on_success_step_id="c1_s27c_biexp_explain",
        ),
        # ── Step 3: Explain biexponential and populations ───────────────────
        InfoStep(
            id="c1_s27c_biexp_explain",
            text=(
                "Nice! You can see two populations — a massive, dense cluster on the "
                "left (live cells) and a smaller, brighter cluster on the right (dead).\n\n"
                "Also, did you notice that BioPro opened the PI sample directly at the 'Cells' population? "
                "That's because BioPro preserves your gating context when switching samples!\n\n"
                "Notice how the X axis automatically switched to 'Biexponential'?\n\n"
                "Fluorescence channels like PI have a quirk: after compensation, "
                "some cells score *negative*. Linear and Log scales can't show negatives "
                "properly. BioPro intelligently detects that this is a fluorescence dye and automatically sets "
                "the scale to Biexponential to perfectly handle those negative values!"
            ),
            cyto_emotion="talking",
            next_step_id="c1_s27c2_biexp_t_explain",
        ),
        InfoStep(
            id="c1_s27c2_biexp_t_explain",
            text=(
                "Behind the Scenes: The 'Top' Bound\n\n"
                "Flow cytometers record brightness using digital bits. A standard 18-bit cytometer "
                "can measure up to 262,144 levels of brightness.\n\n"
                "BioPro automatically scanned this sample when you opened it, detected the instrument's "
                "maximum range, and set the very right edge of the plot (the Logicle 'T' parameter) "
                "to perfectly match that ceiling without squishing the data."
            ),
            cyto_emotion="talking",
            next_step_id="c1_s27c3_biexp_a_explain",
        ),
        InfoStep(
            id="c1_s27c3_biexp_a_explain",
            text=(
                "Behind the Scenes: The 'Negative Tail' 📉\n\n"
                "In flow cytometry, a 'decade' is just a factor of 10 on a log scale (like jumping from 10 to 100).\n\n"
                "BioPro also automatically scanned the data below zero. If it finds a long negative tail "
                "(which is very common after compensation), it dynamically adds extra 'negative decades' "
                "(the Logicle 'A' parameter) to stretch the left side of the axis just enough to show those cells beautifully."
            ),
            cyto_emotion="talking",
            next_step_id="c1_s27d_outlier_fix",
        ),
        # ── Step 4: Fix Outliers ────────────────────────────────────────────
        VerificationStep(
            id="c1_s27d_outlier_fix",
            text=(
                "However, look closely at the left edge of the dim population — "
                "it seems a bit cut off!\n\n"
                "By default, BioPro hides the extreme 0.1% of outliers to prevent "
                "single noise spikes from ruining the scale. Let's turn that off here "
                "to see the full tail.\n\n"
                "1. Click '⚙ Transforms' (highlighted)\n"
                "2. Change 'Outliers:' from '0.1% (Def)' to '0%'\n\n"
                "BioPro is scanning automatically..."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["TransformsButton", "OutlierCombo"],
            validator=AxisOutlierValidator(0.0),
            on_success_step_id="c1_s27d2_outlier_explain",
        ),
        InfoStep(
            id="c1_s27d2_outlier_explain",
            text=(
                "Behind the Scenes: 0.1% Outliers ✂️\n\n"
                "Flow cytometers often record random electronic noise, resulting in one or two 'cells' "
                "appearing way off the chart (e.g. at a brightness of 5 million).\n\n"
                "If BioPro included those few rogue events in the calculation, the entire plot would zoom "
                "out so far that your real cells would look like a single thin line. Dropping the extreme "
                "top and bottom 0.1% guarantees your default zoom is always a good starting point!"
            ),
            cyto_emotion="talking",
            next_step_id="c1_s27e_pseudocolor_settings",
        ),
        # ── Step 5: Explore pseudocolor settings ─────────────────────────────
        InfoStep(
            id="c1_s27e_pseudocolor_settings",
            text=(
                "Pseudocolor Settings 🎨\n\n"
                "The colourmap shows density — hot colours mean many cells, "
                "cool colours mean few.\n\n"
                "Click '⚙ Settings' (highlighted) and try changing the 'Population "
                "Detail' and 'Population Smoothing' sliders.\n"
                "Higher Detail = sharper boundaries; Higher Smoothing = softer look.\n\n"
                "Experiment, then close the dialog to continue."
            ),
            cyto_emotion="talking",
            allow_interaction=True,
            target_widget_names=["PseudocolorSettingsButton"],
            next_step_id="c1_s27f_draw_live_gate",
        ),
        # ── Step 6: Draw the vertical Range gate ────────────────────────────────
        VerificationStep(
            id="c1_s27f_draw_live_gate",
            text=(
                "Now draw the Live cell gate.\n\n"
                "The dark purple box shows the target region. Drag from the left edge of the "
                "box to the right edge to capture the live cells.\n\n"
                "1. Click the 'Range' tool (highlighted in the ribbon)\n"
                "2. Drag horizontally across the left cluster. Start from the far left edge (around -10³) and end just past the dense red center (around 5000).\n\n"
                "BioPro is scanning automatically..."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["Tool_range", "FlowCanvas"],
            guide_poly=[(0.03, 38000), (0.52, 38000), (0.52, 0), (0.03, 0)],
            validator=LiveGateExistsValidator(),
            on_success_step_id="c1_s27b_live_rename",
        ),
        VerificationStep(
            id="c1_s27b_live_rename",
            text=(
                "Let's name this population.\n\n"
                "Right-click the new gate in the Gating Hierarchy panel and rename it to 'Live Cells'.\n\n"
                "BioPro is scanning your progress automatically..."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["GatingHierarchySampleView"],
            validator=GateExistsValidator("Live Cells"),
            on_success_step_id="c1_s28_stats_intro",
        ),
        InfoStep(
            id="c1_s28_stats_intro",
            text=(
                "Understanding the Stats 📊\n\n"
                "Now that you've gated 'Live Cells', check the Property Panel:\n"
                "- Event Count: How many cells fall inside your gate.\n"
                "- % Parent: Percentage of the parent population (e.g. out of 'Cells').\n"
                "- % Total: Percentage of all recorded events in the tube.\n\n"
                "Also, glance at the Group Preview below \u2014 it shows this gate applied to "
                "every sample in your workspace instantly!"
            ),
            cyto_emotion="talking",
            target_widget_names=["PropertiesPanel"],
            next_step_id="c1_s29_leuko_intro",
        ),
        # Leukocytes gate
        InfoStep(
            id="c1_s29_leuko_intro",
            text=(
                "Gate 3: Leukocytes (CD45+)\n\n"
                "CD45 is expressed on ALL white blood cells — T cells, B cells, NK cells, "
                "monocytes — but NOT on red blood cells, platelets or debris.\n\n"
                "Gating CD45-bright cells isolates your immune population for everything that follows.\n\n"
                "Here's the plan:\n"
                "① Open the FMO APC control → see background noise floor\n"
                "② Switch to a full-panel sample → see the real CD45+ cluster\n"
                "③ Draw the gate just to the right of where the FMO noise ended"
            ),
            cyto_emotion="talking",
            next_step_id="c1_s30a_open_fmo",
        ),
        # ── Step 1: Open FMO to see background ───────────────────────────────
        InteractionStep(
            id="c1_s30a_open_fmo",
            text=(
                "Step ①: Open the FMO control.\n\n"
                "Double-click the 'FMO APC' sample in the Sample List to open it. "
                "This sample contains everything *except* the APC dye, so any signal "
                "in the APC channel here is pure background."
            ),
            cyto_emotion="pointing",
            target_widget_names=["SampleList"],
            target_widget_name="SampleList",
            event_trigger="sample_double_clicked",
            next_step_id="c1_s30a_verify_fmo",
        ),
        VerificationStep(
            id="c1_s30a_verify_fmo",
            text="Checking opened sample...",
            cyto_emotion="scanning",
            hide_next_button=True,
            allow_interaction=False,
            validator=ExactSampleOpenValidator("FMO APC"),
            on_success_step_id="c1_s30b_set_x",
            on_fail_step_id="c1_s30a_fail",
        ),
        InteractionStep(
            id="c1_s30a_fail",
            text=(
                "Oops! You opened the wrong sample.\n\n"
                "Please double-click the 'FMO APC' sample to open it."
            ),
            cyto_emotion="surprised",
            target_widget_names=["SampleList"],
            target_widget_name="SampleList",
            event_trigger="sample_double_clicked",
            next_step_id="c1_s30a_verify_fmo",
        ),
        VerificationStep(
            id="c1_s30b_set_x",
            text=(
                "Set X-axis to 'APC-A' (the CD45 channel).\n\n"
                "(The Y-axis is already Side Scatter by default, which is perfect for leukocyte gating).\n\n"
                "BioPro is scanning automatically..."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["AxisSelectorX"],
            validator=AxisChannelValidator("apc"),
            on_success_step_id="c1_s30d_outlier",
        ),
        InfoStep(
            id="c1_s30d_outlier",
            text=(
                "Check the outlier cutoff. ⚠️\n\n"
                "The default 0.1% outlier trim hides a thin sliver of cells at each edge "
                "of the APC-A axis. Byt setting it to 0, we can see the complete spread.\n\n"
                "1. Click '⚙ Transforms'\n"
                "2. Find the 'Outliers' dropdown and set it to 0%\n"
                "3. Close the dialog\n\n"
                "Once done, click Next to continue."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            target_widget_names=["TransformsButton"],
            next_step_id="c1_s30e_read_fmo",
        ),
        InfoStep(
            id="c1_s30e_read_fmo",
            text=(
                "Reading the FMO plot 🔍\n\n"
                "All events are bunched up near X=0 on the APC-A axis — there is NO CD45 "
                "antibody here, so this is pure spillover noise from all the other dyes.\n\n"
                "Your gate boundary will start just to the right of this cloud (~X=10²).\n\n"
                "You may also notice the SSC-A axis appears to have a lower cutoff. "
                "That's the biexponential transform compressing the near-zero region — "
                "it's a visual effect only. Compensation never touches FSC or SSC channels, "
                "so the scatter data is exactly as measured by the instrument.\n\n"
                "Take a good look, then click Next."
            ),
            cyto_emotion="talking",
            allow_interaction=True,
            target_widget_names=["FlowCanvas"],
            next_step_id="c1_s30f_open_sample",
        ),
        # ── Step 2: Switch to full-panel sample ────────────────────────────────
        InteractionStep(
            id="c1_s30f_open_sample",
            text=(
                "Step ②: Open a full-panel sample.\n\n"
                "Double-click 'Sample B' in the sample list.\n\n"
                "Unlike the FMO, Sample B has ALL antibodies including CD45-APC. "
                "You'll now see TWO populations on the X-axis:\n"
                "• Left cluster = non-leukocytes (debris, RBCs)\n"
                "• Right cluster = CD45+ leukocytes ✅"
            ),
            cyto_emotion="pointing",
            target_widget_names=["SampleList"],
            target_widget_name="SampleList",
            event_trigger="sample_double_clicked",
            next_step_id="c1_s30f_verify_sample",
        ),
        VerificationStep(
            id="c1_s30f_verify_sample",
            text="Checking opened sample...",
            cyto_emotion="scanning",
            hide_next_button=True,
            allow_interaction=False,
            validator=ExactSampleOpenValidator("Sample B"),
            on_success_step_id="c1_s30f2_set_x_sample_a",
            on_fail_step_id="c1_s30f_fail",
        ),
        InteractionStep(
            id="c1_s30f_fail",
            text=(
                "Oops! You opened the wrong sample.\n\n"
                "Please double-click 'Sample B' to open it."
            ),
            cyto_emotion="surprised",
            target_widget_names=["SampleList"],
            target_widget_name="SampleList",
            event_trigger="sample_double_clicked",
            next_step_id="c1_s30f_verify_sample",
        ),
        InfoStep(
            id="c1_s30f2_set_x_sample_a",
            text=(
                "BioPro is smart! When you opened Sample B, it preserved your context and opened directly into the 'Live' gate (highlighted in white in the hierarchy view).\n\n"
                "It also remembered that you were looking at APC-A (from the FMO) and perfectly locked the zoom and axis scaling!\n\n"
                "Now, we are ready to draw a Polygon gate around the CD45+ leukocytes on the right."
            ),
            cyto_emotion="talking",
            allow_interaction=True,
            target_widget_names=["AxisSelectorX", "GatingHierarchySampleView"],
            next_step_id="c1_s30f3_persistence_explain",
        ),
        InfoStep(
            id="c1_s30f3_persistence_explain",
            text=(
                "Behind the Scenes: The 'No-Jump' Rule\n\n"
                "In BioPro, the auto-zoom calculation only happens *once* the very first time you select a channel. "
                "From that point on, the view is completely locked for that channel across all samples in the group.\n\n"
                "This guarantees that as you draw deeper gates and switch between controls and full samples, the plot "
                "won't aggressively jump around or zoom in. You will always maintain your bearings!"
            ),
            cyto_emotion="talking",
            next_step_id="c1_s30g_preview_intro",
        ),
        # ── Step 3: Preview intro + Draw gate on full-panel ────────────────────
        InfoStep(
            id="c1_s30g_preview_intro",
            text=(
                "Use the Group Preview to guide your gate! 👥\n\n"
                "Look at the bottom-right panel — it shows mini-plots of every other sample "
                "on the same axes. Scroll down inside it to find a few of the Sample A/B/C "
                "thumbnails.\n\n"
                "As you draw the gate in the next step, those thumbnails update live "
                "so you can instantly see how many leukocytes you're capturing across "
                "all your full-panel samples at once."
            ),
            cyto_emotion="talking",
            allow_interaction=True,
            target_widget_names=["GroupPreviewPanel"],
            next_step_id="c1_s30h_draw_gate",
        ),
        VerificationStep(
            id="c1_s30h_draw_gate",
            text=(
                "Step ③: Draw the Leukocyte gate.\n\n"
                "1. Select the 'Rect' tool.\n"
                "2. The dark purple box marks the CD45+ region. Start your rectangle "
                "at roughly X=10² (where the FMO noise cloud ended) and drag "
                "all the way to the right edge, covering the full height of the SSC-A axis.\n\n"
                "Keep an eye on the Group Preview thumbnails as you drag — "
                "you'll see the gate update live across all samples!\n\n"
                "BioPro is scanning automatically..."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["Tool_rectangle", "FlowCanvas"],
            guide_poly=[(0.42, 500), (0.42, 80000), (0.95, 80000), (0.95, 500)],
            validator=LeukocyteGateExistsValidator(),
            on_success_step_id="c1_s30i_leuko_rename",
        ),
        VerificationStep(
            id="c1_s30i_leuko_rename",
            text=(
                "Name this population.\n\n"
                "Right-click the new gate in the Gating Hierarchy panel and rename it "
                "to 'Leukocytes'.\n\n"
                "BioPro is scanning your progress automatically..."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["GatingHierarchySampleView"],
            validator=GateExistsValidator("Leukocytes"),
            on_success_step_id="c1_s32_auto_propagation",
        ),
        # Auto-propagation
        InfoStep(
            id="c1_s32_auto_propagation",
            text=(
                "Brilliant! Three-gate hierarchy built on our controls. 🎉\n\n"
                "Because Auto-Propagation is enabled, BioPro has automatically "
                "copied all three gates — Cells, Live, and Leukocytes — "
                "to the Full Panel samples in the background!\n\n"
                "The toggle to the right indicates Auto-propagation is enabled."
                "If you're curious you can click the grid next to the toggle to view some stats as well! \n\n"
                "You can verify this by looking at the Gate Hierarchy panel."
            ),
            cyto_emotion="happy",
            target_widget_names=["GatingHierarchySampleView"],
            next_step_id="c1_s33b_save_interaction",
        ),
        VerificationStep(
            id="c1_s33b_save_interaction",
            text=(
                "Phase 4 — Saving your progress 💾\n\n"
                "Course 2 requires the foundation we just built. We need to save "
                "this workspace so we can load it later.\n\n"
                "Click the 'Save New Workflow' button (highlighted) at the top right.\n\n"
                "Give it a name like 'Course 1 Complete' and click Save."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["SaveNewWorkflowButton"],
            validator=WorkflowSavedValidator(),
            on_success_step_id="c1_s33b2_save_explain",
        ),
        InfoStep(
            id="c1_s33b2_save_explain",
            text=(
                "Behind the Scenes: JSON Serialization 💾\n\n"
                "When you clicked save, BioPro wrote all of those manual and auto-calculated zoom levels "
                "directly into a project JSON file. The axis bounds are saved inside every **Group** so "
                "each experimental group retains its unique visual states.\n\n"
                "Even cooler: BioPro saves a 'creation_view' inside every **Gate** you draw! If you open "
                "this project in 5 years and click the 'Live' gate, it will instantly reconstruct the exact "
                "zoom, axes, and logicle parameters you were looking at the moment you drew the polygon!"
            ),
            cyto_emotion="talking",
            next_step_id="c1_s34_graduation",
        ),
        InfoStep(
            id="c1_s34_graduation",
            text=(
                "All done! You've successfully imported, cleaned, and "
                "identified the core immune population in our samples. 🚀\n\n"
                "Your workspace is saved. In Course 2, we will use this exact "
                "setup to finally solve the mystery of what these three "
                "samples are.\n\n"
                "Click Next to collect your badge!"
            ),
            cyto_emotion="cheering",
            cyto_animation="cheering",
        ),
    ],
)
