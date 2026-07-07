# Getting Started with BioPro Flow Cytometry

Welcome! This guide covers everything you need to start analyzing flow cytometry data in BioPro—from loading FCS files through initial population gating and statistical analysis.

---

## 1. Interface Overview

The graphical interface is organized into four functional zones:

```
┌───────────────────────────────────────────────────────────────┐
│ RIBBONS: Workspace│Compensation│Gating│Pipeline│Statistics  │
├─────────────┬─────────────────────────────────┬───────────────┤
│             │                                 │               │
│  GROUPS &   │                                 │  PROPERTIES   │
│  SAMPLE     │        PRIMARY CANVAS           │    & STATS    │
│   TREE      │    (2D Plot or Historgram)      │    OUTPUT     │
│             │                                 │               │
│             │                                 │               │
└─────────────┴─────────────────────────────────┴───────────────┘
```

### A. Ribbons (Toolbar - Top)

Organized by analysis task:

| Ribbon | Purpose | Key Features |
|--------|---------|------|
| **Workspace** | Session management | Open/create samples, manage groups, configure workspace |
| **Compensation** | Spillover correction | Load controls, compute spillover matrix, apply compensation |
| **Gating** | Population definition | Draw gates (Rectangle, Polygon, Ellipse, Quadrant, Range) |
| **Pipeline** | Batch analysis | Execute workflows, batch process samples |
| **Statistics** | Report generation | View stats table, export, format |
| **Spectral** | Advanced visualization | Spillover heatmap, unmixing tools |
| **UMAP** | Dimensionality reduction | Configure UMAP, export embedding |
| **Encyclopedia** | Biology reference | Fluorophore/marker database lookup |

> [!SCREENSHOT PLACEHOLDER]
> Screenshot: All 8 ribbons visible in toolbar

### B. Groups & Sample Tree (Left Sidebar)

- **Groups Panel**: Filter visualizations by experimental condition (e.g., "Stimulated" vs. "Control").
  - Right-click → Create Group
  - Drag samples to assign to groups
  - Groups share gate definitions (auto-propagated)

- **Sample Tree**: Hierarchical view of all samples and populations.
  - Root level: Sample names
  - Nested: All defined populations (gates)
  - Double-click a sample: Load onto canvas
  - Double-click a population: Filter canvas to show only that population

> [!SCREENSHOT PLACEHOLDER]
> Screenshot: Sample tree with 5 samples, groups panel expanded, showing Unstained, Single-Stain controls

### C. Primary Canvas (Center)

High-performance 2D plot with multiple visualization modes:

- **Pseudocolor (Density)**: Hexbin density visualization (recommended for publication)
- **Dot Plot (Scatter)**: Individual event scatter points (best for outlier detection)
- **Contour**: 2D topological contours (publication quality)
- **Histogram**: 1D distribution plot

**Interactive Features:**
- Click-drag to define gates
- Scroll wheel: Zoom in/out
- Right-click: Context menu (export, clear gates, etc.)
- Hover: Tooltip showing nearest gate and event count

> [!SCREENSHOT PLACEHOLDER]
> Screenshot: Canvas showing pseudocolor lymphocyte plot with overlaid rectangle gate

### D. Properties & Statistics (Right Sidebar)

- **Sample Properties**:
  - Display name, file path, FCS version
  - Current axes (X/Y parameters)
  - Visualization mode and settings
  - Transform selection (Linear, Log, Logicle)

- **Statistics Table**:
  - Real-time statistics for selected population
  - Metrics: Count, Mean, Median, MFI, CV, % Parent, % Total
  - Sortable, exportable to CSV

> [!SCREENSHOT PLACEHOLDER]
> Screenshot: Properties panel showing CD4+ T cells statistics (5000 events, 25% parent, 1.2e5 MFI)

---

## 2. Complete Workflow: From Data to Results

### Phase 1: Project Setup

#### Step 1.1: Create Workspace
1. BioPro automatically creates a workspace when you load the Flow Cytometry module
2. Save workspace frequently (File → Save Workspace)

#### Step 1.2: Load FCS Files
1. Click **Workspace** ribbon → **Add Samples**
2. Select your `.fcs` files (supports batch selection)
3. Recommended: Copy FCS files to project's `assets/data/` folder for portability

> [!SCREENSHOT PLACEHOLDER]
> Screenshot: File dialog showing FCS file selection

**Supported FCS Versions:**
- FCS 2.0, 3.0, 3.1 (via FlowKit)
- Automatic channel/marker extraction
- Instrument metadata preserved

