# BioPro Flow Cytometry — Course Teaching Plan

## Overview

Three standalone courses that can be taken sequentially or independently. Each builds on real experimental data from the same 12-sample panel, so concepts carry across courses.

**Shared Panel:**
- **Scatter & Time:** Time, FSC-A, SSC-A
- **Viability & Lineage:** Live Stain, CD45, CD3, CD4, CD8, B220
- **Samples:** Blank, FMO APC, FMO APC-Cy7, FMO e450, FMO FITC, FMO PE, PI (Propidium Iodide), Sample A, Sample B, Sample C

**The Overarching Mystery:** Samples A, B, and C come from three different mouse tissues (Spleen, Thymus, Bone Marrow) — the learner's goal across the courses is to figure out which is which.

---

## Course 1 — Flow Cytometry Fundamentals
**Ribbons Covered:** Workspace, Compensation, Spectral, Gating
**Narrative:** *"Your samples just arrived. Let's set up the experiment, clean the data, and identify the cells."*
**Estimated Duration:** ~50–65 min
**Badge:** 🔬 Flow Fundamentalist

### Phase 1 — Introduction & Data Import

#### Step 1: Meet the Challenge
> **InfoStep** | Emotion: happy, Animation: cheering
- Introduce Cyto and the mystery (3 unknown mouse tissues).
- Explain what the learner will accomplish: import, clean, compensate, and gate.
- Mention the panel: which markers we're using and why each one is interesting.

#### Step 2: Import the Samples
> **InteractionStep** → `ImportDataButton` → clicked
- Instruct the user to click Import and add all 12 files.
- Briefly explain what each sample type is before they import:
  - **Blank:** No cells stained at all. Used as the universal negative baseline.
  - **PI (Propidium Iodide):** Dead cell viability marker — cells with broken membranes glow red.
  - **FMO Controls (×5):** FITC, PE, APC, APC-Cy7, e450 — each has everything EXCEPT one dye.
  - **Samples A, B, C:** The mystery! Your actual experimental unknowns.

#### Step 3: Verify the Import
> **VerificationStep** → `FlowImportValidator`
- BioPro verifies all 12 files by event count hash.
- On failure: guide the user to re-import.
- On success: show a summary table of the samples and their detected event counts.

#### Step 4: Assign Sample Roles
> **InteractionStep** → `PropertiesPanel` → `role_combo`
- Explain what Sample Roles are and why BioPro needs them.
- Walk the user through selecting each sample in the tree and assigning its role (Blank → Unstained, FMOs → FMO Control, A/B/C → Full Panel).
- After this, explain that the Compensation and Pipeline engines now know which samples are controls vs. experimental.

---

### Phase 2 — Compensation & Spectral

#### Step 5: What is Spillover?
> **InfoStep** | Emotion: thinking
- Explain spillover/spectral overlap with a simple analogy:
  *"Think of shining a flashlight through colored cellophane. Some light bleeds through the edges into adjacent 'bins'."*
- Show the Compensation Ribbon.

#### Step 6: The Matrix Was Already Here
> **InfoStep** | Emotion: surprised
- Explain that BioPro found a `$SPILL` keyword inside the Blank's FCS metadata.
- Explain that BioPro applied it automatically during loading — the data is already compensated.
- Walk through what the "Extract from FCS" and "Apply to All" buttons do, and explain *why* they would be needed in other scenarios (raw data, batch runs, overriding machine compensation).
- Have the user click "Extract from FCS" themselves to see the 6×6 matrix that was used.

#### Step 7: Hands-On Spectral — The Learning Compensation Tab
> **InteractionStep (upgraded — forced interaction)** → `MainTabBar` → Spectral tab
- Navigate to the Spectral Ribbon. Explain what spectral unmixing is vs. traditional compensation (spectral unmixing unmixes the complete emission spectrum of each fluorochrome mathematically, not just channel-by-channel spillover).
- **BioPro's built-in Learning Compensation mode** is used here. Instead of passively watching, the learner must actively complete each sub-task before they can advance:
  1. **Assign the Autofluorescence Reference:** Drag the Blank sample into the "Autofluorescence" slot. BioPro will not let the user proceed until this is done correctly.
  2. **Assign Single-Stain References:** For each of the 5 fluorochrome channels, drag the matching FMO (or single-stain if we had one) into its reference slot. BioPro checks these assignments and shows a ✅ or ❌ per channel.
  3. **Run the Unmixing:** Click "Unmix". BioPro runs the spectral decomposition and shows the resulting corrected plots.
