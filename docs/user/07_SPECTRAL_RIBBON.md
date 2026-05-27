# Spectral Ribbon Guide

The **Spectral Ribbon** houses the Spectral Viewer, an advanced analytical interface designed to overlay and evaluate the physical emission and excitation spectra of fluorophores.

## 1. FPbase Integration

The Spectral Viewer is integrated with the comprehensive FPbase database:
- **Live Search**: Use the search bar to find and add fluorescent proteins or organic dyes to the viewer. The autocomplete functionality helps resolve common naming discrepancies.
- **Metadata Chips**: Active spectra are displayed with Quantum Yield (QY) and Extinction Coefficient (EC) metadata to help you evaluate the absolute brightness of a fluorophore.

## 2. Spectral Overlap Evaluation

Evaluating spectral overlap before running experiments or calculating compensation matrices is critical for robust panel design.
- **Toggle Views**: Independently toggle Absorbance (AB), Excitation (EX), and Emission (EM) curves for the selected fluorophores.
- **Overlap Visualization**: When multiple emission curves are active, the viewer automatically highlights regions of spectral overlap with hatched shading.
- **Student vs. Pro Mode**: 
  - **Student Mode**: Provides plain-language explanations of spillover and demonstrates how compensation mathematically subtracts overlapping signals using simulated detector bands and interactive sliders.
  - **Pro Mode**: Displays rigorous numerical overlap coefficients (Bhattacharyya-style normalized integrals) to precisely quantify the degree of spectral bleed-through between two fluorophores.

## 3. Real-Time Interactions

- **Drag and Drop**: You can drag available channels directly from your loaded sample's channel list onto the plot to instantly view their spectral signatures.
- **Interactive Callouts**: The dynamic callouts highlighting spectral overlaps can be clicked to temporarily dismiss them, allowing for an unobstructed view of the spectral curves.
