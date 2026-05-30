# Data Flow & Signal Connections

Complete documentation of data flow through the system, with workflow diagrams for major user operations and signal/event routing.

---

## 1. Complete Data Flow Architecture

```mermaid
graph TB
    subgraph "User Interaction"
        UI["UI Controls<br/>Ribbons, Canvas, Dialogs"]
    end
    
    subgraph "Mutation Layer"
        MUTATE["State Mutation<br/>update FlowState"]
    end
    
    subgraph "Event Bus"
        EVENTS["CentralEventBus<br/>Publish Events"]
    end
    
    subgraph "Service Layer"
        SERVICES["Services<br/>React to Events"]
    end
    
    subgraph "Background Work"
        BG["Background Tasks<br/>TaskScheduler Workers"]
    end
    
    subgraph "UI Update"
        LISTEN["Event Listeners<br/>Signal/Slot"]
    end
    
    subgraph "Display"
        RENDER["Rendering<br/>matplotlib.draw()"]
    end
    
    UI -->|"user action"| MUTATE
    MUTATE -->|"publish"| EVENTS
    EVENTS -->|"subscribe"| SERVICES
    SERVICES -->|"schedule"| BG
    EVENTS -->|"connect"| LISTEN
    BG -->|"complete"| EVENTS
    LISTEN -->|"update"| RENDER
    RENDER -->|"→ Screen"| UI
    
    style MUTATE fill:#ffccbc
    style EVENTS fill:#fff9c4
    style SERVICES fill:#c8e6c9
    style BG fill:#f3e5f5
    style LISTEN fill:#b2dfdb
```

---

## 2. Major Workflows with Detailed Signal Flow

### Workflow 1: User Opens FCS File

```mermaid
graph TB
    USER["User clicks 'Open File'"]
    DIALOG["QFileDialog<br/>workspace_ribbon.py"]
    LOADER["DataLoaderService.load_fcs()"]
    FLOWKIT["flowkit.Sample.load()"]
    PARSE["FCS binary parsing<br/>channels, events, metadata"]
    FCS_DATA["Create FCSData<br/>dataclass"]
    SAMPLE["Create Sample<br/>with root GateNode"]
    ADD_EXP["Experiment.samples[id] = sample"]
    
    PUBLISH1["Publish:<br/>sample.loaded"]
    
    LISTEN1["Event Listeners"]
    SAMPLE_TREE["SampleList.add_sample()"]
    PROPERTIES["PropertiesPanel.show_sample()"]
    CANVAS["FlowCanvas.render_sample()"]
    
    RENDER["RenderTask.run()"]
    DISPLAY["Update display"]
    
    USER --> DIALOG
    DIALOG -->|"file_path"| LOADER
    LOADER --> FLOWKIT
    FLOWKIT --> PARSE
    PARSE --> FCS_DATA
    FCS_DATA --> SAMPLE
    SAMPLE --> ADD_EXP
    ADD_EXP -->|"mutation"| PUBLISH1
    PUBLISH1 --> LISTEN1
    LISTEN1 --> SAMPLE_TREE
    LISTEN1 --> PROPERTIES
    LISTEN1 --> CANVAS
    CANVAS --> RENDER
    RENDER --> DISPLAY
    
    style LOADER fill:#c8e6c9
    style FLOWKIT fill:#e0e0e0
    style PUBLISH1 fill:#fff9c4
    style LISTEN1 fill:#b2dfdb
    style RENDER fill:#f3e5f5
```

**Detailed Steps:**
1. User selects FCS file via dialog
2. `DataLoaderService.load_fcs()` invokes `flowkit.Sample.load()`
3. FlowKit parses binary FCS, extracts channels, events (pandas DataFrame)
4. Create `FCSData` wrapper
5. Create `Sample` with root "All Events" `GateNode`
6. Add to `Experiment.samples` (state mutation)
7. **Publish `sample.loaded` event** via Central Event Bus
8. Multiple listeners react:
   - `SampleList`: Add to tree widget
   - `PropertiesPanel`: Display sample properties
   - `FlowCanvas`: Schedule background render task
9. `RenderTask` computes pseudocolor matrix
10. On completion, update canvas display

**Key Observation:** Single state mutation triggers cascading UI updates via event system.

---

### Workflow 2: User Draws Rectangular Gate

