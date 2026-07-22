# Implementation Plan: Phase 2 Decompose Monoliths & Services

The goal of Phase 2 is to decompose our largest and most risky monolithic classes (e.g., `PopulationAnalysisViewer`, `FlowCanvas`, `WorkspaceIOHandler`, `GateCoordinator`, `FlowCytometryPanel`) into smaller, single-responsibility components. This will significantly improve maintainability, reduce the risk of regressions, and make unit testing easier.

## User Review Required

> [!WARNING]
> This phase touches the core rendering canvas (`FlowCanvas`), the main workflow orchestration (`GateCoordinator`), and the primary UI entry point (`FlowCytometryPanel`). Extensive UI testing will be required after these changes to ensure that event flow and rendering behave exactly as before.

## Open Questions

> [!IMPORTANT]
> **Q1**: For `PopulationAnalysisViewer` (1301 lines), the plan proposes splitting it into a pure container (`PopulationAnalysisViewer`), a control panel (`PopulationAnalysisControlPanel` for parameters/history), and a results view. Is this split consistent with how other large plugins in BioPro are structured?

> [!IMPORTANT]
> **Q2**: Should `WorkspaceIOHandler`'s raw serialization logic be moved into `analysis/services/workspace_serializer.py` (making it a domain service) or kept under `ui/services/`? Moving it to `analysis/services/` would require removing any Qt file dialogs and only passing plain file paths to it.

## Proposed Changes

---

### UI Components

#### [MODIFY] [population_analysis_viewer.py](file:///Users/kalaimaranbalasothy/GitHub%20Projects/BioPro-flow-cytometry/ui/widgets/population_analysis_viewer.py)
- **Current State:** 1301 lines of mixed layout, parameter controls, history management, and background worker orchestration.
- **Changes:** Extract the control panel (sidebar) logic, and the history combobox interaction into dedicated widgets (e.g., `PopulationAnalysisControlPanel`). The main viewer will remain as the orchestrator/container but its size should drop by >50%.

#### [MODIFY] [flow_canvas.py](file:///Users/kalaimaranbalasothy/GitHub%20Projects/BioPro-flow-cytometry/ui/graph/flow_canvas.py)
- **Current State:** 851 lines mixing PyQt input event handling (`mousePressEvent`, `paintEvent`) and Matplotlib rendering (`scatter`, `contour`).
- **Changes:** Extract the raw Matplotlib logic into a new `CanvasRenderer` class. `FlowCanvas` will delegate to `CanvasRenderer.draw_scatter()`, `CanvasRenderer.draw_gates()`, etc., focusing purely on being the Qt host and handling mouse input.

#### [MODIFY] [main_panel.py](file:///Users/kalaimaranbalasothy/GitHub%20Projects/BioPro-flow-cytometry/ui/main_panel.py)
- **Current State:** 907 lines handling the main layout, toolbars, event subscription, plugin lifecycle, and tab state.
- **Changes:** Extract the toolbar instantiation and action wiring into a dedicated `MainToolbarController` or `WorkspaceToolbar` class.

---

### Services & Domain Layer

#### [MODIFY] [workspace_io_handler.py](file:///Users/kalaimaranbalasothy/GitHub%20Projects/BioPro-flow-cytometry/ui/services/workspace_io_handler.py)
- **Current State:** Mixes `QFileDialog` prompts with `AnalysisWorker` task creation and heavy JSON serialization logic.
- **Changes:** Extract the JSON serialization and deserialization payload construction into a pure Python class `WorkspaceSerializer`. The `WorkspaceIOHandler` will only handle the UI prompts and background task lifecycle, delegating the actual data payload extraction to the serializer.

#### [MODIFY] [gate_coordinator.py](file:///Users/kalaimaranbalasothy/GitHub%20Projects/BioPro-flow-cytometry/analysis/gate_coordinator.py)
- **Current State:** Handles gating logic (add/remove/modify) but also manually invokes `AnalysisWorker` tasks to recompute statistics (`recompute_all_stats`, `_on_stats_finished`).
- **Changes:** Delegate statistics computation to the `StatisticsService` (`stats_service.py`), keeping `GateCoordinator` purely focused on the gating tree structure and propagation.

## Verification Plan

### Automated Tests
- Run `uv run pytest tests/unit/ tests/functional/ -v` to ensure that breaking the monoliths did not break the public API of the classes, especially for `FlowCanvas` and `GateCoordinator`.
- Run `uv run ruff check` to ensure no linting regressions occur.

### Manual Verification
- **Graphing**: Open a dataset, draw a polygon gate on `FlowCanvas`, and confirm rendering is still perfectly aligned and interactive.
- **Saving/Loading**: Save a workspace and load it back. Verify that all gates, clusters, and populations are correctly restored (validating the new `WorkspaceSerializer`).
- **Population Analysis**: Run a UMAP or HDBSCAN job in the Population Analysis tab to confirm background tasks still complete successfully and display results.
