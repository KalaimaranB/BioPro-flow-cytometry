# Workspace Ribbon Guide

The **Workspace Ribbon** is the foundational control center for your analytical session in BioPro. It provides all the necessary tools to manage datasets, configure experimental metadata, and organize your analytical hierarchy before diving into computational tasks.

## 1. Experimental Metadata Management

Properly configuring your datasets is critical, as algorithmic workflows (like automated compensation and UMAP) rely heavily on accurate metadata.

### Sample Roles
By default, newly parsed datasets are assigned the generic role of `Other`. To enable algorithmic workflows, strict taxonomic roles must be assigned:
1. Select a sample node within the **Sample Tree** (left panel).
2. Within the **Properties Panel** (right), locate the **Role** dropdown and assign one of the following:
   - **Unstained Control**: Utilized for autofluorescence baseline calculation.
   - **Single Stain**: Utilized to compute the orthogonal spillover matrix during compensation.
   - **FMO Control**: Fluorescence Minus One; utilized for algorithmic boundary detection and objective gating.
   - **Full Panel / Test**: The primary biological experimental samples.

### Dataset Grouping
For longitudinal studies or multi-patient experimental cohorts, it is essential to organize samples systematically:
1. Select **Create Group** within the Workspace Ribbon.
2. Drag and drop targeted samples from the Sample Tree into the newly instantiated group node.
3. Groups can be processed collectively in downstream analysis pipelines.

## 2. Global Visualization Settings

The Workspace Ribbon provides global configurations to refine the visual aesthetics of the analytical coordinate space across all instantiated plots.

### The Configuration Dialog
Access the settings menu to perform real-time parameter tuning:
- **Point Size & Opacity**: Modulate geometric marker size and alpha-transparency to emulate the high-density aesthetic characteristic of classical flow cytometry platforms.
- **Population Detail (Bins)**: Dictates the matrix resolution of the underlying hexbin grid. High detail is optimal for vector export; low detail accelerates real-time exploratory panning.
- **Smoothing (Sigma)**: Modulates the standard deviation of the Gaussian kernel applied to population densities, generating smoother, continuous distribution clouds.
- **Background Suppression**: A noise-floor threshold that maps low-density scatter to a pure baseline color, enhancing the signal-to-noise ratio at population boundaries.

### Standardization Presets
To maintain cross-experiment consistency, utilize the parameterized presets:
- **Standard**: Computationally balanced for routine exploratory analysis.
- **Publication**: Maximized resolution and kernel smoothing optimized for manuscript-ready vector figures.
- **Fast Preview**: Aggressive matrix subsampling optimized for real-time responsiveness on datasets exceeding 10M events.

> [!TIP]
> By default, mutating configurations within the dialog applies the new settings globally to **all instantiated plots**, ensuring visual conformity across the entire workspace.
