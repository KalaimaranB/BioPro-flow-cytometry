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

## 2. Automated Spectral Compensation (Spectral Tab)

Spectral compensation computationally isolates target fluorophore emissions by mathematically eliminating signal bleed-through from overlapping spectral signatures. The **Spectral** tab provides a robust, algorithm-driven environment for generating and projecting these high-dimensional spillover matrices.

### Control Configuration & Algorithmic Discovery
Before computation, strict taxonomic roles must be assigned within the Properties Panel:
1. **Unstained Control**: Serves as the autofluorescence baseline for the experimental matrix.
2. **Single Stain**: Mono-color controls (e.g., beads or cells stained with a single fluorophore). 

The computational engine automatically scans all designated `Single Stain` samples, identifies the primary emission channel exhibiting the highest intensity variance, and maps it to the respective fluorophore, minimizing manual channel-assignment errors.

### Matrix Computation
1. Navigate to the **Spectral** ribbon tab.
2. Select **Calculate Matrix**.
3. The module computes the orthogonal $N \times N$ spillover matrix via linear algebra, deriving compensation coefficients across all detected channels. 
4. The generated matrix is displayed within the Spectral workspace for review. Analysts can inspect off-diagonal coefficients for excessive spectral overlap.

### Non-Destructive Application
Matrix computation does not destructively alter the raw `.fcs` event data. To project the inverted compensation matrix onto your biological datasets, select **Apply to All**. The system immediately recalculates the coordinate space, and all active visualizations will synchronously refresh to reflect the compensated geometry.

---

## 3. Advanced Geometric Gating

Beyond orthogonal rectangles, the module supports complex geometric constraints:

- **Polygon**: Sequentially click to define vertices; double-click to finalize the polygon. Optimal for isolating non-standard morphological populations (e.g., specific myeloid subsets).
- **Ellipse**: Click and drag to instantiate an elliptical region. Computationally optimal for isolating tightly clustered populations distributed across logarithmic coordinate spaces.
- **Quadrant**: Instantiate a bifurcating origin point to divide the coordinate space into four distinct regions (e.g., $CD4^+/CD8^-$, $CD4^-/CD8^+$, etc.).

### Hierarchical Management
Gating logic is structured as a Directed Acyclic Graph (DAG). While you can still select a child gate within the **Sample Tree** to filter downstream events, the real power comes from the **Pipeline Canvas**.

---

## 4. The Node-Based Gating Pipeline

BioPro now features an advanced visual node-based pipeline for constructing complex gating strategies, including multi-parent Boolean logic.

### Accessing the Pipeline
1. Navigate to the **Pipeline** ribbon tab.
2. The central workspace will switch to the infinite **Node Canvas**.
3. Use the **Pan Tool** (or click and drag with the middle mouse button) to navigate the workspace. Use the zoom controls or press `F` to auto-fit the view to your nodes.

### Logic Nodes
Instead of purely spatial geometric gates, you can incorporate mathematical boolean logic:
- **AND Gate**: Yields the intersection of multiple parent populations.
- **OR Gate**: Yields the union of multiple parent populations.
- **NOT Gate**: Yields the inverse of a single parent population.

To add a logic node, simply click the corresponding button in the Pipeline ribbon.

### Wiring and DAG Architecture
Because the gating system uses a Directed Acyclic Graph (DAG), populations can have multiple parents (essential for complex logic):
1. **Connect**: Click and drag from the output port of a parent node to the input port of a child or logic node.
2. **Disconnect**: Click on any wire connecting two nodes (it will highlight in blue) and press the `Delete` or `Backspace` key to sever the connection.
3. **Double-Click**: Double-clicking any node in the pipeline will instantly flip the workspace back to the spatial graph view for that specific population, allowing you to seamlessly switch between structural architecture and spatial refinement.

---

## 5. Visualization & Rendering Architecture

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

## 6. UMAP Dimensionality Reduction (UMAP Tab)

Uniform Manifold Approximation and Projection (UMAP) is a non-linear dimensionality reduction algorithm. The **UMAP** tab allows researchers to project high-dimensional marker data into a 2D coordinate space, effectively mapping continuous biological gradients and identifying discrete phenotypic sub-populations without manual gating.

### Pro-Mode Algorithm Parameters
Access the advanced configuration suite by toggling **Pro** mode on the left panel:
- **Nearest Neighbors ($K$)**: Controls the balance between local and global structure. Lower values (e.g., 5-10) fracture continuous populations into distinct local micro-clusters. Higher values (e.g., 30-50) preserve broader, global phenotypic relationships.
- **Minimum Distance**: Dictates the spatial compression of the final layout. Lower values tightly pack similar cells, emphasizing distinct "island" boundaries.
- **Subsample Events**: UMAP is computationally intensive. Subsampling (e.g., 10,000 to 100,000 events) guarantees interactive performance while retaining sufficient statistical power to represent the manifold.

### The Educational Algorithm Animation
When a UMAP execution is triggered, BioPro renders a real-time, 20-second educational animation demonstrating the algorithm's mathematical progression. This visual walkthrough includes:
1. High-dimensional feature mapping.
2. Construction of the topological $K$-nearest neighbor (KNN) fuzzy graph.
3. The force-directed optimization loop pulling connected nodes together and repelling disjointed nodes into the final 2D islands.

*Note: The animation operates on a lightweight 1,200-event subset to maintain a 30fps visual framerate, while the full analytical algorithm concurrently resolves up to 100,000 events in an isolated background process.*

### Scientific Rationale: PCA Initialization
By default, standard UMAP implementations rely on spectral initialization. However, spectral methods are highly susceptible to graph bottlenecks, often artificially fracturing continuous biological gradients (e.g., B-cell maturation or T-cell activation) into disjointed artifacts. Furthermore, spectral initialization introduces macro-rotational instability between independent algorithmic runs.

To ensure rigorous scientific reproducibility, BioPro explicitly forces **PCA Initialization** (`init="pca"`) for all UMAP projections. This linear prior guarantees that:
1. **Macro-Structure is Preserved:** The global orientation of the manifold remains mathematically stable across varying sample sizes and multiple experimental runs.
2. **Biological Continuums are Maintained:** Continuous phenotypic gradients correctly render as cohesive, stretched manifolds rather than artificial, fractured clusters.

---

## Technical Guides
- **[Getting Started Guide](./01_GETTING_STARTED.md)**
- **[Scientific Logic & Algorithms](./03_SCIENTIFIC_LOGIC.md)**: The mathematical foundation behind rank-percentile density normalization.
