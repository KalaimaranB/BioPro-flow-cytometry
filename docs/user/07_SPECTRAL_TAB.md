# Spectral Tab Guide

The **Spectral Tab** houses the Spectral Viewer, an advanced full-screen analytical interface designed to overlay and evaluate the physical emission and excitation spectra of fluorophores. To maximize viewing space for the spectral plots, this module operates independently of the main workspace ribbon.

## 1. FPbase Integration

The Spectral Viewer is seamlessly integrated with the comprehensive FPbase database:
- **Live Search**: Use the search bar to find and add fluorescent proteins or organic dyes to the viewer. The autocomplete functionality helps resolve common naming discrepancies.
- **Distinct Colors**: To prevent confusion from overlapping default colors, the viewer automatically assigns visually distinct colors (using a 20-color palette) to every newly added fluorophore.
- **Metadata Chips**: Active spectra are displayed with Quantum Yield (QY) and Extinction Coefficient (EC) metadata to help you evaluate the absolute brightness of a fluorophore.

## 2. Spectral Overlap Evaluation

Evaluating spectral overlap before running experiments or calculating compensation matrices is critical for robust panel design.
- **Toggle Views**: Independently toggle Absorbance (AB), Excitation (EX), and Emission (EM) curves for the selected fluorophores.
- **Overlap Visualization**: When multiple emission curves are active, the viewer automatically highlights regions of spectral overlap with hatched shading.

## 3. Educational Wizard: What is Compensation?

The Spectral module includes a dedicated educational tab named **"Learning: What is Compensation?"** which walks users through the math and concepts behind flow cytometry compensation.
- **8-Step Interactive Tutorial**: Breaks down complex mathematics using visual simulations of single-positive and double-positive cell populations.
- **The Golden Rule of Panel Design**: An explicitly documented warning within the wizard that while compensation can subtract average leakage, heavy overlap still causes "Spreading Error" (noise). *Exception*: Highly overlapping dyes can be placed on mutually exclusive markers.

## 4. Real-Time Interactions

- **Drag and Drop Context**: You can drag available channels directly from your loaded sample's channel list onto the plot. The full marker name (e.g., "CD4 (PE)") is dynamically extracted and applied to the plot legends and compensation matrix headers to maintain experimental context.
- **Interactive Callouts**: The dynamic callouts highlighting spectral overlaps can be clicked to temporarily dismiss them, allowing for an unobstructed view of the spectral curves.