#### Step 1.3: Assign Sample Roles

Sample roles enable automated workflows (compensation, boundary detection):

1. Select sample in Sample Tree
2. Right-click → Edit Properties → Role
3. Assign role:

| Role | Use Case | Example |
|------|----------|---------|
| **Unstained** | Autofluorescence baseline | Untreated cells |
| **Single-Stain** | Spillover matrix computation | FITC-only, PE-only, APC-only controls |
| **FMO Control** | Population boundary detection | Fluorescence Minus One controls |
| **Isotype Control** | Antibody specificity validation | Isotype-matched controls |
| **Full Panel** | Experimental sample | Main cohort data |

> [!SCREENSHOT PLACEHOLDER]
> Screenshot: Sample tree showing 6 samples with role badges (Unstained, Single-Stain×3, Full Panel×2)

---

### Phase 2: Spectral Compensation (Optional but Recommended)

#### Step 2.1: Compute Spillover Matrix
1. Click **Compensation** ribbon
2. Click **Select Controls**
3. Choose:
   - Unstained control (if available)
   - Single-stain controls (one per fluorophore)
4. Click **Compute Spillover Matrix**

> [!SCREENSHOT PLACEHOLDER]
> Screenshot: Compensation dialog showing control selection and spillover matrix heatmap

**Output:** Spillover matrix showing crosstalk between detectors (e.g., FITC bleeds 2% into PE)

#### Step 2.2: Apply Compensation
1. Review spillover matrix
2. Click **Apply Compensation**
3. System automatically applies to all samples

> [!NOTE]
> Once applied, all downstream plots and gating use compensated data. Statistics recalculate automatically.

---

### Phase 3: Initial Gating (Morphology)

#### Step 3.1: Load Sample onto Canvas
1. **Sample Tree** → Double-click sample name
2. Canvas displays default axes (FSC-A vs. SSC-A)
3. Pseudocolor density plot renders automatically

> [!SCREENSHOT PLACEHOLDER]
> Screenshot: Lymphocyte population visible as high-density cloud; monocytes and debris as separate clusters

#### Step 3.2: Draw Lymphocyte Gate
1. Click **Gating** ribbon → **Rectangle** tool
2. Click-drag to encompass lymphocyte cluster on canvas
3. Release to create gate
4. Enter population name: "Lymphocytes"
5. Gate instantly appears as overlay on canvas; node added to Sample Tree

> [!SCREENSHOT PLACEHOLDER]
> Screenshot: Rectangle gate drawn around lymphocyte cluster, showing dashed red rectangle

#### Step 3.3: View Population Statistics
1. Click **Lymphocytes** node in Sample Tree
2. **Properties** panel (right) shows:
   - Event count: 80,000
   - % Parent: 80% (of all events)
   - MFI (FSC-A): 145,000
   - etc.

---

### Phase 4: Advanced Gating (Marker-Based)

#### Step 4.1: Switch to Marker Axes
1. Canvas bottom: X-axis selector
2. Change to: "CD3-FITC" (or desired marker)
3. Canvas top: Y-axis selector
4. Change to: "CD4-PE"
5. Canvas auto-redraws with new axes

> [!SCREENSHOT PLACEHOLDER]
> Screenshot: Canvas now showing CD3-FITC vs CD4-PE plot; CD4+ cells visible as distinct population upper-right

#### Step 4.2: Draw CD4+ T Cell Gate
1. Click **Gating** ribbon → **Rectangle** (or **Quadrant** for CD4/CD8 split)
2. Define CD4+ region on canvas
3. Gate is automatically parented to "Lymphocytes" population

> [!TIP]
> **Quadrant Gate Shortcut**: Use **Quadrant** tool for automated 4-way split on two markers (CD4 vs CD8). Creates Q1-Q4 subpopulations instantly.

#### Step 4.3: Apply to Full Experiment
- Gate automatically propagates to all samples in the same group (200ms debounce)
- Check **Properties** panel: Statistics automatically recompute for all samples

---

### Phase 5: Hierarchical Gating (Optional Advanced)

#### Step 5.1: Parent-Child Relationships
1. Select gate in Sample Tree
2. When drawing new gate, click **Gating** ribbon → **On Gate** to set parent
3. New gate inherits parent population filtering

**Example Hierarchy:**
```
All Events
├── Lymphocytes (FSC-A, SSC-A rectangle)
│   ├── Singlets (FSC-A vs FSC-H rectangle)
│   │   ├── CD4+ (CD3+ CD4+)
│   │   └── CD8+ (CD3+ CD8+)
│   └── CD3+ T Cells (CD3 range gate)
└── Monocytes (FSC-A, SSC-A rectangle)
```

