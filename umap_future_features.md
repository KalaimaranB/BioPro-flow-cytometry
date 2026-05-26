# Future UMAP Features

This document tracks high-impact features to be added to the UMAP workflow in BioPro. These features aim to bridge the gap between exploratory visualization and rigorous quantitative analysis, providing a smoother experience than existing tools.

## High-Priority Features

### 1. Back-Gating (The "Killer Feature")
*   **Target Audience:** Researchers
*   **Concept:** Allow users to draw a polygon or lasso directly on the UMAP projection to select a cluster or "island."
*   **Action:** Automatically translate this selection into a formal Gate in the main Gating workspace, tied to the original high-dimensional events.
*   **Value:** Lets researchers discover novel or unexpected populations via UMAP, and instantly quantify them or explore their phenotype in standard 2D plots without manual back-and-forth.

### 2. Auto-Clustering Integration (e.g., HDBSCAN)
*   **Target Audience:** Students & Researchers
*   **Concept:** Integrate an automated clustering algorithm that runs alongside or immediately after UMAP.
*   **Action:** Mathematically identify distinct populations and assign a "Cluster ID" to each cell. Overlay these IDs on the UMAP plot (coloring by cluster).
*   **Value:** Transforms the UMAP from a subjective "pretty picture" into an objective map of discrete populations. Students can see "there are 6 distinct groups" without guessing based on marker heatmaps.

### 3. Channel Exclusion / Selection
*   **Target Audience:** Researchers
*   **Concept:** Allow users to explicitly select which fluorescence channels are fed into the UMAP algorithm.
*   **Action:** Provide a checklist in the "Pro" settings to exclude viability dyes, scatter channels, or "dump" channels from the dimensionality reduction.
*   **Value:** Prevents dead cells or debris from driving the clustering structure, ensuring the UMAP layout is purely driven by phenotypic surface markers. *(Note: Gate selection partially addresses this by pre-filtering events, but channel exclusion is still needed to ignore the viability channel within the live cell gate).*

## Medium-Priority Enhancements

### 4. Density Contour Overlay
*   **Target Audience:** Both
*   **Concept:** Draw probability density contours over the UMAP scatter plot.
*   **Value:** Acts like a topographic map, making the structure, density peaks, and boundaries of clusters much more visually obvious, especially in crowded plots.

### 5. Per-Cluster Marker Profiling
*   **Target Audience:** Students
*   **Concept:** Interactive profiling of clusters.
*   **Action:** When a user clicks on a distinct cluster (or an auto-detected cluster), pop up a bar chart or heatmap showing the average expression of all markers for that specific cluster.
*   **Value:** Instantly answers the question, "What is this population?" by showing its defining phenotype.

### 6. Manual Annotation Labels
*   **Target Audience:** Both
*   **Concept:** Allow users to double-click on an island and type a label (e.g., "B cells", "Activated T cells").
*   **Action:** Pin the text label to that coordinate space on the plot.
*   **Value:** Crucial for presenting data and remembering interpretations when revisiting an analysis later.

### 7. Export Capabilities
*   **Target Audience:** Researchers
*   **Concept:** One-click export of the UMAP viewer.
*   **Action:** Save the current plot view as a high-resolution PDF or PNG.
*   **Value:** Necessary for generating figures for publications or lab meetings.

### Technical Architecture Notes
9. GIL-Free Multiprocessing for Heavy Algorithms
Context: Machine learning algorithms compiled with C-extensions (like PyNNDescent used in UMAP) frequently hold the Python Global Interpreter Lock (GIL) during tight loops. When executed inside a standard QThread or BioPro core scheduler thread, this completely starves the main UI thread, causing the application to freeze for seconds at a time. Furthermore, macOS spawn multiprocessing contexts cannot easily unpickle dynamic plugin functions.
Implementation: BioPro bypasses both the GIL and pickling limitations by spawning a raw subprocess.Popen executing an inline Python script. The heavy matrix data (X) and parameters are serialized to disk via numpy.save to a temporary directory, completely isolating the heavy computation.
Future Implications: Any future integration of heavy iterative algorithms (e.g., HDBSCAN, FlowSOM, or t-SNE) must adopt this identical isolated subprocess architecture. Do not attempt to run them via the standard UmapService threading model if they exhibit GIL-locking behavior.