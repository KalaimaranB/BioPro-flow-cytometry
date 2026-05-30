# Flow Cytometry Knowledge Hub

Welcome to the centralized documentation for the BioPro Flow Cytometry module. This hub is designed to support both researchers conducting data analysis and engineers extending the software capabilities.

---

## For Scientists & Researchers
Comprehensive guides for data analysis workflows, visual refinement, and publication preparation.

- **[Capabilities Overview](./user/00_OVERVIEW.md)**: Feature summary and high-level workflow paradigm.
- **[Getting Started Guide](./user/01_GETTING_STARTED.md)**: Tutorial for loading FCS data, configuring the workspace, and creating initial gates.
- **[Workspace Ribbon](./user/02_WORKSPACE_RIBBON.md)**: Guide to importing FCS files, compensation setup, and sample management.
- **[Compensation Ribbon](./user/03_COMPENSATION_RIBBON.md)**: Advanced compensation matrix management and spillover matrix generation.
- **[Scientific Logic & Algorithms](./user/03_SCIENTIFIC_LOGIC.md)**: Mathematical principles behind Logicle transforms, rank-percentile density calculation, and smoothing kernels.
- **[Gating Ribbon](./user/04_GATING_RIBBON.md)**: Using polygon, rectangle, and hierarchical gates.
- **[Pipeline Ribbon](./user/05_PIPELINE_RIBBON.md)**: Creating workflow templates for sequential sample processing.
- **[Statistics Ribbon](./user/06_STATISTICS_RIBBON.md)**: Analyzing event counts, percentages, and custom population metrics.
- **[Spectral Ribbon](./user/07_SPECTRAL_RIBBON.md)**: High-dimensional spectral unmixing tools and quality controls.
- **[UMAP Ribbon](./user/08_UMAP_RIBBON.md)**: Setting up dimensionality reduction jobs and evaluating UMAP clusters.
- **[Keyboard Shortcuts & Quick Reference](./user/09_KEYBOARD_SHORTCUTS.md)**: Complete list of keyboard shortcuts and quick access commands.
- **[Troubleshooting Guide](./user/10_TROUBLESHOOTING.md)**: Common issues, error messages, and solutions.

---

## For Developers & Maintainers
Architectural specifications, API references, and contribution guidelines for the module.

- **[Architecture & Design Principles](./developer/00_ARCHITECTURE_OVERVIEW.md)**: Breakdown of the decoupled rendering layers and service-oriented backend structure.
- **[API Reference](./developer/01_API_REFERENCE.md)**: Technical documentation for Gating, Scaling, and Configuration models.
- **[UI Engine & Rendering](./developer/02_UI_ENGINE.md)**: Mechanics of the asynchronous rendering pipeline and the context-sensitive settings dispatch system.
- **[Testing & Quality Assurance](./developer/03_TESTING_AND_QA.md)**: Test suite architecture, statistical fixtures, and algorithmic verification checklists.
- **[Services & Dependency Injection](./developer/04_SERVICES_AND_DEPENDENCY_INJECTION.md)**: Core service layer architecture and pattern integration.
- **[Gating & Compensation Deep Dive](./developer/05_GATING_AND_COMPENSATION_DEEP_DIVE.md)**: Exhaustive technical details on the gate evaluation engine and spillover matrix compensation algorithm.
- **[Transforms & Scaling Deep Dive](./developer/06_TRANSFORMS_AND_SCALING.md)**: Mathematical details on axis transformations, auto-ranging algorithms, and coordinate mapping.
- **[Rendering & Visualization Architecture](./developer/07_RENDERING_AND_VISUALIZATION.md)**: Detailed technical documentation of the asynchronous rendering pipeline and visualization algorithms.
- **[Data Flow & Signal Connections](./developer/08_DATA_FLOW_AND_SIGNAL_CONNECTIONS.md)**: Complete documentation of data flow through the system, with workflow diagrams for major user operations and signal/event routing.

---

## External References
- **Parks, D.R., et al. (2006)**. A new "Logicle" display method. *Cytometry Part A*.
- **FlowKit Documentation**: [GitHub Repository](https://github.com/whitews/FlowKit)
- **Fast-Histogram**: [Optimized 2D binning implementation](https://github.com/astrofrog/fast-histogram)
