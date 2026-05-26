"""Auto-layout algorithms for the Node Canvas."""

from typing import Dict, Any, List

class LayoutEngine:
    """Computes X/Y coordinates for a tree of nodes."""
    
    # Spacing configuration
    X_SPACING = 300  # Distance between levels
    Y_SPACING = 320  # Distance between siblings
    
    @classmethod
    def compute_layout(cls, root_node: Any, items_dict: Dict[str, Any]) -> None:
        """
        Compute and apply positions to a dictionary of NodeItems.
        
        Args:
            root_node: The root GateNode of the tree.
            items_dict: Dictionary mapping node_id to NodeItem instance.
        """
        if not root_node or not root_node.children:
            # If there's no tree or just root, put root at center
            if root_node and root_node.node_id in items_dict:
                items_dict[root_node.node_id].setPos(0, 0)
            return

        # 1. Collect all nodes and compute depth
        depths = {}
        visited = set()
        
        def _compute_depth(node: Any, current_depth: int) -> None:
            if node.node_id not in depths or current_depth > depths[node.node_id]:
                depths[node.node_id] = current_depth
                
            if node.node_id in visited and depths[node.node_id] >= current_depth:
                return
            visited.add(node.node_id)
            
            for child in node.children:
                _compute_depth(child, current_depth + 1)
                
        _compute_depth(root_node, 0)
        
        # 2. Group nodes by depth
        nodes_by_depth: Dict[int, List[Any]] = {}
        for node_id, depth in depths.items():
            if depth not in nodes_by_depth:
                nodes_by_depth[depth] = []
            
            # Find the actual node object (traverse again or use items_dict)
            # We can't get node from items_dict easily, we need the GateNode.
            # Let's write a quick finder.
            def find(n, target_id, found_set):
                if n.node_id == target_id:
                    return n
                if n.node_id in found_set:
                    return None
                found_set.add(n.node_id)
                for c in n.children:
                    res = find(c, target_id, found_set)
                    if res: return res
                return None
                
            n = find(root_node, node_id, set())
            if n:
                nodes_by_depth[depth].append(n)
                
        # 3. Assign positions
        for depth, nodes in nodes_by_depth.items():
            # Calculate total height of this column to center it vertically
            total_height = (len(nodes) - 1) * cls.Y_SPACING
            start_y = -total_height / 2.0
            
            for i, node in enumerate(nodes):
                item = items_dict.get(node.node_id)
                if item:
                    x = depth * cls.X_SPACING
                    y = start_y + i * cls.Y_SPACING
                    item.setPos(x, y)
