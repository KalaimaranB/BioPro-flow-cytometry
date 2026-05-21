# Getting Started with BioPro Flow Cytometry

This guide outlines the procedural steps to initialize an analysis session, from loading Flow Cytometry Standard (FCS) data to establishing hierarchical gating populations.

## 1. Topographical Layout

The graphical interface is structurally divided into three functional zones designed to mirror standard analytical workflows:

### A. The Context Ribbon (Top)
Organized functionally into context-aware tabs:
- **Workspace**: Global session actions, including dataset loading, condition grouping, and template exportation.
- **Compensation**: Algorithmic tools for generating, importing, and applying mathematical spillover matrices.
- **Gating**: Geometric isolation tools for delineating cellular subpopulations.

### B. The Operations Sidebar (Left)
- **Groups Panel**: Filter data visualizations by experimental condition (e.g., *Stimulated* vs. *Control*).
- **Sample Tree**: The core hierarchical state viewer. It displays all parsed files and their cascaded gate populations. Double-clicking a node invokes it onto the primary canvas.

### C. The Primary Canvas (Center)
The high-performance rendering engine. Utilizing hardware-accelerated hexbin matrices, the canvas supports real-time rendering of millions of events. 

### D. Properties & Statistics (Right)
- **Sample Properties**: Inspect cryptographic metadata, toggle axis scalars (Linear, Log, Logicle), and switch visualization modalities (e.g., Contour vs. Density).
- **Statistical Output**: Real-time evaluation of quantitative metrics (MFI, CV, % Parent, Event Counts) for the actively selected population node.

---

## 2. Initializing an Analysis

### Step 1: Loading FCS Data
1. Navigate to the **Workspace** tab in the Context Ribbon.
2. Click **Add Samples** to invoke the file parser.
3. Select the desired `.fcs` files. The parser natively handles FCS versions 2.0, 3.0, and 3.1.

> [!IMPORTANT]
> To ensure your analysis session remains fully portable and reproducible across different computational environments, we strongly recommend copying your `.fcs` files into your project's local `assets/` directory when prompted by the parser.

### Step 2: Visualization Deployment
Double-click any sample node within the **Sample Tree** (Operations Sidebar). The primary canvas will instantiate the rendering pipeline using default scattering parameters (typically FSC-A vs. SSC-A).

### Step 3: Parameter Selection
Configure the visualization axes using the parameter selectors located at the bottom (X-axis) and left (Y-axis) of the canvas.
- The selectors intelligently display both the **Detector Name** (e.g., *FITC-A*) and the associated **Biological Marker** (e.g., *CD4*), simplifying channel navigation in highly multiplexed panels.

### Step 4: Delineating a Subpopulation (Gating)
1. Select the **Gating** tab in the Context Ribbon.
2. Choose the appropriate geometric constraint tool (e.g., **Rectangle** or **Polygon**).
3. Click and drag across the canonical region of interest (e.g., the Lymphocyte morphological cluster).
4. Assign a strict taxonomic name to the population when prompted (e.g., "Lymphocytes").
5. The newly established constraint will immediately populate as a child node beneath the parent sample in the Sample Tree.

---

## 3. Operational Heuristics

> [!TIP]
> - **Rapid Export**: Right-click a node in the Sample Tree to synchronously export its statistical matrix to a CSV file.
> - **Dynamic Scaling**: Utilize the Mouse Scroll Wheel to dynamically zoom and translate across the coordinate space.
> - **Outlier Detection**: Toggle between *Pseudocolor* (density-focused) and *Dot Plot* (scatter-focused) in the Properties panel to evaluate low-frequency events.

---

## Next Steps

To progress beyond morphological gating, please consult the specialized analytical guides:
- **[Deep Dive: Compensation & Advanced Gating](./02_ANALYSIS_GUIDE.md)**
- **[Scientific Principles of Scaling](./03_SCIENTIFIC_LOGIC.md)**
