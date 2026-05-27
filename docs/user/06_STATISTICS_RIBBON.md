# Statistics Ribbon Guide

The **Statistics Ribbon** provides the necessary tools for quantifying and analyzing the properties of your identified populations. It is the bridge between qualitative visualization and quantitative reporting.

## 1. Population Metrics

Once you have established your gating hierarchy (via the Gating and Pipeline ribbons), you can extract numerical statistics for any defined node:
- **Event Count**: The absolute number of events within the selected gate.
- **Frequency**: The relative percentage of events compared to the immediate parent population or the total sample.
- **Central Tendency**: Median Fluorescence Intensity (MFI) and Arithmetic Mean for all active fluorescent channels.
- **Dispersion**: Coefficient of Variation (CV) and Robust Coefficient of Variation (rCV) to assess population spread.

## 2. Generating Statistical Reports

The Statistics Ribbon allows you to compile these metrics into comprehensive views:
1. Select the populations and channels of interest.
2. Generate a tabular summary directly within the application.
3. Compare MFIs across different experimental conditions or sample groups to evaluate biological shifts (e.g., activation marker upregulation).

## 3. Data Export

For downstream statistical analysis (e.g., in Python, R, or GraphPad Prism):
- Use the **Export** functionality to save your generated statistics as standardized CSV files.
- You can export metrics for a single sample or execute batch exports across entire sample groups configured in the Workspace Ribbon.
