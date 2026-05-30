"""Manager to bridge GateTree model with the Canvas View."""

from PyQt6.QtWidgets import QGraphicsScene
from PyQt6.QtCore import QObject, pyqtSignal, QPointF

from analysis.state import FlowState
from analysis.gating.gate_node import GateNode

from .items.node_item import NodeItem
from .items.edge_item import EdgeItem
from .layout_engine import LayoutEngine

from biopro.core.task_scheduler import task_scheduler
from biopro_sdk.plugin import get_logger
from PyQt6.QtGui import QImage
from typing import Any

logger = get_logger(__name__, "flow_cytometry")

# Global Cache for Mini-plots
# Key: (sample_id, node_id, geom_hash) -> Value: QImage
_ThumbnailCache = {}

class CanvasManager(QObject):
    """Controls the QGraphicsScene based on the current gating state."""

    node_double_clicked = pyqtSignal(str)
    connection_requested = pyqtSignal(str, str)  # source_node_id, target_node_id
    connection_removed = pyqtSignal(str, str)    # source_node_id, target_node_id

    def __init__(self, state: FlowState, scene: QGraphicsScene, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self.scene = scene
        
        self._node_items = {}  # node_id -> NodeItem
        self._edge_items = []
        
        # Interactive edge dragging state
        self._temp_drag_edge = None
        self._drag_source_id = None
        
        self._current_sample_id = None
        self._pending_tasks = {} # task_id -> node_id

        # Subscribe to TaskScheduler ONLY ONCE by checking if we're already connected
        try:
            task_scheduler.task_finished.disconnect(self._on_render_task_finished)
        except TypeError:
            pass
        task_scheduler.task_finished.connect(self._on_render_task_finished)

    def load_sample(self, sample_id: str) -> None:
        """Load the given sample's gating tree onto the canvas."""
        self.scene.clear()
        self._node_items.clear()
        self._edge_items.clear()
        
        if not sample_id:
            return
            
        sample = self.state.data.experiment.samples.get(sample_id)
        if not sample or not sample.gate_tree:
            return
            
        self._current_sample_id = sample_id
            
        # 1. Build Nodes
        self._build_nodes_recursive(sample.gate_tree, is_root=True)
        
        # 2. Build Edges
        self._build_edges_recursive(sample.gate_tree)
        
        # 3. Apply Layout
        LayoutEngine.compute_layout(sample.gate_tree, self._node_items)
        
        # 4. Update edges after layout
        for edge in self._edge_items:
            edge.update_position()
            
    def _build_nodes_recursive(self, node: GateNode, is_root: bool = False) -> None:
        # Don't show the virtual root node itself if it's named "All Events", but
        # wait, we DO want to show "All Events" so users can branch from it!
        
        item = NodeItem(node.node_id, node.name or "All Events")
        item.logic_operator = node.logic_operator
        item.is_logic_node = (node.gate is None and not is_root)
        
        # Populate stats if available
        if node.statistics:
            item.event_count = node.statistics.get("count", 0)
            item.parent_percentage = node.statistics.get("pct_parent", 0.0)
            
        if is_root:
            item.x_param, item.y_param = "FSC-A", "SSC-A"
        elif node.gate:
            item.x_param, item.y_param = node.gate.x_param, node.gate.y_param
            
        self.scene.addItem(item)
        self._node_items[node.node_id] = item
        
        # If the item is dragged, update its connected edges
        item.xChanged.connect(self._update_edges)
        item.yChanged.connect(self._update_edges)
        
        # Wire double click to Ribbon swap
        item.node_double_clicked.connect(self.node_double_clicked.emit)
        
        # Wire edge dragging
        item.edge_drag_started.connect(self._on_edge_drag_started)
        item.edge_dragged.connect(self._on_edge_dragged)
        item.edge_drag_released.connect(self._on_edge_drag_released)
        
        # Request thumbnail
        self._request_render(node, item, is_root=is_root)
        
        for child in node.children:
            self._build_nodes_recursive(child, is_root=False)
            
    def _build_edges_recursive(self, node: GateNode) -> None:
        source_item = self._node_items.get(node.node_id)
        
        is_absolute_root = not node.parents
        
        for child in node.children:
            target_item = self._node_items.get(child.node_id)
            
            # Hide the default connection to root for empty logic nodes to avoid clutter
            hide_edge = False
            if is_absolute_root and child.gate is None:
                if len(child.parents) == 1:
                    hide_edge = True
                    
            if source_item and target_item and not hide_edge:
                edge = EdgeItem(source_item, target_item)
                self.scene.addItem(edge)
                self._edge_items.append(edge)
                
            self._build_edges_recursive(child)
            
    def _update_edges(self) -> None:
        """Called when any node moves. Recalculates all edge curves."""
        for edge in self._edge_items:
            edge.update_position()
            
    # ── Interactive Edge Wiring ────────────────────────────────────────

    def _on_edge_drag_started(self, source_node_id: str, start_pos: QPointF) -> None:
        source_item = self._node_items.get(source_node_id)
        if not source_item:
            return
            
        self._drag_source_id = source_node_id
        
        # Create a temporary edge from the source to the current mouse pos
        # We can simulate this by making a dummy EdgeItem where the target is just a point
        class DummyItem:
            def __init__(self, pos):
                self.pos = pos
            def get_input_port_pos(self):
                return self.pos
                
        self._dummy_target = DummyItem(start_pos)
        self._temp_drag_edge = EdgeItem(source_item, self._dummy_target)
        self.scene.addItem(self._temp_drag_edge)

    def _on_edge_dragged(self, current_pos: QPointF) -> None:
        if self._temp_drag_edge:
            self._dummy_target.pos = current_pos
            self._temp_drag_edge.update_position()

    def _on_edge_drag_released(self, source_node_id: str, release_pos: QPointF) -> None:
        if self._temp_drag_edge:
            self.scene.removeItem(self._temp_drag_edge)
            self._temp_drag_edge = None
            
        self._drag_source_id = None
        
        # Find which node we released over
        items = self.scene.items(release_pos)
        target_node_id = None
        for item in items:
            if isinstance(item, NodeItem) and item.node_id != source_node_id:
                # Check if it was specifically released over the input port
                port = item._get_port_at(item.mapFromScene(release_pos))
                if port == 'input':
                    target_node_id = item.node_id
                    break
                    
        if target_node_id:
            self.connection_requested.emit(source_node_id, target_node_id)

    # ── Mini Plot Rendering ───────────────────────────────────────────

    def _get_geom_hash(self, gate) -> tuple:
        if not gate: return None
        if hasattr(gate, "vertices"): return tuple(gate.vertices)
        if hasattr(gate, "x_min"): return (gate.x_min, gate.x_max, gate.y_min, gate.y_max)
        if hasattr(gate, "center"): return (gate.center, gate.width, gate.height)
        if hasattr(gate, "x_mid"): return (gate.x_mid, gate.y_mid)
        if hasattr(gate, "low"): return (gate.low, gate.high)
        return None

    def _request_render(self, node: GateNode, item: NodeItem, is_root: bool = False) -> None:
        """Asynchronously render a mini plot for the node item."""
        if item.is_logic_node:
            return # Logic nodes skip plots
        
        # UMAP parent nodes contain index-based populations \u2014 no geometric axes to plot
        if getattr(node, "is_umap_parent", False):
            return

        sample_id = self._current_sample_id
        if not sample_id:
            return

        gate = node.gate
        geom_hash = self._get_geom_hash(gate)
        
        # Check cache first
        cache_key = (sample_id, node.node_id, geom_hash)
        if cache_key in _ThumbnailCache:
            item.set_plot_image(_ThumbnailCache[cache_key])
            return

        # Prepare parameters
        # Determine axes
        if node.creation_view:
            cv = node.creation_view
            x_param = cv["x_param"]
            y_param = cv.get("y_param", "SSC-A")
        elif node.children and node.children[0].gate:
            # Show the axes where the first child gate is drawn
            x_param, y_param = node.children[0].gate.x_param, node.children[0].gate.y_param
            if x_param == "Subset" or not y_param:
                x_param, y_param = "FSC-A", "SSC-A"
        else:
            # No children, show the axes of the gate that created it (or default for root)
            if is_root:
                x_param, y_param = "FSC-A", "SSC-A"
            else:
                x_param, y_param = gate.x_param, gate.y_param
                if x_param == "Subset" or not y_param:
                    x_param, y_param = "FSC-A", "SSC-A"

        # Get events for THIS node (not its parent)
        events = self.state.population_service.get_gated_events(sample_id, None if is_root else node.node_id)
        
        if events is None or len(events) == 0:
            return

        # Gather the gates drawn ON this node (its children's gates)
        # Only include gates that match the chosen x_param/y_param
        child_gates = []
        for child in node.children:
            if child.gate and child.gate.x_param == x_param and child.gate.y_param == y_param:
                child_gates.append(child.gate)

        # Use exact scales from creation_view if available, else fallback to global
        if node.creation_view and "x_scale" in node.creation_view:
            from analysis.scaling import AxisScale
            x_scale = AxisScale.from_dict(node.creation_view["x_scale"])
        else:
            x_scale = self.state.axis_manager.get_scale(x_param)
            
        if node.creation_view and "y_scale" in node.creation_view:
            from analysis.scaling import AxisScale
            y_scale = AxisScale.from_dict(node.creation_view["y_scale"])
        else:
            y_scale = self.state.axis_manager.get_scale(y_param)
            
        x_range = self.state.axis_manager.calculate_range(events[x_param], x_param)
        y_range = self.state.axis_manager.calculate_range(events[y_param], y_param)
        
        # Choose renderer based on plot type
        plot_type = self.state.view.active_plot_type
        if node.creation_view and "plot_type" in node.creation_view:
            plot_type = node.creation_view["plot_type"]
        
        from ...graph.render_task import RenderTask
        task = RenderTask()
        
        # We add show_gate_labels=False so the GateOverlayRenderer hides the labels
        rc = self.state.view.render_config.to_dict()
        rc["show_gate_labels"] = False
        rc["show_axis_labels"] = False
        rc["dpi"] = 300
        
        # Request 2x size (360x360) for high-DPI (Retina) support,
        # NodeItem.paint will smoothly scale it down to the 180x180 display rect.
        task.configure(
            data=events,
            x_param=x_param,
            y_param=y_param,
            x_scale=x_scale,
            y_scale=y_scale,
            x_range=x_range,
            y_range=y_range,
            width_px=180,
            height_px=180,
            plot_type=plot_type,
            max_events=15000,
            quality_multiplier=2.0,
            gates=child_gates,
            selected_gate_id=None,
            s=0.5,
            colormap=self.state.view.render_config.pseudocolor.colormap,
            render_config=rc
        )
        
        # We need both node_id and the param names so NodeItem can draw axis labels
        task.config["node_id"] = node.node_id
        task.config["x_param"] = x_param
        task.config["y_param"] = y_param
        
        worker = task_scheduler.submit(task, self.state)
        # Store metadata to map back the result
        self._pending_tasks[worker.task_id] = {
            "node_id": node.node_id,
            "cache_key": cache_key
        }

    def _on_render_task_finished(self, tid: str, results: dict) -> None:
        """Process the returned image payload."""
        if str(tid) not in self._pending_tasks:
            return
            
        meta = self._pending_tasks.pop(str(tid))
        node_id = meta["node_id"]
        cache_key = meta["cache_key"]
        
        if "error" in results:
            logger.warning(f"Thumbnail render error for {node_id}: {results['error']}")
            return
            
        buf = results.get("image_data")
        if not buf:
            return
            
        w, h = results["width"], results["height"]
        
        try:
            qimg = QImage(buf, w, h, QImage.Format.Format_RGBA8888).copy()
            _ThumbnailCache[cache_key] = qimg
            
            # Apply to item if it still exists
            item = self._node_items.get(node_id)
            if item:
                item.set_plot_image(qimg)
        except RuntimeError:
            # The user likely navigated away or rebuilt the scene, 
            # so the NodeItem's underlying C++ object was deleted.
            pass
        except Exception as e:
            logger.error(f"Failed to set thumbnail for {node_id}: {e}")
