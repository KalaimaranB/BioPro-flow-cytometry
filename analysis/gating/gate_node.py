"""GateNode class for hierarchical gating."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from biopro_sdk.plugin import get_logger

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
    gate: Gate | None = None
    children: list[GateNode] = field(default_factory=list)
    parents: list[GateNode] = field(default_factory=list, repr=False)
    logic_operator: str = "AND"
    statistics: dict = field(default_factory=dict)
    creation_view: dict = field(default_factory=dict)

    @property
    def is_root(self) -> bool:
        """True only for the single 'All Events' root node — not for logic nodes.
        
        Logic nodes (AND/OR/NOT) also have gate=None but have parents or a
        non-default logic_operator. Only the sentinel root has no gate AND
        no parents (it is the top of the tree).
        """
        return self.gate is None and not self.parents

    def add_child(self, gate: Gate, name: str | None = None) -> GateNode:
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

    def find_node_by_id(self, node_id: str) -> GateNode | None:
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

    def find_nodes_by_gate(self, gate_id: str) -> list[GateNode]:
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
                    parent_mask = events.index.isin(parent_df.index)
                    logger.debug(
                        "AND gate '%s': parent '%s' contributed %d/%d events (index dtype: %s, parent index dtype: %s)",
                        self.name, p.name, int(parent_mask.sum()), len(events),
                        events.index.dtype, parent_df.index.dtype
                    )
                    mask &= parent_mask
                logger.debug("AND gate '%s': intersection = %d events", self.name, int(mask.sum()))
            elif self.logic_operator == "OR":
                mask = np.zeros(len(events), dtype=bool)
                for p in self.parents:
                    parent_df = p.apply_hierarchy(events)
                    mask |= events.index.isin(parent_df.index)
            elif self.logic_operator == "NOT":
                if not self.parents:
                    mask = np.ones(len(events), dtype=bool)
                else:
                    # NOT gate takes the primary parent (first one)
                    # and SUBTRACTS any subsequent parents.
                    # If only one parent exists, it subtracts it from all events.
                    if len(self.parents) == 1:
                        primary_df = self.parents[0].apply_hierarchy(events)
                        mask = ~events.index.isin(primary_df.index)
                    else:
                        primary_df = self.parents[0].apply_hierarchy(events)
                        mask = events.index.isin(primary_df.index)
                        for p in self.parents[1:]:
                            parent_df = p.apply_hierarchy(events)
                            mask &= ~events.index.isin(parent_df.index)
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
        if self.gate and getattr(self.gate, "adaptive", False):
            parent_events = events
            if self.parents:
                dummy = GateNode(parents=self.parents, logic_operator=self.logic_operator)
                parent_events = dummy.apply_hierarchy(events)
            self.gate.adapt(parent_events)

        subset = self.gate.apply(events) if self.gate else events
        for child in self.children:
            child.adapt_all(subset)

    @staticmethod
    def from_dict(data: dict) -> GateNode:
        """Reconstruct a population DAG from a serialized dictionary."""
        from .gate_factory import gate_from_dict

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
                    logic_operator=n_data.get("logic_operator", "AND"),
                )
                node.creation_view = n_data.get("creation_view", {})
                node.is_umap_parent = n_data.get("is_umap_parent", False)
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

        def _collect(n: GateNode):
            if n.node_id in visited:
                return
            visited.add(n.node_id)
            nodes.append(
                {
                    "node_id": n.node_id,
                    "name": n.name,
                    "negated": n.negated,
                    "logic_operator": n.logic_operator,
                    "gate": n.gate.to_dict() if n.gate else None,
                    "parents": [p.node_id for p in n.parents],
                    "is_root": not bool(n.parents),
                    "creation_view": n.creation_view,
                    "is_umap_parent": getattr(n, "is_umap_parent", False),
                }
            )
            for c in n.children:
                _collect(c)

        _collect(self)
        return {"type": "dag", "nodes": nodes}
