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
    WorkflowSavedValidator,
)

# ==============================================================================
# Course 3 — Population Analysis & Pipeline
# ==============================================================================

course_3_analysis = Course(
    id="flow_course_3_analysis",
    title="Population Analysis & Pipeline",
    description=(
        "Finish manual gating with a Quadrant Gate, analyze statistics, and let the data speak for itself using UMAP and HDBSCAN."
    ),
    estimated_minutes=45,
    badge_reward="Population Analyst",
    badge_icon="🧠",
    prerequisite_course_ids=["flow_course_2_gating"],
    steps=[
        InfoStep(
            id="c3_s1_intro",
            text=(
                "Welcome to Course 3! 🧠\n\n"
                "We'll start by finishing our manual gating with a Quadrant Gate to find Double Positive (DP) T-cells, "
                "then analyze statistics and explore automated analysis like UMAP."
            ),
            cyto_emotion="happy",
            next_step_id="c3_s2_gate_cd4_cd8",
        ),
        InteractionStep(
            id="c3_s2_gate_cd4_cd8",
            text=(
                "Step 1: Gate CD4 and CD8 — The Double Positive Question\n\n"
                "Plot CD4 (FITC, x-axis) vs. CD8 (APC-Cy7, y-axis) inside the T-cells gate.\n\n"
                "Subplot: Use FMO FITC to anchor the vertical (CD4) boundary. Use FMO APC-Cy7 to anchor the horizontal (CD8) boundary.\n\n"
                "Draw a Quadrant gate. Name the quadrants: CD4+ only, CD8+ only, DP (Double Positive), DN (Double Negative).\n\n"
                "Watch the DP quadrant number — it's going to be very different across the three tissues!"
            ),
            target_widget_name="Tool_quadrant",
            event_trigger="clicked",
            cyto_emotion="thinking",
            next_step_id="c3_s3_propagate",
        ),
        InteractionStep(
            id="c3_s3_propagate",
            text=(
                "Step 2: Propagate All Lineage Gates\n\n"
                "Copy all your new lineage gates to Samples B and C.\n\n"
                "This ensures all three mystery samples are gated with identical boundaries for a fair comparison."
            ),
            target_widget_name="CopyGatesButton",
            event_trigger="clicked",
            cyto_emotion="pointing",
            next_step_id="c3_s4_stats_table",
        ),
        InteractionStep(
            id="c3_s4_stats_table",
            text=(
                "Step 3: Your First Stats Table\n\n"
                "Navigate to the Statistics tab.\n\n"
                "Here you can see Count, %Parent, %Total, Mean, MFI, and CV.\n"
                "Focus on the %Total of DP T-cells across Samples A, B, and C."
            ),
            target_widget_name="MainTabBar",
            event_trigger="clicked",
            cyto_emotion="talking",
            next_step_id="c3_s5_stats_charts",
        ),
        InteractionStep(
            id="c3_s5_stats_charts",
            text=(
                "Step 4: Building Comparison Charts\n\n"
                "Navigate to Statistics Explorer → chart mode.\n\n"
                "Violin Plot: Create a violin plot comparing DP T-cell %Total across all three samples. "
                "The outlier sample will have a dramatically higher and tighter distribution — almost all its T-cells are DP.\n\n"
                "Radar Plot: Switch to the radar chart mode. Add all four populations: DP T-cells, CD4+ T-cells, CD8+ T-cells, B-cells. "
                "Each sample gets its own colored polygon on the radar."
            ),
            target_widget_name="StatsChartMode",
            event_trigger="clicked",
            cyto_emotion="happy",
            next_step_id="c3_s6_solve_mystery_1",
        ),
        BranchingStep(
            id="c3_s6_solve_mystery_1",
            text=(
                "Solving Part of the Mystery:\n\n"
                "Which sample has the highest proportion of CD4+CD8+ Double Positive T-cells (The Thymus)?"
            ),
            options={
                "Sample A": "c3_s6_wrong",
                "Sample B": "c3_s7_pipeline",
                "Sample C": "c3_s6_wrong",
            },
        ),
        InfoStep(
            id="c3_s6_wrong",
            text=(
                "Not quite! Look for the sample with a dramatically higher proportion of Double Positive T-cells."
            ),
            cyto_emotion="sad",
            next_step_id="c3_s6_solve_mystery_1",
        ),
        InfoStep(
            id="c3_s7_pipeline",
            text=(
                "Correct! Sample B is the Thymus! 🎉\n\n"
                "Now let's switch to the Pipeline tab as a visual map of the gating hierarchy. "
                "Nodes, connections, and mini-plots allow you to build Logic Gates (AND, OR, NOT)."
            ),
            cyto_emotion="pointing",
            next_step_id="c3_s8_boolean",
        ),
        InteractionStep(
            id="c3_s8_boolean",
            text=(
                "Building a Boolean Gate — 'True T-cells'\n\n"
                "Scenario: You want cells that are CD3+ AND (CD4+ OR CD8+) — a more precise T-cell definition.\n\n"
                "Click the + AND button to create an AND node combining CD3+ with the CD4+/CD8+ gates."
            ),
            target_widget_name="AddAndGateButton",
            event_trigger="clicked",
            cyto_emotion="thinking",
            next_step_id="c3_s9_umap_intro",
        ),
        InfoStep(
            id="c3_s9_umap_intro",
            text=(
                "Understanding UMAP — A Deep Dive\n\n"
                "You have 6 fluorescence channels, meaning each cell is a point in 6D space. UMAP flattens this 6D manifold into a 2D map.\n\n"
                "The axes have no biological meaning; what matters is the relative position of the clusters. Each 'island' corresponds to a biologically coherent population."
            ),
            cyto_emotion="thinking",
            next_step_id="c3_s10_umap_run",
        ),
        InteractionStep(
            id="c3_s10_umap_run",
            text=(
                "Configure and Run UMAP\n\n"
                "Navigate to the Population Analysis tab.\n"
                "Uncheck FSC-A, SSC-A, and Live Stain. Keep CD45, CD3, CD4, CD8, B220.\n"
                "Set n_neighbors = 15, min_dist = 0.10. Select the 'Leukocytes' gate.\n"
                "Click 'Run Analysis'."
            ),
            target_widget_name="RunAnalysisButton",
            event_trigger="clicked",
            cyto_emotion="pointing",
            next_step_id="c3_s11_umap_read",
        ),
        InfoStep(
            id="c3_s11_umap_read",
            text=(
                "Reading the UMAP\n\n"
                "Look at the 'islands' on the UMAP plot. Color the UMAP by CD3 expression to watch the T-cell island light up, then by B220 for B-cells.\n\n"
                "The relative sizes of these islands differ across tissues — this is the key to solving the final mystery."
            ),
            cyto_emotion="happy",
            next_step_id="c3_s12_hdbscan",
        ),
        InteractionStep(
            id="c3_s12_hdbscan",
            text=(
                "HDBSCAN Auto-Clustering\n\n"
                "Check 'Run HDBSCAN Auto-Clustering' and click 'Run Analysis'.\n\n"
                "HDBSCAN runs on the original 6D data (not the 2D UMAP) and groups cells without human input."
            ),
            target_widget_name="RunAnalysisButton",
            event_trigger="clicked",
            cyto_emotion="pointing",
            next_step_id="c3_s13_annotate",
        ),
        InteractionStep(
            id="c3_s13_annotate",
            text=(
                "Annotate the Clusters\n\n"
                "Navigate to the Population Statistics tab. Use the Marker Expression Heatmap to identify each cluster (e.g., CD4+, CD8+, B220+).\n\n"
                "Type names into the 'Population Name' field next to each Cluster ID."
            ),
            target_widget_name="ClusterResultsTabs",
            event_trigger="currentChanged",
            cyto_emotion="thinking",
            next_step_id="c3_s14_validate",
        ),
        InteractionStep(
            id="c3_s14_validate",
            text=(
                "Manual Gates vs. UMAP Clusters — The Validation\n\n"
                "Navigate back to the Pipeline tab.\n"
                "Create an AND gate combining your manual 'B-cells (B220+)' gate with the HDBSCAN 'B-cell Cluster' gate.\n\n"
                "You should see ~95–99% overlap, confirming your manual gate and the unbiased algorithm agree."
            ),
            target_widget_name="AddAndGateButton",
            event_trigger="clicked",
            cyto_emotion="happy",
            next_step_id="c3_s15_compare",
        ),
        InteractionStep(
            id="c3_s15_compare",
            text=(
                "Cluster Abundance Comparison\n\n"
                "Compare cluster abundances across Samples A, B, and C in the Statistics tab.\n"
                "Look for the sample with a high proportion of immature/progenitor-like clusters (low CD3, low B220, low CD4/CD8). That will be Bone Marrow."
            ),
            target_widget_name="MainTabBar",
            event_trigger="currentChanged",
            cyto_emotion="pointing",
            next_step_id="c3_s16_reveal",
        ),
        BranchingStep(
            id="c3_s16_reveal",
            text=(
                "The Final Reveal:\n\n"
                "Sample B is the Thymus. Sample C has a high proportion of B220+ B-cells. Sample A has lots of progenitors.\n\n"
                "Which sample is the Spleen?"
            ),
            options={
                "Sample A": "c3_s16_wrong",
                "Sample B": "c3_s16_wrong",
                "Sample C": "c3_s17_graduation",
            },
        ),
        InfoStep(
            id="c3_s16_wrong",
            text=(
                "Not quite! The Spleen is a peripheral lymphoid organ rich in mature B-cells and T-cells. Look for the sample with high B220+."
            ),
            cyto_emotion="sad",
            next_step_id="c3_s16_reveal",
        ),
        InfoStep(
            id="c3_s17_graduation",
            text=(
                "Correct! Sample C is the Spleen!\n\n"
                "By elimination, Sample A is the Bone Marrow.\n\n"
                "You've mastered manual gating, pipelines, boolean logic, and automated population analysis! Course 3 complete — you are a Population Analyst! 🏆\n\n"
                "Click Next to save your final workflow."
            ),
            cyto_emotion="cheering",
            cyto_animation="cheering",
            allow_interaction=True,
            next_step_id="c3_s18_save",
        ),
        VerificationStep(
            id="c3_s18_save",
            text=(
                "Final Step: Save your completed analysis workflow.\n\n"
                "Click the 'Save Workflow' button in the toolbar."
            ),
            validator=WorkflowSavedValidator(),
            cyto_emotion="happy",
        ),
    ],
)
