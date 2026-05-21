# Advanced Analysis Guide

This manual covers advanced analytical workflows, including metadata role management, algorithmic compensation matrix generation, and high-fidelity rendering configurations for publication.

## 1. Experimental Metadata Management

### Sample Roles
By default, newly parsed datasets are assigned the generic role of `Other`. To enable algorithmic workflows, strict taxonomic roles must be assigned:
1. Select a sample node within the **Sample Tree**.
2. Within the **Properties Panel** (right), assign one of the following roles:
   - **Unstained Control**: Utilized for autofluorescence baseline calculation.
   - **Single Stain**: Utilized to compute the orthogonal spillover matrix.
   - **FMO Control**: Fluorescence Minus One; utilized for algorithmic boundary detection.
   - **Full Panel / Test**: The primary biological experimental samples.

### Dataset Grouping 
Employ Groups to systematically organize longitudinal or multi-patient experimental cohorts. Select **Create Group** within the Workspace Ribbon, and subsequently drag targeted samples into the newly instantiated group node.

---

## 2. Automated Spectral Compensation

Spectral compensation mathematically eliminates signal bleed-through resulting from overlapping fluorophore emission spectra.

### Matrix Computation
1. Ensure all single-stain algorithmic controls are tagged with the `Single Stain` role.
2. Navigate to the **Compensation** ribbon tab.
3. Select **Calculate Matrix**.
4. The computational engine automatically identifies the primary fluorescence channel for each control and derives the $N \times N$ spillover matrix via linear algebra.

### Matrix Application
Matrix computation does not destructively alter the raw event data. To project the inverted matrix onto your datasets, select **Apply to All**. The coordinate space and visual plots will refresh synchronously.

---

## 3. Advanced Geometric Gating

Beyond orthogonal rectangles, the module supports complex geometric constraints:

- **Polygon**: Sequentially click to define vertices; double-click to finalize the polygon. Optimal for isolating non-standard morphological populations (e.g., specific myeloid subsets).
- **Ellipse**: Click and drag to instantiate an elliptical region. Computationally optimal for isolating tightly clustered populations distributed across logarithmic coordinate spaces.
- **Quadrant**: Instantiate a bifurcating origin point to divide the coordinate space into four distinct regions (e.g., $CD4^+/CD8^-$, $CD4^-/CD8^+$, etc.).

### Hierarchical Management
Gating logic is strictly hierarchical. Selecting a child gate within the **Sample Tree** filters the downstream analysis pipeline to only process events satisfying that geometric constraint. This mechanism permits "gating down" to low-frequency cell types (e.g., *Lymphocytes → T Cells → CD4+ T Cells*).

---

## 4. Visualization & Rendering Architecture

BioPro provides a robust configuration system to refine the visual aesthetics of the analytical coordinate space. Access these controls via the **Settings** action on the graph toolbar.

### The Configuration Dialog
This non-modal interface permits real-time parameter tuning:

- **Point Size & Opacity**: Modulate geometric marker size and alpha-transparency to emulate the high-density aesthetic characteristic of classical flow cytometry platforms.
- **Population Detail (Bins)**: Dictates the matrix resolution of the underlying hexbin grid. High detail is optimal for vector export; low detail accelerates real-time exploratory panning.
- **Smoothing (Sigma)**: Modulates the standard deviation of the Gaussian kernel applied to population densities, generating smoother, continuous distribution clouds.
- **Background Suppression**: A noise-floor threshold that maps low-density scatter to a pure baseline color, enhancing the signal-to-noise ratio at population boundaries.

### Standardization Presets
To maintain cross-experiment consistency, utilize the parameterized presets:
- **Standard**: Computationally balanced for routine exploratory analysis.
- **Publication**: Maximized resolution and kernel smoothing optimized for manuscript-ready vector figures.
- **Fast Preview**: Aggressive matrix subsampling optimized for real-time responsiveness on datasets exceeding 10M events.

### Global vs. Local Configuration
By default, mutating configurations within the dialog applies the new `RenderConfig` globally to **all instantiated plots**, ensuring visual conformity across the entire workspace.

---

## Technical Guides
- **[Getting Started Guide](./01_GETTING_STARTED.md)**
- **[Scientific Logic & Algorithms](./03_SCIENTIFIC_LOGIC.md)**: The mathematical foundation behind rank-percentile density normalization.