```mermaid
graph TB
    USER["User drag-draws gate<br/>on FlowCanvas"]
    
    MOUSE["CanvasEventHandler<br/>on_mouse_press()"]
    STATE["FSM transition:<br/>IDLE → DRAW_RECT"]
    PREVIEW["Render preview overlay<br/>(dashed rectangle)"]
    
    MOVE["on_mouse_move()"]
    UPDATE_PREVIEW["Update preview position"]
    
    RELEASE["on_mouse_release()"]
    FINALIZE["Create RectangleGate<br/>instance"]
    COORD_CONVERT["Display space →<br/>Data space<br/>(via CoordinateMapper)"]
    
    GATE_COORD["GateCoordinator<br/>.add_gate()"]
    MUTATION["GateMutationService<br/>.add_gate()"]
    CREATE_NODE["Create GateNode<br/>Wire to tree"]
    DAG_EVAL["DagEvaluator<br/>.evaluate()"]
    COMPUTE_STATS["Compute statistics<br/>for all nodes"]
    
    PUBLISH_GATE["Publish:<br/>gate.created"]
    
    PROP["GatePropagator<br/>.schedule_propagation()"]
    DEBOUNCE["Debounce 200ms"]
    CLONE["Clone gate tree to<br/>sibling samples"]
    
    LISTEN["Multiple Listeners"]
    GATE_TREE["GateHierarchy<br/>Add node"]
    RENDER_GATE["GateLayerRenderer<br/>Overlay gate patch"]
    PROPS["PropertiesPanel<br/>Show statistics"]
    RENDER_DATA["FlowCanvas<br/>Re-render data layer<br/>with new gate filter"]
    
    USER --> MOUSE
    MOUSE --> STATE
    STATE --> PREVIEW
    MOVE --> UPDATE_PREVIEW
    UPDATE_PREVIEW --> PREVIEW
    RELEASE --> FINALIZE
    FINALIZE --> COORD_CONVERT
    COORD_CONVERT --> GATE_COORD
    GATE_COORD --> MUTATION
    MUTATION --> CREATE_NODE
    CREATE_NODE --> DAG_EVAL
    DAG_EVAL --> COMPUTE_STATS
    COMPUTE_STATS -->|"mutation"| PUBLISH_GATE
    PUBLISH_GATE --> LISTEN
    PUBLISH_GATE -->|"schedule"| PROP
    PROP --> DEBOUNCE
    DEBOUNCE -->|"200ms delay"| CLONE
    
    LISTEN --> GATE_TREE
    LISTEN --> RENDER_GATE
    LISTEN --> PROPS
    LISTEN --> RENDER_DATA
    
    RENDER_GATE -->|"update"| PREVIEW
    RENDER_DATA -->|"schedule RenderTask"| RENDER_DATA
    
    style MOUSE fill:#fff9c4
    style STATE fill:#fff9c4
    style MUTATION fill:#ffccbc
    style DAG_EVAL fill:#c8e6c9
    style PUBLISH_GATE fill:#fff9c4
    style PROP fill:#f3e5f5
    style LISTEN fill:#b2dfdb
```

**Detailed Steps:**
1. User clicks and drags on canvas (mouse down, move, release)
2. `CanvasEventHandler` captures events; FSM: IDLE → DRAW_RECT
3. Render dashed rectangle overlay (transient, non-blocking)
4. On mouse release:
   - Finalize gate coordinates
   - Convert from display space → data space (via `CoordinateMapper`)
   - Create `RectangleGate` instance
