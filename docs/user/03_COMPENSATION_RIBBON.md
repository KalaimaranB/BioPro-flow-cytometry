# Compensation Ribbon Guide

Spectral compensation computationally isolates target fluorophore emissions by mathematically eliminating signal bleed-through from overlapping spectral signatures. The **Compensation Ribbon** provides a robust, algorithm-driven environment for generating, reviewing, and applying these high-dimensional spillover matrices.

## 1. Prerequisites: Control Configuration

Before computation, strict taxonomic roles must be assigned to your control samples within the Workspace Properties Panel:
1. **Unstained Control**: Serves as the autofluorescence baseline for the experimental matrix.
2. **Single Stain**: Mono-color controls (e.g., beads or cells stained with a single fluorophore). 

The computational engine automatically scans all designated `Single Stain` samples, identifies the primary emission channel exhibiting the highest intensity variance, and maps it to the respective fluorophore. This minimizes manual channel-assignment errors.

## 2. Matrix Computation

Once your controls are correctly assigned:
1. Navigate to the **Compensation** ribbon tab.
2. Select **Calculate Matrix**.
3. The module computes the orthogonal $N \times N$ spillover matrix via linear algebra, deriving compensation coefficients across all detected channels. 
4. The generated matrix is displayed within the workspace for review. Analysts can inspect off-diagonal coefficients for excessive spectral overlap.

> [!WARNING]
> High spillover values (typically $>50\%$) indicate severe spectral overlap, which may compromise population resolution. If you observe excessive values, consider redesigning your panel or referencing the **Spectral Ribbon** to analyze the physical overlaps.

## 3. Non-Destructive Application

Matrix computation does not destructively alter the raw `.fcs` event data. 
- To project the inverted compensation matrix onto your biological datasets, select **Apply to All**. 
- The system immediately recalculates the coordinate space, and all active visualizations will synchronously refresh to reflect the compensated geometry.

## 4. Matrix Export

Once verified, the calculated compensation matrix can be exported in standardized formats (e.g., CSV) for use in downstream pipelines or for documentation in publications.
