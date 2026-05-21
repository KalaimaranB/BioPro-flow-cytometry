# Flow Cytometry Module — Overview

Welcome to the **BioPro Flow Cytometry Module**, a high-performance analytical suite designed to satisfy the rigorous demands of modern immunology and cell biology.

This module provides a robust bridge between raw instrument data and publication-ready statistical insights, merging the speed of hardware-accelerated rendering with the precision of mathematically validated gating algorithms.

## Core Capabilities

- **Massive Scale Integration**: Process datasets encompassing millions of events without UI latency, utilizing our optimized hexbin density matrix engine.
- **Mathematical Rigor**: Native integration of the **Parks 2006 Logicle Transform**, ensuring algorithmically sound visualization of compensated spectral data and sub-zero populations.
- **Hierarchical Geometry**: Construct complex, nested gating strategies using Rectangle, Polygon, Ellipse, and Quadrant geometric constraints.
- **Automated Spectral Compensation**: Derive spillover matrices directly from single-stain algorithmic controls, or extract embedded matrix permutations directly from FCS binary metadata.
- **Publication-Ready Export**: Export high-resolution (300 DPI) bitmaps or lossless vector-based (PDF/SVG) figures dynamically.

## Targeted Audiences

### For Scientists & Researchers
Researchers focused on data analysis, population quantification, and figure generation should begin with the **[Getting Started Guide](./01_GETTING_STARTED.md)**.
- Learn robust methodologies for data loading and marker mapping.
- Master algorithmic compensation and geometric gating tools.
- Comprehend the scientific logic and mathematical principles governing our coordinate transformations.

### For Developers & Engineers
Engineers tasked with extending the module, integrating novel algorithms, or analyzing the underlying state machine should consult the **[Architecture Overview](../developer/00_ARCHITECTURE_OVERVIEW.md)**.
- Explore the unidirectional `FlowState` architecture and BioPro Core lifecycle integration.
- Analyze the Finite State Machine (FSM) driven rendering engine.
- Reference the API definitions for custom logic extensions.

---

## Technical Guides
- **[Getting Started Guide](./01_GETTING_STARTED.md)**
- **[Full Analysis Guide](./02_ANALYSIS_GUIDE.md)**
- **[Technical Architecture](../developer/00_ARCHITECTURE_OVERVIEW.md)**