5. Call `GateCoordinator.add_gate()`
6. Service layer:
   - `GateMutationService.add_gate()` creates `GateNode`, wires to tree
   - `DagEvaluator` re-evaluates entire DAG
   - Compute statistics for all nodes (including new gate's counts, percentages)
7. **Publish `gate.created` event**
8. Simultaneously:
   - **Schedule propagation** (debounce 200ms) to clone gate to sibling samples
   - **Publish event** triggers multiple listeners:
     - `GateHierarchy`: Add row to tree widget
     - `GateLayerRenderer`: Draw gate patch on canvas
     - `PropertiesPanel`: Display population statistics
     - `FlowCanvas`: Re-render data layer (visualize gated subset)
9. Background propagation (after 200ms debounce):
   - Clone gate tree to all samples in group
   - Re-evaluate DAG for each sample
   - Re-compute statistics
   - Update group preview thumbnails

**Performance Note:** Debounce prevents thrashing during rapid gate edits (e.g., user dragging gate handle).

---

### Workflow 3: User Applies Compensation

```mermaid
graph TB
    USER["User loads controls<br/>CompensationRibbon"]
    
    SELECT["Select samples:<br/>Single-stain + Unstained"]
    COMPUTE_BUTTON["Click 'Compute Spillover'"]
    
    COMP_SERVICE["CompensationService<br/>.calculate_spillover_matrix()"]
    
    CALC["calculate_spillover_matrix()"]
    EXTRACT_MEDIANS["Extract median<br/>per-channel per-sample"]
    BG_SUBTRACT["Subtract unstained<br/>background"]
    RATIOS["Compute spillover ratios"]
    INVERT["Invert matrix"]
    
    RESULT["CompensationMatrix"]
    
    STORE["FlowState.compensation =<br/>CompensationMatrix"]
    PUBLISH["Publish:<br/>compensation.applied"]
    
    APPLY_TO_SAMPLES["Apply to all samples"]
    FOR_EACH["For each sample:"]
    TRANSFORM["events @ compensation.T<br/>(matrix multiplication)"]
    UPDATE_EVENTS["Update FCSData.events"]
    
    INVALIDATE_STATS["Invalidate statistics<br/>cache"]
    INVALIDATE_RENDER["Invalidate render<br/>cache"]
    
    PUBLISH_EACH["Publish per-sample"]
    
    LISTEN["Multiple Listeners"]
    RE_EVAL["FlowCanvas:<br/>Re-evaluate gates<br/>on compensated data"]
    RE_STATS["Statistics service:<br/>Re-compute stats"]
    SHOW_COMP["Properties panel:<br/>Display compensation"]
    
    USER --> SELECT
    SELECT --> COMPUTE_BUTTON
    COMPUTE_BUTTON --> COMP_SERVICE
    COMP_SERVICE --> CALC
    CALC --> EXTRACT_MEDIANS
    EXTRACT_MEDIANS --> BG_SUBTRACT
    BG_SUBTRACT --> RATIOS
    RATIOS --> INVERT
    INVERT --> RESULT
    
    RESULT --> STORE
    STORE -->|"mutation"| PUBLISH
    PUBLISH --> APPLY_TO_SAMPLES
    APPLY_TO_SAMPLES --> FOR_EACH
    FOR_EACH --> TRANSFORM
    TRANSFORM --> UPDATE_EVENTS
    UPDATE_EVENTS -->|"per-sample"| PUBLISH_EACH
    
    PUBLISH --> INVALIDATE_STATS
    PUBLISH --> INVALIDATE_RENDER
    
    PUBLISH_EACH --> LISTEN
    LISTEN --> RE_EVAL
    LISTEN --> RE_STATS
    LISTEN --> SHOW_COMP
    
    style COMP_SERVICE fill:#c8e6c9
    style CALC fill:#e0e0e0
    style PUBLISH fill:#fff9c4
    style APPLY_TO_SAMPLES fill:#ffccbc
    style LISTEN fill:#b2dfdb
```

**Detailed Steps:**
1. User selects single-stain controls (FITC, PE, PerCP)
2. User selects unstained control (background)
3. Click "Compute Spillover Matrix"
4. Service computes spillover matrix:
   - Extract median fluorescence per detector per control
   - Subtract unstained background
   - Compute spillover ratios (median[detector_j] / median[primary])
   - Invert matrix for compensation application
5. Store in `FlowState.compensation`
6. **Publish `compensation.applied` event**
7. For each sample in experiment:
   - Apply compensation: `compensated_events = raw_events @ inverse_matrix`
   - Update `Sample.fcs_data.events`
   - **Publish per-sample event**
8. Multiple listeners react:
   - `FlowCanvas`: Re-evaluate gates on compensated data (re-apply DAG)
   - `StatsService`: Re-compute statistics
   - `PropertiesPanel`: Display compensation applied badge
9. All plots update to show compensated data

---

## 3. Event Bus Topic Reference

All events published to `CentralEventBus`:

```
Gate Lifecycle
  gate.created(sample_id, node_id, gate_type, name)
  gate.deleted(sample_id, node_id)
  gate.renamed(sample_id, node_id, new_name)
  gate.modified(sample_id, node_id, updates_dict)
  gate.propagated(sample_ids_affected, source_sample_id)
  gate.selected(sample_id, node_id)

Sample Lifecycle
  sample.loaded(sample_id, file_path)
  sample.selected(sample_id)
  sample.role_changed(sample_id, new_role)
  sample.deleted(sample_id)

Rendering Events
  render.config_changed(param_name, new_value)
  render.mode_changed(new_display_mode)
  render.completed()

Axis Events
  axis.params_changed(sample_id, x_param, y_param)
  axis.range_changed(channel, min_val, max_val)
  axis.transform_changed(channel, new_transform_type)

Statistics Events
  stats.computed(sample_id, node_id, stat_results)
  stats.invalidated()

Compensation Events
  compensation.matrix_loaded(matrix, source)
  compensation.applied(samples_affected)

UMAP Events
  umap.job_started(job_id, sample_id)
  umap.job_completed(results)
  umap.job_failed(error_msg)

Propagation Events
  propagation.started()
  propagation.completed(samples_affected)
```

---

## 4. Signal/Slot Connections (PyQt)

### Main Panel Signal Connections

```python
class FlowCytometryPanel(PluginBase):
    def __init__(self):
        self.flow_state = FlowState(...)
        self.event_bus = BioPro.event_bus  # Central Event Bus
        
        # Subscribe to events
        self.event_bus.subscribe('gate.created', self.on_gate_created)
        self.event_bus.subscribe('sample.loaded', self.on_sample_loaded)
        self.event_bus.subscribe('render.completed', self.on_render_complete)
        self.event_bus.subscribe('compensation.applied', self.on_compensation_applied)
    
    def on_gate_created(self, event):
        """Gate creation event from event bus."""
        sample_id = event.sample_id
        node_id = event.node_id
        
        # Update UI components
        self.gate_hierarchy.refresh()
        self.properties_panel.refresh()
        self.flow_canvas.refresh_gate_overlay()
    
    def on_sample_loaded(self, event):
        """Sample loading event."""
        self.sample_list.add_sample(event.sample_id)
        self.flow_canvas.render_sample(event.sample_id)
```

### Canvas Signal Connections

```python
class FlowCanvas(FigureCanvas):
    # PyQt signals (UI → background work)
    render_started = pyqtSignal()
    render_completed = pyqtSignal(dict)  # plot_data
    
    def connect_signals(self):
        # Subscribe to events
        event_bus.subscribe('gate.created', self.on_gate_created)
        event_bus.subscribe('render.config_changed', self.on_render_config_changed)
        event_bus.subscribe('axis.transform_changed', self.on_axis_changed)
        
        # Internal RenderTask signal
        self.render_task.render_complete.connect(self.on_render_complete)
    
    def on_render_config_changed(self, event):
        """Render settings changed (sigma, bins, etc.)."""
        # Schedule re-render with new config
        self.spawn_render_task(
            self.current_sample,
            render_config=event.new_config
        )
    
    def on_render_complete(self):
        """Background RenderTask finished."""
        # Update display
        self.data_layer_renderer.update(self.render_task.plot_data)
        self.canvas.draw()
```

---

## 5. State Mutation Patterns

### Immutable State Updates

The module enforces immutable state updates via event publishing:

```python
# WRONG: Direct mutation without event
flow_state.render_config.sigma = 2.0  # ❌ Other components don't know

# CORRECT: Mutation + publication
flow_state.render_config.sigma = 2.0  # Update state
event_bus.publish('render.config_changed', param='sigma', new_value=2.0)  # Broadcast change
```

### Two-Phase Commits

Complex operations use two-phase commits with validation:

```python
# Phase 1: Attempt mutation
try:
    gate_mutation_service.add_gate(sample_id, gate)
except GeometryError as e:
    # Validation failed; don't publish event
    ui.show_error(f"Invalid gate: {e}")
    return False

# Phase 2: Publication
event_bus.publish('gate.created', sample_id=sample_id, node_id=new_id)
```

---

## References

- **[Architecture Overview](./00_ARCHITECTURE_OVERVIEW.md)**: High-level design principles.
- **[Services & Dependency Injection](./04_SERVICES_AND_DEPENDENCY_INJECTION.md)**: Service orchestration.
- **[Rendering & Visualization](./07_RENDERING_AND_VISUALIZATION.md)**: Rendering pipeline details.
