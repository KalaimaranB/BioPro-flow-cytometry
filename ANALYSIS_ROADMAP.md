# Flow Cytometry Analysis — Implementation Roadmap

This document outlines the phased implementation plan for elevating the Flow Cytometry module into a robust, high-performance analytical tool.

> [!NOTE]
> **Design Principles**
> - Utilize existing, validated libraries — avoid redundant algorithm implementation.
> - `flowkit` (+ `flowutils`, `flowio`) for FCS I/O, transforms (Logicle), and compensation.
> - `matplotlib` embedded via `FigureCanvasQTAgg` for plotting and interactive gate drawing.
> - Cross-sample gate propagation is a **core requirement**, not a secondary feature.
> - Adaptive gating is a **future optimization** — currently deprioritized.

---

## Dependencies (Integrated into BioPro Core)

| Package | Purpose |
|---------|---------|
| `flowkit` | FCS parsing, Logicle/biexponential transforms, compensation, GatingML integration |
| `flowio` | Low-level FCS parsing (dependency of `flowkit`) |
| `flowutils` | C-extension algorithmic transforms (dependency of `flowkit`) |
| `numpy` | Numerical operations and matrix algebra |
| `pandas` | DataFrame state management |
| `matplotlib` | Embedded canvas and geometric gate drawing |
| `scipy` | Kernel Density Estimation (KDE) and peak detection |

---

## Phase Progress Overview

- [x] **Phase 1: Data Visualization** — *Complete*
- [x] **Phase 2: Spectral Compensation** — *Complete*
- [x] **Phase 3: Interactive Geometric Gating** — *Complete*
- [x] **Phase 4: Cross-Sample Gate Propagation** — *Complete*
- [x] **Phase 5: State Integrity & SDK Alignment** — *Complete*
- [/] **Phase 6: Marker Awareness & Sample Tracking** — *In Progress*
- [ ] **Phase 7: Reporting & Batch Export** — *Planned*
- [x] **Phase 8: Advanced Analytical Features (UMAP & Discovery)** — *Complete*
- [ ] **Phase 9: High-Performance Pipeline Optimization** — *Planned*

---

## Phase 1 — Data Visualization [COMPLETE]

**Goal**: Parse FCS datasets and render interactive coordinate plots.

1. **Refactor `fcs_io.py`** — Replaced raw `fcsparser` with `flowkit.Sample`.
2. **Refactor `transforms.py`** — Implemented Parks 2006 Logicle algorithm via `flowkit.transforms`.
3. **Build `FlowCanvas`** — Engineered a custom Matplotlib canvas for dot plots, pseudocolor density, and histograms.
4. **Interface Integration** — Linked axis selection and display mode events to asynchronous canvas redraws.
5. **Sample Tree Integration** — Connected file parsing to double-click instantiation workflows.

---

## Phase 2 — Spectral Compensation [COMPLETE]

**Goal**: Algorithmically compute and apply spectral spillover matrices.

1. **Calculate Spillover** — Integrated single-stain control computational algorithms.
2. **Spillover Matrix Editor** — Engineered an interactive matrix interface with dynamic fluorochrome indexing.
3. **Apply Compensation** — Linked matrix application to real-time rendering engine updates.
4. **Embedded Metadata extraction** — Automated parsing of `$SPILL` / `$SPILLOVER` binary keywords.

---

## Phase 3 — Interactive Geometric Gating [COMPLETE]

**Goal**: Enable interactive geometric boundary definition directly on the coordinate canvas.

1. **Interactive Tools** — Deployed mouse event handlers for Rectangle, Polygon, Ellipse, and Range bounds.
2. **Visual Geometries** — Rendered real-time boundary previews utilizing alpha compositing.
3. **Hierarchical Propagation** — Linked geometric boundaries to the `GateNode` tree topology.
4. **Quadrant Definition** — Deployed real-time bifurcating crosshairs.
5. **Event Abort Handlers** — Configured escape keystrokes to synchronously terminate drawing operations across all views.

---

## Phase 4 — Cross-Sample Gate Propagation [COMPLETE]

**Goal**: Synchronize geometric boundaries across experimental groups seamlessly.

1. **GatePropagator** — Implemented a background thread scheduler for synchronous hierarchy updates.
2. **Event Debouncing** — Engineered a ~200ms input debounce algorithm to eliminate UI render latency during geometry translation.
3. **Real-Time Statistics** — Configured synchronous updates for population statistics and UI badges.

