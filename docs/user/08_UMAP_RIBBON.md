# UMAP Ribbon Guide

Uniform Manifold Approximation and Projection (UMAP) is a state-of-the-art, non-linear dimensionality reduction algorithm. The **UMAP Ribbon** allows researchers to project high-dimensional marker data into a 2D coordinate space, effectively mapping continuous biological gradients and identifying discrete phenotypic sub-populations without the bias of manual gating.

## 1. Algorithm Parameters

Access the advanced configuration suite within the UMAP viewer:

- **Nearest Neighbors ($K$)**: Controls the balance between local and global structure. Lower values (e.g., 5-10) fracture continuous populations into distinct local micro-clusters. Higher values (e.g., 30-50) preserve broader, global phenotypic relationships.
- **Minimum Distance**: Dictates the spatial compression of the final layout. Lower values tightly pack similar cells, emphasizing distinct "island" boundaries.
- **Subsample Events**: UMAP is computationally intensive. The interactive slider allows you to subsample a percentage of your events (e.g., 10%) to guarantee interactive performance while retaining sufficient statistical power to represent the manifold.
- **Channel Selection**: Explicitly select which fluorescence channels are fed into the dimensionality reduction. Exclude viability or dump channels to ensure the resulting topology is purely phenotype-driven.

## 2. Interactive Run History

The **Run History** dropdown in the UMAP ribbon tracks multiple UMAP executions.
- **Persistent State**: Each run preserves its unique parameter combination ($K$, minimum distance) and the generated 2D embedding.
- **Gate Context**: Run histories are mapped directly to the specific sample and gate they were executed on. This allows you to maintain separate, parallel UMAP histories for different sub-populations.

## 3. Scientific Rationale: PCA Initialization

By default, standard UMAP implementations rely on spectral initialization. However, spectral methods are highly susceptible to graph bottlenecks, often artificially fracturing continuous biological gradients (e.g., B-cell maturation or T-cell activation) into disjointed artifacts.

To ensure rigorous scientific reproducibility, BioPro explicitly forces **PCA Initialization** for all UMAP projections. This linear prior guarantees that:
1. **Macro-Structure is Preserved**: The global orientation of the manifold remains mathematically stable across varying sample sizes and multiple experimental runs.
2. **Biological Continuums are Maintained**: Continuous phenotypic gradients correctly render as cohesive, stretched manifolds rather than artificial, fractured clusters.

## 4. The Educational Algorithm Animation

When a UMAP execution is triggered, BioPro renders a real-time educational animation demonstrating the algorithm's mathematical progression:
1. High-dimensional feature mapping.
2. Construction of the topological $K$-nearest neighbor (KNN) fuzzy graph.
3. The force-directed optimization loop pulling connected nodes together and repelling disjointed nodes into the final 2D islands.

*Note: The animation operates on a lightweight subset to maintain visual fluidity, while the full analytical algorithm concurrently resolves your events in an isolated background process.*