- Reward: BioPro shows a before/after comparison of a sample plot (pre- and post-unmixing) so the learner can see the improvement firsthand.

---

### Phase 3 — Initial Gating Strategy

#### Step 8: Introduction to Subplots — Read the Context, Not Just the Gate
> **InfoStep** | Emotion: talking
- Before drawing any gates, introduce the **Subplot Panel**.
- Explain that every gate you draw also appears as a mini-plot in the gate hierarchy. This lets you see *how each child population looks* after filtering through its parent gate.
- **Why this matters for FMOs:** When you draw a gate on a Full Panel sample, you must also look at that same gate on the FMO sample in the subplot. The FMO subplot shows you the background spread *without* the signal — the gate boundary must sit at the far right edge of the FMO subplot, not the Full Panel subplot.
- Clarify which sample type to use on each axis:
  - **FSC / SSC gates:** Use Full Panel (Sample A). FMO controls are irrelevant here — you're gating on cell size, not fluorescence.
  - **Viability gate (Live Stain):** Use Full Panel. The viability dye is in every sample, so FMO is not needed.
  - **CD45 gate:** Use Full Panel vs. FMO APC (if CD45 is on APC). The FMO subplot anchors your upper boundary.
  - **Lineage marker gates (CD3, CD4, CD8, B220):** Always draw on Full Panel, but the boundary is dictated by the FMO subplot for that specific channel.

#### Step 9: Gate for Real Cells — FSC-A vs SSC-A
> **InteractionStep** → `Tool_polygon` → clicked
- Navigate to Sample A in the Workspace.
- Set axes to FSC-A (x) and SSC-A (y).
- Explain what FSC and SSC measure (size and granularity).
- Explain the debris cloud (bottom left) vs. the cell population (central cluster).
- Have the user draw a Polygon gate around the main cell population. Name it "Cells".
- **Check the subplot:** Confirm the "Cells" gate is capturing the correct population visually.

#### Step 10: Doublets — FSC-H Not Available in This Dataset
> **InfoStep** | Emotion: talking
- Explain doublets: when two cells flow through together, they look like one giant event. The standard practice is to plot **FSC-A (x) vs FSC-H (y)** — single cells form a tight diagonal line, while doublets deviate above it.
- **However:** Our dataset only includes FSC-A, not FSC-H. This is a data collection limitation — the cytometer was not set to record the height parameter.
- Mention that in any real experiment, you should always configure your cytometer to record height parameters (FSC-H, SSC-H) and perform doublet exclusion before proceeding.
- We continue without a singlets gate for this tutorial dataset.

#### Step 11: Gate for Live Cells
> **InteractionStep** → draw gate on Live Stain channel
- Explain the viability dye: cells that are dead have broken membranes and take up more dye, making them brighter.
- Using a histogram on the Live Stain channel, show how dead cells appear as a bright population to the right.
- Have the user draw a Range gate selecting only the dim (live) cells. Name it "Live".
- **Check the subplot:** Confirm that the Live gate excludes the bright dead cell cluster.

#### Step 12: CD45 Gate — Are These Immune Cells?
> **InfoStep / InteractionStep**
- Explain CD45: the universal leukocyte surface marker. Every white blood cell expresses it.
- Plot CD45 (y) vs FSC-A (x).
- **Axis note:** Use Full Panel Sample A as your primary view. The FMO APC subplot shows background CD45 spread — draw the gate boundary where the FMO ends.
- All three mystery tissues are immune-rich, so CD45+ cells should be the large majority.
- Have the user draw a gate for CD45+ cells. Name it "Leukocytes".
- **Check the subplot:** Make sure the FMO APC subplot shows the gate sitting right at the edge of background.

#### Step 13: Introducing FMO Controls for Lineage Markers
> **InfoStep** | Emotion: talking
- Explain the concept of FMO overlay using the images generated earlier.
- Explain that for each marker (CD3, CD4, CD8, B220), there is an FMO control to show exactly where background signal ends.
- Preview: "In Course 2, you'll use each FMO subplot to set exact boundaries for each lineage marker."

#### Step 14: Copy Gates to All Samples — The Default Behavior
> **InteractionStep** → `Copy Gates` button
- The user has gated Sample A. Now explain that Samples B and C need the same gates.
- **Default behavior:** BioPro's "Copy Gates" propagates to **all samples in the Full Panel group** by default. This is by design — in most experiments you want consistent gates across your samples.
- Mention that this can be customized (e.g., restrict to a single sample, or a sub-group) if the scientist needs different gates per sample, but we'll use the default.
- Click "Copy Gates". BioPro applies all gates and recomputes statistics in the background.

