"""GateNode class for hierarchical gating.
"""

from __future__ import annotations

from biopro_sdk.plugin import get_logger
import uuid
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .base import Gate

logger = get_logger(__name__, "flow_cytometry")

@dataclass
class GateNode:
    """A node in the hierarchical gating tree.

    Each node wraps a :class:`Gate` and maintains parent-child
    relationships and population identity.
    """

    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "All Events"
    negated: bool = False
    gate: Optional[Gate] = None
    children: list["GateNode"] = field(default_factory=list)
    parents: list["GateNode"] = field(default_factory=list, repr=False)
    logic_operator: str = "AND"
    statistics: dict = field(default_factory=dict)
    creation_view: dict = field(default_factory=dict)
    
    @property
    def parent(self) -> Optional["GateNode"]:
        """Backward compatibility for tree traversal. Returns first parent."""
        return self.parents[0] if self.parents else None

    def __post_init__(self):
        # Ensure parent backward compatibility on initialization
        # If someone instantiated GateNode(..., parent=p) we want to handle it.
        # But dataclass doesn't have parent field anymore.
        pass

    @property
    def is_root(self) -> bool:
        return self.gate is None

    def add_child(self, gate: Gate, name: Optional[str] = None) -> "GateNode":
        """Create and attach a child gate node.
        
        Args:
            gate: The Gate instance to wrap in the child node.
            name: Optional human-readable name for the population. If None,
                  uses the first 8 characters of the gate_id.
                  
        Returns:
            GateNode: The newly created and attached child node.
        """
        node_name = name or (gate.gate_id[:8] if gate else "Unknown")
        child = GateNode(gate=gate, name=node_name, parents=[self])
        self.children.append(child)
        return child

    def remove_child(self, node_id: str) -> bool:
        """Remove a child population by node ID.
        
        Args:
            node_id: The unique identifier of the child node to remove.
            
        Returns:
            bool: True if the child was found and removed, False otherwise.
        """
        for i, child in enumerate(self.children):
            if child.node_id == node_id:
                self.children.pop(i)
                return True
        return False

    def find_node_by_id(self, node_id: str) -> Optional["GateNode"]:
        """Recursively search for a population node by its node ID.
        
        Args:
            node_id: The unique identifier to search for in this node and its descendants.
            
        Returns:
            GateNode or None: The matching node if found, otherwise None.
        """
        if self.node_id == node_id:
            return self
        for child in self.children:
            found = child.find_node_by_id(node_id)
            if found:
                return found
        return None

    def find_nodes_by_gate(self, gate_id: str) -> list["GateNode"]:
        """Find all population nodes that use a specific gate instance.
        
        Args:
            gate_id: The unique identifier of the Gate instance to search for.
            
        Returns:
            list[GateNode]: A list of nodes that wrap the specified gate.
        """
        matches = []
        if self.gate and self.gate.gate_id == gate_id:
            matches.append(self)
        for child in self.children:
            matches.extend(child.find_nodes_by_gate(gate_id))
        return matches

    def apply_hierarchy(self, events: pd.DataFrame) -> pd.DataFrame:
        """Apply the DAG hierarchy of gates up to this node.
        
        Args:
            events: The un-gated (root) DataFrame of events.
            
        Returns:
            pd.DataFrame: A subset of events that fall within this hierarchical path.
        """
        if not self.parents:
            mask = np.ones(len(events), dtype=bool)
        else:
            if self.logic_operator == "AND":
                mask = np.ones(len(events), dtype=bool)
                for p in self.parents:
                    parent_df = p.apply_hierarchy(events)
                    mask &= events.index.isin(parent_df.index)
            elif self.logic_operator == "OR":
                mask = np.zeros(len(events), dtype=bool)
                for p in self.parents:
                    parent_df = p.apply_hierarchy(events)
                    mask |= events.index.isin(parent_df.index)
            elif self.logic_operator == "NOT":
                if self.parents:
                    parent_df = self.parents[0].apply_hierarchy(events)
                    mask = ~events.index.isin(parent_df.index)
                else:
                    mask = np.ones(len(events), dtype=bool)
            else:
                mask = np.ones(len(events), dtype=bool)

        if self.gate is not None:
            gate_mask = self.gate.contains(events)
            if self.negated:
                gate_mask = ~gate_mask
            mask &= gate_mask
            
        return events.loc[mask].copy()

    def adapt_all(self, events: pd.DataFrame) -> None:
        """Recursively adapt all adaptive gates in the tree.
        
        Args:
            events: The un-gated (root) DataFrame of events to use for adaptation.
        """
        if self.gate and self.gate.adaptive:
            parent_events = events
            if self.parent:
                parent_events = self.parent.apply_hierarchy(events)
            self.gate.adapt(parent_events)
        
        subset = self.gate.apply(events) if self.gate else events
        for child in self.children:
            child.adapt_all(subset)

    @staticmethod
    def from_dict(data: dict, parent: Optional["GateNode"] = None) -> "GateNode":
        """Reconstruct a population DAG from a serialized dictionary."""
        from .gate_factory import gate_from_dict
        
        # Backward compatibility for nested tree format
        if "children" in data:
            gate_data = data.get("gate")
            gate = gate_from_dict(gate_data) if gate_data else None
            
            node = GateNode(
                gate=gate,
                name=data.get("name", "Unknown"),
                parents=[parent] if parent else [],
                node_id=data.get("node_id"),
                negated=data.get("negated", False),
                logic_operator=data.get("logic_operator", "AND")
            )
            node.statistics = data.get("statistics", {})
            node.creation_view = data.get("creation_view", {})
            
            for child_data in data.get("children", []):
                node.children.append(GateNode.from_dict(child_data, parent=node))
                
            return node
            
        # Flat DAG format
        if "nodes" in data:
            nodes_by_id = {}
            root = None
            
            # First pass: create all nodes
            for n_data in data["nodes"]:
                gate_data = n_data.get("gate")
                gate = gate_from_dict(gate_data) if gate_data else None
                node = GateNode(
                    gate=gate,
                    name=n_data.get("name", "Unknown"),
                    node_id=n_data.get("node_id"),
                    negated=n_data.get("negated", False),
                    logic_operator=n_data.get("logic_operator", "AND")
                )
                node.creation_view = n_data.get("creation_view", {})
                nodes_by_id[node.node_id] = node
                if n_data.get("is_root"):
                    root = node
                    
            # Second pass: wire them up
            for n_data in data["nodes"]:
                node = nodes_by_id[n_data["node_id"]]
                for p_id in n_data.get("parents", []):
                    if p_id in nodes_by_id:
                        p_node = nodes_by_id[p_id]
                        node.parents.append(p_node)
                        p_node.children.append(node)
                        
            return root
            
        raise ValueError("Invalid serialized DAG format")

    def to_dict(self) -> dict:
        """Serialize the full population DAG as a flat list of nodes."""
        nodes = []
        visited = set()
        
        def _collect(n: "GateNode"):
            if n.node_id in visited:
                return
            visited.add(n.node_id)
            nodes.append({
                "node_id": n.node_id,
                "name": n.name,
                "negated": n.negated,
                "logic_operator": n.logic_operator,
                "gate": n.gate.to_dict() if n.gate else None,
                "parents": [p.node_id for p in n.parents],
                "is_root": not bool(n.parents),
                "creation_view": n.creation_view
            })
            for c in n.children:
                _collect(c)
                
        _collect(self)
        return {"type": "dag", "nodes": nodes}