---

## Phase 5 — State Integrity & SDK Alignment [COMPLETE]

**Goal**: Enforce BioPro architectural compliance and guarantee stable state transitions.

1. **Logging Architecture** — Migrated generic loggers across all 35 source files to the context-aware SDK `get_logger`.
2. **State Serialization** — Implemented comprehensive `from_dict()` serialization within `FlowState` to re-establish nested domain objects during history stack traversal, eliminating critical undo/redo failures.
3. **Transform State Inheritance** — Configured coordinate scales to persist previous transformation types during axis switching, preventing generic linear resets.
4. **Synchronized Rendering Memory** — Wired cancellation events to synchronously flush `GATE_PREVIEW` memory pools across the `CentralEventBus`.

---

## Phase 6 — Marker Awareness & Sample Tracking [IN PROGRESS]

**Goal**: Systematically manage fluorophore-to-marker mapping across populations.

1. **Stateful Marker Badges** — Deploy UI indicators on the `SampleTree` reflecting configured spectral channels.
2. **Algorithmic Warnings** — Flag missing FMO controls expected by the overarching workflow template.
3. **Contextual Axis Labeling** — Render user-mapped biological markers (e.g., `"CD4 (FITC)"`) in lieu of generic detector names (e.g., `"FL1-A"`).
4. **FMO Auto-Gating** — Implement single-shot threshold determination utilizing the 99th percentile of algorithmic FMO distributions.

---

## Phase 7 — Reporting & Batch Export [PLANNED]

**Goal**: Engineer high-fidelity publication outputs and batch computational pipelines.

1. **Analytical Statistics Table** — Deploy customizable schemas for population counts, MFI, CV, and percent-parent metrics.
2. **Tabular Export** — Enable CSV extraction of computed statistical tables.
3. **Publication Vector Graphics** — Export 300+ DPI PDF/PNG plots with lossless geometric annotations.
4. **Batch Group Execution** — Enable synchronous strategy execution across entire cohort group templates.

---

## Phase 8 — Advanced Analytical Features (UMAP & Discovery) [COMPLETE]

**Goal**: Introduce high-dimensional discovery capabilities and bridge exploratory visualization with rigorous quantitative analysis.

1. **Dimensionality Reduction (UMAP)** ✅ — Full UI with sample/gate/channel selection, n_neighbors, min_dist, metric, random seed, and subsampling controls. Run history tracking with named runs.
2. **Channel Exclusion/Selection** ✅ — Per-channel checkboxes allow users to exclude viability/scatter channels from the embedding.
3. **Auto-Clustering (HDBSCAN)** ✅ — Integrated HDBSCAN producing discrete Cluster IDs with configurable minimum cluster size. Cluster statistics table and 100% stacked marker expression bar chart included.
4. **Per-Cluster Marker Profiling** ✅ — Interactive marker expression heatmap and stacked expression profile visualization across all auto-detected clusters.
5. **Custom Population Drawing (Back-Gating)** ✅ — Polygon selector tool on the Interactive Map allows users to draw arbitrary regions on the UMAP projection, creating named custom populations with event counts and exportable masks.
6. **Hover Neighborhood Stats** ✅ — Real-time `HoverStatsWidget` displays local marker expression bars (n=50 nearest neighbors) as the user moves the cursor over the UMAP.
7. **Boolean Logic Gating** *(Planned)* — AND/OR/NOT combination of geometric boundaries.
8. **Standards Compliance** *(Planned)* — GatingML 2.0 interoperability.

---

## Phase 9 — High-Performance Pipeline Optimization [PLANNED]

**Goal**: Ensure sub-millisecond rendering latency for datasets exceeding 10M events and handle heavy iterative algorithms without UI freezing.

1. **GIL-Free Multiprocessing for Heavy Algorithms** — Adopt a raw subprocess/GIL-free architecture for heavy matrix operations (e.g., PyNNDescent, HDBSCAN, FlowSOM) to avoid starving the main UI thread, utilizing temporary disk serialization for IPC.
2. **Multi-threaded Density Algorithms** — Delegate hexbin/KDE computations to the `TaskScheduler`.
3. **Subplot Coordinate Caching** — Persist grid calculations to accelerate UI redraws.
4. **Hardware Acceleration** — Investigate GPU compute shaders for real-time density rendering.
