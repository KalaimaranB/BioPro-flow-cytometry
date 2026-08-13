import json
import os

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
workflow_path = os.path.join(
    _repo_root, "src/karcytics_plugins/flow_cytometry/workflows/simple_viability.json"
)
with open(workflow_path) as f:
    data = json.load(f)

for child in data["gate_template"]["children"]:
    if child["gate"]["name"] == "Cells":
        print(f"Gate Name: {child['gate']['name']}")
        print(f"Gate Type: {child['gate']['type']}")
        print(f"Vertices Length: {len(child['gate']['vertices'])}")
        print(f"Vertices Data: {child['gate']['vertices']}")
