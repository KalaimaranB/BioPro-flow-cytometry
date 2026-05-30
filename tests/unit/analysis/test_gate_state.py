import json

with open("workflows/simple_viability.json") as f:
    data = json.load(f)

for child in data["gate_template"]["children"]:
    if child["gate"]["name"] == "Cells":
        print(f"Gate Name: {child['gate']['name']}")
        print(f"Gate Type: {child['gate']['type']}")
        print(f"Vertices Length: {len(child['gate']['vertices'])}")
        print(f"Vertices Data: {child['gate']['vertices']}")
