"""Karcytics Flow Cytometry — Academy Courses.

Step conventions:
  InfoStep              — teaches a concept; user clicks Next → to continue.
  InteractionStep       — user must click/interact with a named widget to auto-advance.
  VerificationStep      — auto-polls a validator every ~2 s and advances automatically.
                          Set allow_interaction=True only if the user also needs to freely
                          interact with the UI before clicking the manual 'Check ✓' button.
  BranchingStep         — presents options that route to different next steps (quizzes).

Spotlight convention:
  target_widget_name  — single objectName for InteractionStep highlight.
  target_widget_names — list of objectNames for multi-target InfoStep spotlights.

Main tab bar order (0-indexed): Workspace, Compensation, Gating, Pipeline,
Statistics, Spectral, Population Analysis, Comparisons.

Panel reference — see course2.py header for the full CD45/CD3/CD4/CD8/B220/PI
channel map. Course 3 does no new gating: it proves what Course 2 hypothesized
(Sample A = Thymus) and resolves Spleen vs. Bone Marrow using statistics,
comparison charts, and unsupervised population analysis.
"""

from karcytics.core.models.tutorial_models import (
    BranchingStep,
    Course,
    InfoStep,
    InteractionStep,
    VerificationStep,
)

from .validators import (
    ComparisonPlotTypeValidator,
    LogicGateExistsValidator,
    StatsChartTypeValidator,
    TabActiveValidator,
    UmapClusterExportedValidator,
    WorkflowSavedValidator,
)

# ==============================================================================
# Course 3 — Population Analysis & Advanced Comparisons
# Advanced content: no new gating. Statistics, Comparisons, and unsupervised
# Population Analysis prove the Course 2 hypothesis and solve the mystery.
# ==============================================================================

