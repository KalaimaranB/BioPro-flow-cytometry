# Developer Guide — UI Engine & Render Architecture

This technical specification details the internal architecture of the `FlowCanvas`, its interaction Finite State Machine (FSM), and the asynchronous multi-threaded rendering pipeline.

## 1. The `FlowCanvas` Finite State Machine

To robustly manage complex mouse interactions (e.g., drawing polygon vertices, translating gating geometry, defining zoom boundaries) without relying on brittle nested conditional logic, the `FlowCanvas` implements a strict internal state machine governed by the `CanvasState` enumeration.

### Interaction States
- `IDLE`: The default quiescent state. Cursor movement invokes non-mutating nearest-neighbor evaluations to highlight proximal geometries.
- `DRAW_RECT` / `DRAW_ELLIPSE`: Active, continuous click-and-drag evaluation for boundary definition.
- `DRAW_POLY`: Sequential, discrete vertex placement for the construction of arbitrary n-gons.
- `MOVE_GATE`: Real-time coordinate translation of an instantiated boundary or centroid.
- `ZOOM`: Rubber-band spatial definition for axis coordinate limitation.

### Event Orchestration
State transitions are strictly managed by the tri-part handler system: `_on_mouse_press`, `_on_mouse_move`, and `_on_mouse_release`. State-specific transient overlays (such as the dashed architectural lines of an incomplete polygon) are dynamically rendered via the `_render_overlay_layer` method.

---

## 2. Rendering Pipeline Architecture

The module employs a multi-layered rendering architecture to guarantee 60 FPS user interactivity, even when projecting datasets exceeding millions of events.

### Layered Rendering (SOLID Principles)
Following a comprehensive architectural refactor, the `FlowCanvas` class no longer manages direct rendering logic. Rather, responsibility is delegated to specialized abstraction layers:

1. **Data Layer (`DataLayerRenderer`)**: Responsible for intensive event projection (Pseudocolor density, KDE, Histogram). It asynchronously coordinates with the background `RenderTask` to execute numerical matrix transformations.
2. **Gate Layer (`GateLayerRenderer`)**: Explicitly manages the spatial life-cycle of gate geometries (`matplotlib.patches`) and topological labels.
3. **Event Handler (`CanvasEventHandler`)**: Orchestrates human-computer interaction inputs and drives the aforementioned FSM.

---

## 3. Parameterized Visualization Configuration

The module exposes a dynamic, non-modal **Render Settings** system to enable real-time aesthetic tuning without occluding the primary canvas workspace.

### Context-Sensitive Dispatching
The `RenderSettingsDialog` implements a factory pattern to dynamically instantiate interface panels based on the active `DisplayMode` state:
- `PseudocolorSettingsPanel`: Exposes parameters for rank-percentile density calculation, geometric point size, and Gaussian kernel variance.
- `HistogramSettingsPanel`: Modulates binning algorithms and KDE bandwidth.
- `DotPlotSettingsPanel`: Provides explicit scatter geometry and alpha controls.

### Preset Parameterization
The interface incorporates standard high-level presets (**Standard**, **Publication**, **Fast Preview**) which bundle disparate mathematical parameters (e.g., smoothing sigma, grid detail, outlier rejection) to rapidly deploy validated aesthetic standards.

---

## Technical Guides
- **[Architecture & Design Principles](./00_ARCHITECTURE_OVERVIEW.md)**
- **[API Reference](./01_API_REFERENCE.md)**
- **[Testing & Quality Assurance](./03_TESTING_AND_QA.md)**
