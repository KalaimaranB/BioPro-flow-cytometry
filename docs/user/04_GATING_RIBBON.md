# Gating Ribbon Guide

Gating is the fundamental process of defining sub-populations within your flow cytometry data. The **Gating Ribbon** provides access to a suite of advanced geometric gating tools that go far beyond standard orthogonal rectangles.

## 1. Advanced Geometric Gating

BioPro supports complex geometric constraints tailored to isolate distinct cellular morphologies and fluorescent phenotypes:

- **Polygon**: Sequentially click to define vertices on the plot; double-click to finalize the polygon. Optimal for isolating non-standard morphological populations (e.g., specific myeloid subsets) that do not fit into rigid squares.
- **Ellipse**: Click and drag to instantiate an elliptical region. Computationally optimal for isolating tightly clustered populations distributed across logarithmic coordinate spaces, especially where variance is normally distributed in both dimensions.
- **Quadrant**: Instantiate a bifurcating origin point to divide the coordinate space into four distinct regions (e.g., $CD4^+/CD8^-$, $CD4^-/CD8^+$, $CD4^+/CD8^+$, and $CD4^-/CD8^-$).

## 2. Navigating the Sample Tree

Once a geometric gate is drawn on a plot, it defines a new mathematical subset of the parent data.
- **Child Populations**: Selecting a child gate within the **Sample Tree** (left panel) will actively filter downstream events. Any plots instantiated from that node will only display the gated sub-population.
- **Hierarchical Structuring**: By sequentially drawing gates on child populations, you build a structural hierarchy of your data. 

> [!TIP]
> While spatial gating is powerful, biological logic often requires more than simple spatial overlap. To incorporate boolean logic (AND, OR, NOT) or to merge populations from different spatial hierarchies, utilize the **Pipeline Ribbon**.
