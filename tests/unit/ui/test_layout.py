import sys
import os

from analysis.gating.gate_node import GateNode
from analysis.gating.base import Gate
from ui.widgets.gate_hierarchy.node_tree_engine import NodeTreeEngine

class DummyGate(Gate):
    def contains(self, events): pass

root = GateNode(node_id="root", name="All Events")
child1 = GateNode(node_id="child1", name="Gate 1", gate=DummyGate("child1"))
child2 = GateNode(node_id="child2", name="Gate 2", gate=DummyGate("child2"))
root.add_child(child1)
root.add_child(child2)

engine = NodeTreeEngine()
rects = engine.compute(root)

for r in rects:
    print(f"{r.name}: x={r.x}, y={r.y}, w={r.width}, h={r.height}")

