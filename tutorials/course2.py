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
    BranchingStep,  # noqa: F401
    Course,
    ForcedInteractionStep,  # noqa: F401
    InfoStep,
    InteractionStep,
    SubTask,  # noqa: F401
    VerificationStep,
)

from .validators import (
    ExactSampleOpenValidator,
    GateExistsValidator,
    Course1StateValidator,
    LearningCompensationCompleteValidator,
)

# ==============================================================================
# Course 2 — Advanced Gating & Lineage Identification
# ==============================================================================

course_2_gating = Course(
    id="flow_course_2_gating",
    title="Immunophenotyping & Spectral Analysis",
    description=(
        "Identify T-Cells and B-Cells using Histograms and Pseudocolor plots, "
        "explore the Pipeline view, and master Spectral Compensation."
    ),
    estimated_minutes=35,
    badge_reward="Immunophenotyper",
    badge_icon="🧬",
    prerequisite_course_ids=["flow_course_1_fundamentals"],
    steps=[
        VerificationStep(
            id="c2_s0_verify",
            validator=Course1StateValidator(),
            text=(
                "Checking your workspace...\n\n"
                "Making sure all 10 samples are loaded, roles are assigned, and the "
                "base gates (Cells -> Live -> Leukocytes) exist on Sample A."
            ),
            allow_interaction=False,
            cyto_emotion="thinking",
            next_step_id="c2_s1_intro",
        ),
        InfoStep(
            id="c2_s1_intro",
            text=(
                "Welcome to Course 2! 🎯\n\n"
                "We have clean, compensated data with our base gate "
                "hierarchy in place. Time to identify immune cell "
                "lineages using our FMO controls.\n\n"
                "We're going to use Histograms and Pseudocolor plots to precisely gate "
                "T-cells (CD3+) and B-cells (B220+)."
            ),
            cyto_emotion="talking",
            next_step_id="c2_s1b_open_sample",
        ),
        VerificationStep(
            id="c2_s1b_open_sample",
            text=(
                "First, we need a sample open to gate on.\n\n"
                "Double-click 'Sample A' in the Data hierarchy to open it in a Graph Window."
            ),
            validator=ExactSampleOpenValidator("sample a"),
            allow_interaction=True,
            cyto_emotion="pointing",
            target_widget_names=["SampleList"],
            on_success_step_id="c2_s2_gate_cd3_prep",
        ),
        InteractionStep(
            id="c2_s2_gate_cd3_prep",
            text=(
                "Step 1: Switch to Histogram mode\n\n"
                "To gate our first population, we'll use a 1D Histogram. "
                "Use the Display Mode dropdown (above the plot) and set it to 'Histogram'."
            ),
            target_widget_name="DisplayModeCombo",
            target_widget_names=["DisplayModeCombo"],
            event_trigger="activated",
            cyto_emotion="pointing",
            next_step_id="c2_s2_gate_cd3",
        ),
        VerificationStep(
            id="c2_s2_gate_cd3",
            text=(
                "Step 2: Gate CD3+ T-cells\n\n"
                "1. Make sure you are inside the 'Leukocytes' population on Sample A.\n"
                "2. Change your X-axis to the Pacific Blue-A channel (CD3).\n"
                "3. Look at the FMO PE overlay subplot below to see the true negative background.\n"
                "4. Draw a Range gate (using the tool ribbon) starting right where the FMO ends, capturing the positive peak.\n\n"
                "Name your new gate 'T-cells' or 'T-cells (CD3+)'."
            ),
            validator=GateExistsValidator("t-cells"),
            allow_interaction=True,
            cyto_emotion="thinking",
            target_widget_names=["Tool_range", "AxisSelectorX", "AxisSelectorFMO"],
            on_success_step_id="c2_s3_gate_b220_prep",
        ),
        InteractionStep(
            id="c2_s3_gate_b220_prep",
            text=(
                "Step 3: Switch back to Pseudocolor\n\n"
                "Great! Now return to the 'Leukocytes' population in the Hierarchy panel "
                "so we can look for B-cells.\n\n"
                "Change the Display Mode dropdown back to 'Pseudocolor'."
            ),
            target_widget_name="DisplayModeCombo",
            target_widget_names=["DisplayModeCombo"],
            event_trigger="activated",
            cyto_emotion="pointing",
            next_step_id="c2_s3_gate_b220",
        ),
        VerificationStep(
            id="c2_s3_gate_b220",
            text=(
                "Step 4: Gate B-cells (B220+)\n\n"
                "1. Set your X-axis to e450 (B220) and your Y-axis to PE (CD3).\n"
                "2. You should see distinct populations. B-cells are B220 positive but CD3 negative.\n"
                "3. Use the Rectangle or Polygon tool to gate the B220+ CD3- population in the bottom right.\n\n"
                "Name this gate 'B-cells'."
            ),
            validator=GateExistsValidator("b-cells"),
            allow_interaction=True,
            cyto_emotion="thinking",
            target_widget_names=["Tool_rectangle", "Tool_polygon"],
            on_success_step_id="c2_s4_pipeline_intro",
        ),
        InfoStep(
            id="c2_s4_pipeline_intro",
            text=(
                "Now that we have T-cells and B-cells, let's visualize our strategy.\n\n"
                "Click on the 'Pipeline' tab at the top of the window."
            ),
            cyto_emotion="happy",
            allow_interaction=True,
            target_widget_names=["MainTabBar"],
            next_step_id="c2_s5_pipeline_orient",
        ),
        InteractionStep(
            id="c2_s5_pipeline_orient",
            text=(
                "Step 5: Pipeline Orientation\n\n"
                "The Pipeline view shows your gating hierarchy as a flowchart.\n"
                "Change the Layout dropdown in the Pipeline ribbon from 'Vertical' to 'Horizontal'."
            ),
            target_widget_name="PipelineOrientationCombo",
            event_trigger="currentTextChanged",
            cyto_emotion="pointing",
            next_step_id="c2_s6_pipeline_info",
        ),
        InfoStep(
            id="c2_s6_pipeline_info",
            text=(
                "Notice how the Leukocyte node gracefully splits into two distinct branches: "
                "T-cells and B-cells! 🌿\n\n"
                "The pipeline view is perfect for visualizing complex strategies. "
                "In Course 3, we'll return here to use the Logic Nodes (AND/OR/NOT) "
                "to perform boolean gating."
            ),
            cyto_emotion="talking",
            next_step_id="c2_s7_spectral_intro",
        ),
        InfoStep(
            id="c2_s7_spectral_intro",
            text=(
                "Let's move on to the physics of flow cytometry.\n\n"
                "Click on the 'Spectral' tab at the top."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            target_widget_names=["MainTabBar"],
            next_step_id="c2_s8_spectral_info",
        ),
        InfoStep(
            id="c2_s8_spectral_info",
            text=(
                "The Spectral Viewer! 🌈\n\n"
                "Here you can see the actual light signatures of your fluorophores. "
                "Notice the three toggle buttons: AB (Absorbance), EX (Excitation), and EM (Emission).\n\n"
                "Overlap in these EM curves is exactly why we need 'Compensation'!"
            ),
            cyto_emotion="talking",
            next_step_id="c2_s9_learning_switch",
        ),
        InfoStep(
            id="c2_s9_learning_switch",
            text=(
                "Let's dive deep into Compensation.\n\n"
                "Click on the 'Learning Compensation' sub-tab inside this viewer."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            target_widget_names=["SpectralTabs"],
            next_step_id="c2_s10_learning_slideshow",
        ),
        VerificationStep(
            id="c2_s10_learning_slideshow",
            text=(
                "Step 6: The Compensation Masterclass\n\n"
                "Work your way through the interactive slideshow in the Learning Compensation tab. "
                "It's a step-by-step interactive journey that will teach you exactly why "
                "spillover happens and how the math corrects it.\n\n"
                "I'll be waiting here until you reach the final slide!"
            ),
            validator=LearningCompensationCompleteValidator(),
            allow_interaction=True,
            cyto_emotion="thinking",
            on_success_step_id="c2_s11_graduation",
        ),
        InfoStep(
            id="c2_s11_graduation",
            text=(
                "Incredible job! 🎉\n\n"
                "You now understand lineage gating, pipeline visualization, and "
                "the fundamental principles of spectral compensation.\n\n"
                "Course 2 is complete — you're officially an Immunophenotyper! 🏆"
            ),
            cyto_emotion="cheering",
            cyto_animation="cheering",
        ),
    ],
)