course_3_analysis = Course(
    id="flow_course_3_analysis",
    title="Population Analysis & Advanced Comparisons",
    description=(
        "Prove your Course 2 hypothesis with real statistics, explore every "
        "comparison chart type, and let UMAP/HDBSCAN validate your manual gates."
    ),
    estimated_minutes=45,
    badge_reward="Population Analyst",
    badge_icon="🧠",
    prerequisite_course_ids=["flow_course_2_gating"],
    steps=[
        InfoStep(
            id="c3_s00_intro",
            text=(
                "Welcome to Course 3! 🧠\n\n"
                "Your hypothesis from Course 2: Sample A is the Thymus, based on "
                "its dramatically higher DP T-cell percentage.\n\n"
                "This course proves it with real statistics, walks every "
                "comparison chart type, and uses unsupervised clustering to "
                "double-check your manual gates — then solves the rest of the "
                "mystery: which is Spleen, and which is Bone Marrow?"
            ),
            cyto_emotion="happy",
            next_step_id="c3_s01_stats_switch",
        ),
        # ── Statistics tab ───────────────────────────────────────────────────
        InteractionStep(
            id="c3_s01_stats_switch",
            text="Click the 'Statistics' tab at the top.",
            cyto_emotion="pointing",
            target_widget_name="MainTabBar",
            target_widget_names=["MainTabBar"],
            event_trigger="currentChanged",
            next_step_id="c3_s02_verify_stats_tab",
        ),
        VerificationStep(
            id="c3_s02_verify_stats_tab",
            text="Checking tab...",
            cyto_emotion="scanning",
            hide_next_button=True,
            allow_interaction=False,
            validator=TabActiveValidator(4),
            on_success_step_id="c3_s03_stats_theory",
            on_fail_step_id="c3_s02b_wrong_tab",
        ),
        InteractionStep(
            id="c3_s02b_wrong_tab",
            text="Oops! Click the 'Statistics' tab to proceed.",
            cyto_emotion="surprised",
            target_widget_name="MainTabBar",
            target_widget_names=["MainTabBar"],
            event_trigger="currentChanged",
            next_step_id="c3_s02_verify_stats_tab",
        ),
        InfoStep(
            id="c3_s03_stats_theory",
            text=(
                "Choosing the right statistic 📊\n\n"
                "• % Parent — fraction of the immediate parent gate (e.g. % CD4+ "
                "out of T-cells). Shows your gating hierarchy step by step.\n"
                "• % Total — fraction of ALL events in the tube. The number to "
                "use when comparing a population's true abundance across samples.\n"
                "• Median / MFI — the standard, outlier-robust measure of "
                "fluorescence intensity. Avoid the arithmetic Mean on log-scaled "
                "fluorescence data — outliers skew it badly.\n"
                "• CV (Coefficient of Variation) — how tight or spread-out a "
                "peak is. High CV = broad, messy population."
            ),
            cyto_emotion="talking",
            next_step_id="c3_s04_select_pops",
        ),
        InfoStep(
            id="c3_s04_select_pops",
            text=(
                "Select populations to compare 📋\n\n"
                "In the sidebar, check T-cells, B-cells, CD4+ only, CD8+ only, "
                "DP, and DN — across Samples A, B, and C."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            next_step_id="c3_s05_select_stats",
        ),
        InfoStep(
            id="c3_s05_select_stats",
            text=(
                "Pick a reasonable stat set: '% Total' (cross-sample abundance), "
                "'MFI' (expression-level sanity check), and 'CV' (peak "
                "sharpness). Add them from the stat picker."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            next_step_id="c3_s06_read_table",
        ),
        InfoStep(
            id="c3_s06_read_table",
            text=(
                "Reading the table 🔍\n\n"
                "Focus on the % Total column for 'DP' across Samples A, B, C. "
                "Does Sample A's number back up your Course 2 hypothesis?"
            ),
            cyto_emotion="thinking",
            target_widget_names=["PropertiesPanel"],
            next_step_id="c3_s07_chart_toggle",
        ),
        InteractionStep(
            id="c3_s07_chart_toggle",
            text="Click '📈 Chart' (highlighted) to switch from table to chart view.",
            target_widget_name="StatsChartMode",
            event_trigger="clicked",
            cyto_emotion="pointing",
            next_step_id="c3_s08_grouped_bar",
        ),
        VerificationStep(
            id="c3_s08_grouped_bar",
            text=(
                "From the chart-type dropdown, select 'Grouped Bar' and build a "
                "bar chart of DP % Total across Samples A, B, and C."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["StatsChartTypeCombo"],
            validator=StatsChartTypeValidator("grouped bar"),
            on_success_step_id="c3_s09_bar_read",
        ),
        InfoStep(
            id="c3_s09_bar_read",
            text=(
                "There's your proof, in a bar chart. 📊\n\n"
                "One bar towers over the other two — that's your quantitative "
                "confirmation of the Thymus call."
            ),
            cyto_emotion="happy",
            next_step_id="c3_s10_heatmap",
        ),
        VerificationStep(
            id="c3_s10_heatmap",
            text=(
                "Now switch the chart-type dropdown to 'Heatmap' to see all 6 "
                "populations × 3 samples at once."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["StatsChartTypeCombo"],
            validator=StatsChartTypeValidator("heatmap"),
            on_success_step_id="c3_s11_heatmap_read",
        ),
        InfoStep(
            id="c3_s11_heatmap_read",
            text=(
                "One-glance organ ID 🗺️\n\n"
                "A good heatmap makes the mystery samples' identities almost "
                "readable at a glance. Keep this pattern in mind — you'll see a "
                "fancier version of it in Comparisons next."
            ),
            cyto_emotion="talking",
            next_step_id="c3_s12_comparisons_switch",
        ),
        # ── Comparisons tab — all 5 chart types ─────────────────────────────────
        InteractionStep(
            id="c3_s12_comparisons_switch",
            text="Click the 'Comparisons' tab at the top.",
            cyto_emotion="pointing",
            target_widget_name="MainTabBar",
            target_widget_names=["MainTabBar"],
            event_trigger="currentChanged",
            next_step_id="c3_s13_verify_comparisons_tab",
        ),
        VerificationStep(
            id="c3_s13_verify_comparisons_tab",
            text="Checking tab...",
            cyto_emotion="scanning",
            hide_next_button=True,
            allow_interaction=False,
            validator=TabActiveValidator(7),
            on_success_step_id="c3_s14_comparisons_intro",
            on_fail_step_id="c3_s13b_wrong_tab",
        ),
        InteractionStep(
            id="c3_s13b_wrong_tab",
            text="Oops! Click the 'Comparisons' tab to proceed.",
            cyto_emotion="surprised",
            target_widget_name="MainTabBar",
            target_widget_names=["MainTabBar"],
            event_trigger="currentChanged",
            next_step_id="c3_s13_verify_comparisons_tab",
        ),
        InfoStep(
            id="c3_s14_comparisons_intro",
            text=(
                "5 ways to compare 🎨\n\n"
                "This tab has 5 dedicated chart types. Let's walk all of them — "
                "each is genuinely better suited to a different question."
            ),
            cyto_emotion="talking",
            target_widget_names=["ComparisonsPlotTypeCombo"],
            next_step_id="c3_s15_violin",
        ),
        VerificationStep(
            id="c3_s15_violin",
            text=(
                "Select '🎻 Violin Plot'. Compare DP % Total (or CD3 expression) "
                "across Samples A, B, C side-by-side."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["ComparisonsPlotTypeCombo"],
            validator=ComparisonPlotTypeValidator("violin"),
            on_success_step_id="c3_s16_violin_info",
        ),
        InfoStep(
            id="c3_s16_violin_info",
            text=(
                "Wide violin = many cells at that intensity. Sample A's DP "
                "violin should look dramatically higher and tighter than B or C."
            ),
            cyto_emotion="happy",
            next_step_id="c3_s17_heatmap",
        ),
        VerificationStep(
            id="c3_s17_heatmap",
            text=(
                "Select '🗺️ Channel Heatmap'. Rows = samples, columns = "
                "channels, color = median expression — the one-glance view."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["ComparisonsPlotTypeCombo"],
            validator=ComparisonPlotTypeValidator("channel heatmap"),
            on_success_step_id="c3_s18_heatmap_info",
        ),
        InfoStep(
            id="c3_s18_heatmap_info",
            text=(
                "Thymus rows should light up for CD3/CD4/CD8; a Bone-Marrow-like "
                "row lights up for B220/IgM-type markers instead."
            ),
            cyto_emotion="talking",
            next_step_id="c3_s19_radar",
        ),
        VerificationStep(
            id="c3_s19_radar",
            text=(
                "Select '🕷️ Radar Chart'. Add DP, CD4+ only, CD8+ only, and "
                "B-cells — each sample becomes its own colored polygon."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["ComparisonsPlotTypeCombo"],
            validator=ComparisonPlotTypeValidator("radar"),
            on_success_step_id="c3_s20_radar_info",
        ),
        InfoStep(
            id="c3_s20_radar_info",
            text=(
                "The shape IS the identity 🕸️\n\n"
                "Completely different polygon shapes across samples reveal "
                "different tissues at a glance, no numbers required."
            ),
            cyto_emotion="happy",
            next_step_id="c3_s23_histogram_overlay",
        ),
        VerificationStep(
            id="c3_s23_histogram_overlay",
            text=(
                "Select '📊 Histogram Overlay'. Check all 5 lineage populations "
                "(T-cells, B-cells, CD4+ only, CD8+ only, DP) on one sample, one "
                "channel — 5 histograms, one plot."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["ComparisonsPlotTypeCombo"],
            validator=ComparisonPlotTypeValidator("histogram overlay"),
            on_success_step_id="c3_s24_histogram_info",
        ),
        InfoStep(
            id="c3_s24_histogram_info",
            text=(
                "Overlay vs. Ridge 🏔️\n\n"
                "'Overlay' mode stacks all 5 on one shared axis — great up to "
                "roughly a dozen series before colors start repeating. 'Ridge' "
                "mode staggers them vertically — try both, but Ridge gets "
                "visually crowded well before Overlay does, so reach for Ridge "
                "only with a handful of series like this."
            ),
            cyto_emotion="thinking",
            next_step_id="c3_s25_pop_analysis_switch",
        ),
        # ── Population Analysis: UMAP + HDBSCAN ─────────────────────────────────
        InteractionStep(
            id="c3_s25_pop_analysis_switch",
            text="Click the 'Population Analysis' tab at the top.",
            cyto_emotion="pointing",
            target_widget_name="MainTabBar",
            target_widget_names=["MainTabBar"],
            event_trigger="currentChanged",
            next_step_id="c3_s26_verify_pop_tab",
        ),
        VerificationStep(
            id="c3_s26_verify_pop_tab",
            text="Checking tab...",
            cyto_emotion="scanning",
            hide_next_button=True,
            allow_interaction=False,
            validator=TabActiveValidator(6),
            on_success_step_id="c3_s27_umap_theory",
            on_fail_step_id="c3_s26b_wrong_tab",
        ),
        InteractionStep(
            id="c3_s26b_wrong_tab",
            text="Oops! Click the 'Population Analysis' tab to proceed.",
            cyto_emotion="surprised",
            target_widget_name="MainTabBar",
            target_widget_names=["MainTabBar"],
            event_trigger="currentChanged",
            next_step_id="c3_s26_verify_pop_tab",
        ),
        InfoStep(
            id="c3_s27_umap_theory",
            text=(
                "Understanding UMAP — A Deep Dive 🧠\n\n"
                "You have 6 fluorescence channels — each cell is a point in 6D "
                "space. UMAP flattens that manifold into a 2D map.\n\n"
                "The axes have no biological meaning; what matters is the "
                "relative position and size of the 'islands' — each one should "
                "correspond to a biologically coherent population."
            ),
            cyto_emotion="thinking",
            next_step_id="c3_s28_umap_config",
        ),
        InteractionStep(
            id="c3_s28_umap_config",
            text=(
                "Configure and run UMAP:\n\n"
                "1. Set the root population to 'Leukocytes' — the same "
                "population you've been gating T/B-cells out of all along.\n"
                "2. Uncheck FSC-A, SSC-A, and PI. Keep CD45, CD3, CD4, CD8, B220.\n"
                "3. Set n_neighbors = 15, min_dist = 0.10.\n"
                "4. Click 'Run Analysis'."
            ),
            target_widget_name="RunAnalysisButton",
            event_trigger="clicked",
            cyto_emotion="pointing",
            next_step_id="c3_s29_umap_read",
        ),
        InfoStep(
            id="c3_s29_umap_read",
            text=(
                "Reading the islands 🏝️\n\n"
                "Color the UMAP by CD3 expression to watch the T-cell island "
                "light up, then by B220 for B-cells. Island size differs across "
                "tissues — that's your next clue for Spleen vs. Bone Marrow."
            ),
            cyto_emotion="happy",
            next_step_id="c3_s30_hdbscan",
        ),
        InteractionStep(
            id="c3_s30_hdbscan",
            text=(
                "Check 'Run HDBSCAN Auto-Clustering' and click 'Run Analysis' "
                "again.\n\n"
                "HDBSCAN clusters on the original 6D data (not the 2D UMAP "
                "projection) and groups cells with zero human input — a fully "
                "independent check on your manual gates."
            ),
            target_widget_name="RunAnalysisButton",
            event_trigger="clicked",
            cyto_emotion="pointing",
            next_step_id="c3_s31_export_intro",
        ),
        InfoStep(
            id="c3_s31_export_intro",
            text=(
                "Exporting a cluster as a real population 📤\n\n"
                "In the 'Export Populations' panel on the right, each detected "
                "cluster gets a checkbox and an editable name. Find the cluster "
                "that lights up for B220 in the marker heatmap — that's your "
                "unsupervised B-cell population."
            ),
            cyto_emotion="talking",
            target_widget_names=["ClusterResultsTabs"],
            next_step_id="c3_s32_export_cluster",
        ),
        VerificationStep(
            id="c3_s32_export_cluster",
            text=(
                "1. Rename the B220-high cluster's 'Population Name' field to "
                "exactly 'HDBSCAN B-cells'.\n"
                "2. Make sure its checkbox is checked.\n"
                "3. Click '➕ Create Populations' (highlighted).\n\n"
                "This creates a 'UMAP Reduction' node in your Pipeline with "
                "your named cluster underneath it — a real, usable population."
            ),
            cyto_emotion="pointing",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["CreatePopulationsButton"],
            validator=UmapClusterExportedValidator(),
            on_success_step_id="c3_s33_export_done",
        ),
        InfoStep(
            id="c3_s33_export_done",
            text=(
                "Exported! ✅\n\n"
                "Now let's put your Course 2 Pipeline skills to real use: "
                "validate your manual B-cells gate against this computed cluster."
            ),
            cyto_emotion="happy",
            next_step_id="c3_s34_pipeline_switch",
        ),
        InteractionStep(
            id="c3_s34_pipeline_switch",
            text="Click the 'Pipeline' tab at the top.",
            cyto_emotion="pointing",
            target_widget_name="MainTabBar",
            target_widget_names=["MainTabBar"],
            event_trigger="currentChanged",
            next_step_id="c3_s35_verify_pipeline_tab",
        ),
        VerificationStep(
            id="c3_s35_verify_pipeline_tab",
            text="Checking tab...",
            cyto_emotion="scanning",
            hide_next_button=True,
            allow_interaction=False,
            validator=TabActiveValidator(3),
            on_success_step_id="c3_s36_and_gate_intro",
            on_fail_step_id="c3_s35b_wrong_tab",
        ),
        InteractionStep(
            id="c3_s35b_wrong_tab",
            text="Oops! Click the 'Pipeline' tab to proceed.",
            cyto_emotion="surprised",
            target_widget_name="MainTabBar",
            target_widget_names=["MainTabBar"],
            event_trigger="currentChanged",
            next_step_id="c3_s35_verify_pipeline_tab",
        ),
        InfoStep(
            id="c3_s36_and_gate_intro",
            text=(
                "Manual gate vs. computed cluster — the AND node 🔗\n\n"
                "Recall from Course 2: '+ AND' creates a blank logic node with "
                "no parents. You wire two populations into it by dragging a "
                "connection line from each into the new node."
            ),
            cyto_emotion="thinking",
            next_step_id="c3_s37_build_and",
        ),
        InteractionStep(
            id="c3_s37_build_and",
            text="Click '+ AND' (highlighted) to create a new logic node.",
            target_widget_name="AddAndGateButton",
            event_trigger="clicked",
            cyto_emotion="pointing",
            next_step_id="c3_s38_wire_and",
        ),
        VerificationStep(
            id="c3_s38_wire_and",
            text=(
                "Drag a connection from your manual 'B-cells' node into the new "
                "AND node, then drag another from 'HDBSCAN B-cells' into it too. "
                "You should see ~95–99% overlap between the two independent "
                "methods."
            ),
            cyto_emotion="thinking",
            allow_interaction=True,
            hide_next_button=True,
            target_widget_names=["PipelineCanvas"],
            validator=LogicGateExistsValidator("AND", ["b-cells", "hdbscan b-cells"]),
            on_success_step_id="c3_s39_and_stats_intro",
        ),
        InfoStep(
            id="c3_s39_and_stats_intro",
            text=(
                "Independent confirmation, wired together. 🎉\n\n"
                "Let's pull real numbers on that intersection — head back to "
                "the Statistics tab."
            ),
            cyto_emotion="happy",
            next_step_id="c3_s40_stats_switch2",
        ),
        InteractionStep(
            id="c3_s40_stats_switch2",
            text="Click the 'Statistics' tab at the top.",
            cyto_emotion="pointing",
            target_widget_name="MainTabBar",
            target_widget_names=["MainTabBar"],
            event_trigger="currentChanged",
            next_step_id="c3_s41_verify_stats_tab2",
        ),
        VerificationStep(
            id="c3_s41_verify_stats_tab2",
            text="Checking tab...",
            cyto_emotion="scanning",
            hide_next_button=True,
            allow_interaction=False,
            validator=TabActiveValidator(4),
            on_success_step_id="c3_s42_and_stats_read",
            on_fail_step_id="c3_s41b_wrong_tab",
        ),
        InteractionStep(
            id="c3_s41b_wrong_tab",
            text="Oops! Click the 'Statistics' tab to proceed.",
            cyto_emotion="surprised",
            target_widget_name="MainTabBar",
            target_widget_names=["MainTabBar"],
            event_trigger="currentChanged",
            next_step_id="c3_s41_verify_stats_tab2",
        ),
        InfoStep(
            id="c3_s42_and_stats_read",
            text=(
                "Select the new AND node's population and pull its Count, "
                "% Parent, and CV.\n\n"
                "A count close to both parent populations and a CV similar to "
                "your manual 'B-cells' gate is strong quantitative proof that "
                "an unbiased algorithm and your own eyes agree."
            ),
            cyto_emotion="happy",
            next_step_id="c3_s43_final_intro",
        ),
        # ── Final reveal ─────────────────────────────────────────────────────────
        InfoStep(
            id="c3_s43_final_intro",
            text=(
                "One mystery left. 🔍\n\n"
                "Sample A is confirmed as the Thymus. Between Samples B and C: "
                "one is rich in mature B220+ B-cells and T-cells (a peripheral "
                "lymphoid organ), the other is dominated by immature, "
                "low-marker progenitor-like clusters. Use your Comparisons "
                "charts and cluster stats to decide."
            ),
            cyto_emotion="thinking",
            next_step_id="c3_s44_final_quiz",
        ),
        BranchingStep(
            id="c3_s44_final_quiz",
            text="Which sample is the Spleen?",
            options={
                "Sample A": "c3_s45_final_wrong",
                "Sample B": "c3_s45_final_wrong",
                "Sample C": "c3_s46_reveal",
            },
        ),
        InfoStep(
            id="c3_s45_final_wrong",
            text=(
                "Not quite! The Spleen is a peripheral lymphoid organ rich in "
                "mature B-cells and T-cells — look for the sample with high "
                "B220+ and strong lineage marker expression, not progenitor "
                "clusters."
            ),
            cyto_emotion="sad",
            next_step_id="c3_s44_final_quiz",
        ),
        InfoStep(
            id="c3_s46_reveal",
            text=(
                "Correct! Sample C is the Spleen. 🎉\n\n"
                "By elimination, Sample B is the Bone Marrow — its abundance of "
                "immature, low-CD3/low-B220 progenitor-like clusters gives it away.\n\n"
                "Mystery solved:\n"
                "  Sample A = Thymus\n"
                "  Sample B = Bone Marrow\n"
                "  Sample C = Spleen\n\n"
                "You've mastered manual gating, pipelines, boolean logic, "
                "statistics, every comparison chart type, and unsupervised "
                "population analysis. Click Next to save your final workflow."
            ),
            cyto_emotion="cheering",
            cyto_animation="cheering",
            allow_interaction=True,
            next_step_id="c3_s47_save",
        ),
        VerificationStep(
            id="c3_s47_save",
            text="Click the 'Save Workflow' button in the toolbar.",
            validator=WorkflowSavedValidator(),
            cyto_emotion="happy",
            on_success_step_id="c3_s48_graduation",
        ),
        InfoStep(
            id="c3_s48_graduation",
            text=(
                "Course 3 complete — you are a Population Analyst! 🏆\n\n"
                "Every part of this module, taught end to end."
            ),
            cyto_emotion="cheering",
            cyto_animation="cheering",
        ),
    ],
)