#### Step 15: Graduation
> **InfoStep** | Emotion: happy, Animation: cheering
- Recap: imported, compensated, and built a clean Cells → Live → Leukocytes hierarchy.
- Preview: "In Course 2, you'll use FMO controls to identify T-cells, B-cells, and start solving the mystery."
- Award badge: 🔬 Flow Fundamentalist

---

## Course 2 — Immunophenotyping & Analysis Basics
**Ribbons Covered:** Spectral, Pipeline, Gating, Statistics
**Prerequisite:** Course 1 completed, or saved state loaded
**Narrative:** *"The cells are clean. Now let's unmix the signals, map our workflow, and figure out who's who in the crowd."*
**Estimated Duration:** ~35–45 min
**Badge:** 🧬 Immunophenotyper

### Phase 0 — State Verification

#### Step 0: Verifying Your Workspace
> **VerificationStep** → `Course1StateValidator`
- BioPro silently verifies that the workspace state matches the expected Course 1 checkpoint (all 12 samples, roles assigned, Cells → Live → Leukocytes gated).
- **On failure:** Offer a one-click restore to the correct Course 1 checkpoint.

---

### Phase 1 — Spectral Unmixing

#### Step 1: Traditional vs Spectral
> **InfoStep** | Emotion: thinking
- Explain that while we used basic spillover compensation in Course 1, modern flow cytometry uses **Spectral Unmixing** to resolve highly overlapping fluorochromes.
- Introduce the Spectral tab.

#### Step 2: Hands-On Spectral Unmixing
> **ForcedInteractionStep** → `MainTabBar` → Spectral tab
- The learner must actively complete each sub-task to advance:
  1. **Assign Autofluorescence:** Drag the Blank sample into the "Autofluorescence" slot.
  2. **Assign References:** Drag the FMOs into their respective single-stain reference slots.
  3. **Run Unmixing:** Click "Unmix".
- **Reward:** See a before/after comparison showing improved resolution of populations.

---

### Phase 2 — Pipeline & Marker Gating

#### Step 3: Meet the Pipeline
> **InteractionStep** → Pipeline tab
- Introduce the Pipeline tab as a visual map of the gating hierarchy.
- Show how gates flow from one to the next, and explain that you can double-click a node here to open it in the Workspace.

#### Step 4: Gate CD3+ T-cells (Using FMO PE)
> **InteractionStep** → draw gate
- Plot PE channel (CD3) as a histogram on Sample A, inside the Leukocytes population.
- **Subplot:** Open the FMO PE subplot to find the true background boundary.
- Draw a Range gate. Name it "T-cells (CD3+)".

#### Step 5: Gate B-cells (Using FMO e450)
> **InteractionStep** → draw gate
- Plot e450 channel (B220) as a histogram on Sample A, also inside Leukocytes (since B-cells are CD3−).
- **Subplot:** Use the FMO e450 subplot to anchor the boundary.
- Draw a Range gate. Name it "B-cells (B220+)".

#### Step 6: Propagate Gates via the Pipeline
> **InteractionStep** → Copy Gates
- Use the "Copy Gates" feature to propagate these new T and B cell gates to Samples B and C.
- Watch the Pipeline tab automatically build out the tree for the other samples.

---

### Phase 3 — Statistics Explorer

#### Step 7: Your First Stats Table
> **InteractionStep** → Statistics tab
- Navigate to the Statistics tab.
- Explain what each statistic means: Count, %Parent, %Total.
- Compare the %Total of T-cells vs B-cells across Samples A, B, and C.

#### Step 8: Visualizing the Data (Violin Plots)
> **InteractionStep** → Statistics Explorer → chart mode
- Create a **Violin Plot** comparing T-cell and B-cell percentages across the samples.
- Foreshadow: *"These different proportions are a huge clue to which tissue is which. We'll solve the mystery in Course 3."*

#### Step 9: Graduation
> **InfoStep** | Emotion: happy, Animation: cheering
- Recap: Unmixed the data, mapped it in the pipeline, gated major populations, and explored statistics.
- Award badge: 🧬 Immunophenotyper

---

## Course 3 — Advanced Analysis & Validation
**Ribbons Covered:** Gating (Quadrant, Logic), Comparisons, Population Analysis
**Prerequisite:** Courses 1 & 2, or pre-loaded state
**Narrative:** *"Let's dig deeper into the T-cells, and let unbiased machine learning algorithms validate our manual gating strategy."*
**Estimated Duration:** ~45–55 min
**Badge:** 🧠 Population Analyst

