# Flow Cytometry Knowledge Hub

Welcome to the centralized documentation for the BioPro Flow Cytometry module. This hub is designed to support both researchers conducting data analysis and engineers extending the software capabilities.

---

## For Scientists & Researchers
Comprehensive guides for data analysis workflows, visual refinement, and publication preparation.

- **[Capabilities Overview](./user/00_OVERVIEW.md)**: Feature summary and high-level workflow paradigm.
- **[Getting Started Guide](./user/01_GETTING_STARTED.md)**: Tutorial for loading FCS data, configuring the workspace, and creating initial gates.
- **[Analysis & Visualization](./user/02_ANALYSIS_GUIDE.md)**: In-depth manual for compensation, rendering parameters, and hierarchical gating logic.
- **[Scientific Logic & Algorithms](./user/03_SCIENTIFIC_LOGIC.md)**: Mathematical principles behind Logicle transforms, rank-percentile density calculation, and smoothing kernels.

---

## For Developers & Maintainers
Architectural specifications, API references, and contribution guidelines for the module.

- **[Architecture & Design Principles](./developer/00_ARCHITECTURE_OVERVIEW.md)**: Breakdown of the decoupled rendering layers and service-oriented backend structure.
- **[API Reference](./developer/01_API_REFERENCE.md)**: Technical documentation for Gating, Scaling, and Configuration models.
- **[UI Engine & Rendering](./developer/02_UI_ENGINE.md)**: Mechanics of the asynchronous rendering pipeline and the context-sensitive settings dispatch system.
- **[Testing & Quality Assurance](./developer/03_TESTING_AND_QA.md)**: Test suite architecture, statistical fixtures, and algorithmic verification checklists.

---

## External References
- **Parks, D.R., et al. (2006)**. A new "Logicle" display method. *Cytometry Part A*.
- **FlowKit Documentation**: [GitHub Repository](https://github.com/whitews/FlowKit)
- **Fast-Histogram**: [Optimized 2D binning implementation](https://github.com/astrofrog/fast-histogram)
