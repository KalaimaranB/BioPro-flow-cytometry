# Developer API Reference — Gating & Analysis

This document provides a technical specification for the core analytical and mathematical engines of the BioPro Flow Cytometry module.

## 1. Gating Engine (`analysis/gating.py`)

The geometric gating engine implements high-performance hierarchical point-in-polygon evaluations. All gating geometries inherit from the abstract `Gate` base class and must implement the `contains(events: pd.DataFrame) -> np.ndarray[bool]` boolean masking method.

### `RectangleGate`
Defines an orthogonal 1D or 2D region in the raw scalar data space.
```python
RectangleGate(
    x_param: str,
    y_param: str,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    name: str = "",
    adaptive: bool = False
)
```

### `PolygonGate`
Defines an arbitrary multi-vertex geometric boundary using an ordered list of vertices. Coordinates are dynamically projected into display space during the `contains()` evaluation to ensure visual parity across linear, logarithmic, and biexponential coordinate systems.
```python
PolygonGate(
    x_param: str,
    y_param: str,
    vertices: list[tuple[float, float]],
    name: str = "",
    adaptive: bool = False
)
```

### `EllipseGate`
Defines an elliptical boundary utilizing a center point, axis lengths, and a rotational matrix.
```python
EllipseGate(
    x_param: str,
    y_param: str,
    center: tuple[float, float],
    width: float,
    height: float,
    angle: float = 0.0,
    name: str = "",
    adaptive: bool = False
)
```
> [!NOTE]
> `width` and `height` designate the full axis lengths (not semi-axes).

### `QuadrantGate`
Instantiates a bifurcating origin point that divides the analytical coordinate space into four mutually exclusive regions.
```python
QuadrantGate(
    x_param: str,
    y_param: str,
    x_mid: float,
    y_mid: float,
    name: str = ""
)
```

---

## 2. Mathematical Transformations (`analysis/transforms.py`)

The module supports three primary algebraic transformations, explicitly controlled via the `TransformType` enumeration.

### `TransformType`
- `LINEAR`: The identity transformation matrix.
- `LOG`: Canonical Base-10 logarithmic scaling.
- `BIEXPONENTIAL`: Mathematical implementation of the Parks 2006 Logicle algorithm.

### `biexponential_transform`
The core mathematical algorithm governing fluorescence visualization.
```python
biexponential_transform(
    data: np.ndarray,
    top: float = 262144.0,  # T parameter
    width: float = 1.0,     # W parameter
    positive: float = 4.5,  # M parameter
    negative: float = 0.0   # A parameter
)
```
The implementation natively utilizes the `flowkit` C-extension for peak computational throughput, with a high-fidelity `asinh` algorithmic fallback for unsupported architectures.

---

## 3. Coordinate Scaling & Ranging (`analysis/scaling.py`)

The `AxisScale` dataclass manages coordinate scale parameters and transformation configurations for an isolated detector channel.

### `AxisScale`
```python
@dataclass
class AxisScale:
    transform_type: TransformType
    min_val: float | None = None
    max_val: float | None = None
    logicle_t: float = 262144.0
    logicle_w: float = 1.0
    logicle_m: float = 4.5
    logicle_a: float = 0.0
    outlier_percentile: float = 0.1
```

### Robust Auto-Ranging Algorithm
The module implements a statistical auto-ranging algorithm that algorithmically discards outliers at the specified `outlier_percentile` threshold (default 0.1%). This prevents visual "compression" of dense populations caused by rare background noise or extreme instrument artifacts.

---

## Technical Guides
- **[Architecture Overview](./00_ARCHITECTURE_OVERVIEW.md)**
- **[UI Engine & Rendering](./02_UI_ENGINE.md)**
- **[Testing & Quality Assurance](./03_TESTING_AND_QA.md)**