### Phase 1 — Quadrant Gating & Comparisons

#### Step 1: Sub-typing T-cells
> **InteractionStep** → draw Quadrant gate
- Plot CD4 (FITC, x-axis) vs. CD8 (APC-Cy7, y-axis) inside the T-cells gate.
- **Subplot:** Use FMO FITC (CD4) and FMO APC-Cy7 (CD8) to perfectly anchor the crosshairs.
- Draw a Quadrant gate. Name the quadrants: CD4+ only, CD8+ only, DP (Double Positive), DN (Double Negative).

#### Step 2: The Comparisons Tab
> **InteractionStep** → Comparisons tab
- Open the Comparisons tab and overlay the DP (Double Positive) quadrant from Samples A, B, and C on a single plot.
- Highlight the DP quadrant: *"Notice the massive spike in DP T-cells in one of these samples. That is a hallmark of the Thymus."*

---

### Phase 2 — Population Analysis (UMAP & Clustering)

#### Step 3: Dimensionality Reduction (UMAP)
> **InfoStep** & **InteractionStep** → Population Analysis tab
- Explain UMAP: Compressing 6 dimensions of fluorescence into a 2D map while preserving biological relationships (islands).
- Select the **Leukocytes** gate to run UMAP on clean immune cells. Check CD45, CD3, CD4, CD8, B220. Uncheck scatter and viability.
- Run the analysis and view the UMAP islands. Color by CD3 and B220 to see the T-cell and B-cell islands light up.

#### Step 4: HDBSCAN Auto-Clustering
> **InteractionStep** → Run HDBSCAN
- Explain that HDBSCAN finds clusters in the original high-dimensional space without human bias.
- Review the resulting clusters using the Marker Expression Heatmap.
- Identify the cluster with high B220 and name it "Auto-B-cell Cluster".

---

### Phase 3 — Validating Manual Gates with Logic

#### Step 5: The Validation Strategy
> **InfoStep** | Emotion: thinking
- Explain that a powerful way to validate human gating is to intersect it with machine learning clusters. If they match perfectly, your manual strategy is rock solid.

#### Step 6: Using the AND Logic Gate
> **InteractionStep** → Pipeline tab → + AND button
- In the Pipeline, select your manual "B-cells (B220+)" gate and your new HDBSCAN "Auto-B-cell Cluster".
- Click the **+ AND** button to intersect them.
- Look at the resulting population count: it should be nearly identical to the original B-cell count, proving high overlap and validating the manual gate.

---

### Phase 4 — Solving the Full Mystery

#### Step 7: The Final Reveal
> **BranchingStep**
- Present the full data summary across Samples A, B, and C:
  - Which has the huge DP T-cell spike? (Thymus)
  - Which has a high proportion of mature B-cells and T-cells? (Spleen)
  - Which has many progenitor clusters / immature cells? (Bone Marrow)
- Ask the learner to assign the final identities.

#### Step 8: Full Graduation
> **InfoStep** | Emotion: happy, Animation: cheering
- Reveal all three tissue identities.
- Summarize the journey: raw FCS files to complex machine learning validation.
- Award badge: 🧠 Population Analyst

---

## Implementation Notes

### Sequencing & State

- Each course saves a **checkpoint state** on graduation so subsequent courses load exactly where the previous left off.
- Courses 2 and 3 offer a **"Quick Start"** mode that pre-loads a clean reference state for users who skipped earlier courses.
- Course 2's **Step 0 VerificationStep** does a hash + role + gate-hierarchy check. If the state was tampered or is missing gates, the learner is offered a one-click restore.

### Step Type Summary

| Step Type | When to Use |
|-----------|-------------|
| `InfoStep` | Pure teaching moment, no user action required |
| `InteractionStep` | User must click a specific widget to proceed |
| `VerificationStep` | BioPro validates the user's action was correct |
| `BranchingStep` | Multiple-choice question with different outcomes |

### New Step Variants Needed

| Variant | Description |
|---------|-------------|
| `ForcedInteractionStep` | Like InteractionStep, but with multiple sub-tasks that must each be completed before advancing (used in Step 7 Spectral). |
| `SubplotCheckStep` | Prompts the user to open a subplot and verify it before advancing. |

### Deferred Features (not blocking any course)
- **GatingML 2.0 export** *(Phase 8 remainder)*
- **Reporting & PDF/CSV export** *(Phase 7)*
- **High-performance pipeline optimization for >10M events** *(Phase 9)*
