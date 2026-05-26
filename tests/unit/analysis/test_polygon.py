import pandas as pd
import numpy as np
from analysis.gating.polygon import PolygonGate
from analysis.scaling import AxisScale
from analysis.transforms import TransformType

# Create dummy data
df = pd.DataFrame({
    'FSC-A': np.linspace(0, 1000, 1000),
    'SSC-A': np.linspace(0, 1000, 1000)
})

# Create a polygon that encompasses 100 to 900
vertices = [(100, 100), (900, 100), (900, 900), (100, 900)]
gate = PolygonGate('FSC-A', 'SSC-A', vertices)

# Test contains
mask = gate.contains(df)
print(f"Events contained: {np.sum(mask)}")
