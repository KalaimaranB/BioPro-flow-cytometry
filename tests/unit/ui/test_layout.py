from analysis.gating.base import Gate
from analysis.gating.gate_node import GateNode
from ui.widgets.gate_hierarchy.node_tree_engine import NodeTreeEngine


class DummyGate(Gate):
    def __init__(self, gate_id=""):
        super().__init__(gate_id=gate_id, x_param="FSC-A")
        self.y_param = "SSC-A"

    def contains(self, events):
        pass

    def contains_vectorized(self, events):
        pass

    def copy(self):
        return DummyGate(self.gate_id)


def test_layout_computation():
    root = GateNode(node_id="root", name="All Events")
    child1 = root.add_child(DummyGate("child1"), name="Gate 1")
    child2 = root.add_child(DummyGate("child2"), name="Gate 2")

    engine = NodeTreeEngine()
    rects = engine.compute(root)

    for r in rects:
        print(f"{r.name}: x={r.x}, y={r.y}, w={r.width}, h={r.height}")


if __name__ == "__main__":
    test_layout_computation()