#### Step 5.2: View Gate Hierarchy
**Node Canvas** (side panel):
- Visual DAG (Directed Acyclic Graph) of population relationships
- Drag nodes to reposition
- Right-click edges to delete connections
- Automatically layouts to prevent overlap

> [!SCREENSHOT PLACEHOLDER]
> Screenshot: Node canvas showing 8 populations connected in hierarchical tree

---

## 3. Statistical Analysis & Export

### Step A: View Statistics

1. Select population in Sample Tree
2. **Properties** panel (right) displays:
   - **Count**: Total events in population
   - **Mean**: Average parameter intensity
   - **Median** / **MFI**: Median intensity (standard metric)
   - **CV**: Coefficient of variation (spread)
   - **%Parent**: Percentage of parent population
   - **%Total**: Percentage of all events

### Step B: Compare Populations

1. Select multiple populations (Ctrl+Click)
2. **Statistics** ribbon → **Compare**
3. Generate comparison table (all metrics, all populations)

> [!SCREENSHOT PLACEHOLDER]
> Screenshot: Statistics table showing CD4+, CD8+, DN (double-negative), DP (double-positive) populations side-by-side with MFI, CV, percentages

### Step C: Export Results

Multiple export options:

| Format | Use Case | Content |
|--------|----------|---------|
| **CSV** | Excel/analysis software | Statistics table (easily imported to R, Python, GraphPad) |
| **PDF** | Publication/report | High-quality figures (300 DPI, vector graphics) |
| **PNG/TIFF** | Presentations | Raster images (specified DPI) |
| **GatingML** | Reproducible analysis | Gate definitions (importable into other software) |

**Export Workflow:**
1. Select population(s) in Sample Tree
2. Right-click → **Export**
3. Choose format and location
4. Statistics and plots export together

> [!SCREENSHOT PLACEHOLDER]
> Screenshot: Export dialog showing CSV, PDF, PNG options with preview

---

## 4. Tips & Tricks

### Efficiency Tips
- **Undo/Redo**: Ctrl+Z / Ctrl+Y to undo gate edits
- **Keyboard Shortcuts**: See [Keyboard Shortcuts Guide](./09_KEYBOARD_SHORTCUTS.md)
- **Template Saving**: After setting up a protocol, save as template for reuse on new samples
- **Batch Gating**: Use **Pipeline** ribbon to apply gates to multiple samples simultaneously

### Quality Tips
- **FMO Controls**: Always use FMO controls for accurate boundary detection (automated via FMO role)
- **Live/Dead Filtering**: Apply viability marker gate early in hierarchy
- **Transform Selection**: Use **Logicle** (biexponential) for all fluorescence channels; **Linear** for scatter
- **Remove Debris**: Apply forward/side scatter gates early to improve visualization

### Troubleshooting
See [Troubleshooting Guide](./10_TROUBLESHOOTING.md) for common issues:
- "Empty plot" → Check axis parameter selection and data range
- "Gates not propagating" → Verify samples in same group
- "Slow rendering" → Switch to "Fast Preview" in Workspace settings for large datasets

---

## 5. Next Steps

- **[Workspace Ribbon Guide](./02_WORKSPACE_RIBBON.md)**: Advanced session management, groups, and presets
- **[Compensation Ribbon Guide](./03_COMPENSATION_RIBBON.md)**: Detailed spillover correction workflows
- **[Gating Ribbon Guide](./04_GATING_RIBBON.md)**: All gate types, Boolean logic, node operations
- **[Statistics Ribbon Guide](./06_STATISTICS_RIBBON.md)**: Advanced metric calculation and export
- **[Scientific Logic](./03_SCIENTIFIC_LOGIC.md)**: Mathematical principles behind transforms and compensation
- **[UMAP Guide](./08_UMAP_RIBBON.md)**: Dimensionality reduction and discovery analysis

---

## Keyboard Reference

| Action | Shortcut |
|--------|----------|
| Undo | Ctrl+Z |
| Redo | Ctrl+Y |
| Save | Ctrl+S |
| Zoom In | Scroll Up / + |
| Zoom Out | Scroll Down / - |
| Pan | Middle-click Drag |
| Delete Gate | Delete / Backspace |
| Select Multiple | Ctrl+Click |

See [Complete Shortcuts List](./09_KEYBOARD_SHORTCUTS.md) for more.
