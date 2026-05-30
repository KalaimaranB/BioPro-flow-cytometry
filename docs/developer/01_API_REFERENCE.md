# Developer API Reference — Complete Implementation Details

This document provides comprehensive technical specifications for the analytical engines, gate types, statistics computations, and service layer of the BioPro Flow Cytometry module.

---

## 1. Gate Types & Geometric Algorithms

All gates inherit from the abstract `Gate` base class. Each implements:
- `contains(events: pd.DataFrame) -> np.ndarray[bool]`: Returns boolean mask of gated events.
- `adapt(events: pd.DataFrame) -> Gate`: Adaptive rescaling based on event distribution.
- `serialize() -> dict`: JSON serialization for workflow persistence.

### `RectangleGate` (2D Rectangular Region)

**Mathematical Definition:**
$$\text{Gated} = \{(x,y) : x_{\min} \leq x \leq x_{\max} \text{ AND } y_{\min} \leq y \leq y_{\max}\}$$

```python
RectangleGate(
    x_param: str,           # X-axis parameter name (e.g., 'FSC-A')
    y_param: str,           # Y-axis parameter name (e.g., 'SSC-A')
    x_min: float,           # Lower x boundary
    x_max: float,           # Upper x boundary
    y_min: float,           # Lower y boundary
    y_max: float,           # Upper y boundary
    name: str = "",         # Population display name
    adaptive: bool = False  # Auto-adjust on display transform change
)
```

**Performance:** O(n) single pass; vectorized NumPy operations.

**Use Cases:**
- Forward/Side scatter lymphocyte gating
- Density-based population isolation
- Quality control thresholding

---

### `PolygonGate` (Free-Form Multi-Vertex Region)

**Mathematical Definition:**  
Uses **Winding Number Algorithm** for point-in-polygon testing:
- For each vertex pair, compute cross product: $\vec{v} = (v_i - p) \times (v_{i+1} - p)$
- Sum cross products; if non-zero, point is inside polygon.

```python
PolygonGate(
    x_param: str,
    y_param: str,
    vertices: list[tuple[float, float]],  # Ordered vertices [(x0,y0), (x1,y1), ...]
    name: str = "",
    adaptive: bool = False
)
```

**Coordinate Handling:**
- Vertices stored in **event/data space** (pre-transform coordinates).
- During `contains()` evaluation, vertices are dynamically projected into **display space** using current `AxisScale` transforms.
- This ensures visual parity: gate drawn at screen position matches the event filter.

**Example: Lymphocyte Polygon**
```python
vertices = [
    (0, 0),           # lower-left
    (100000, 0),      # lower-right
    (100000, 80000),  # upper-right
    (40000, 60000),   # upper-left
]
gate = PolygonGate('FSC-A', 'SSC-A', vertices, name='Lymphocytes')
```

**Performance:** O(n*m) where m = number of vertices; optimized via NumPy broadcasts.

---

### `EllipseGate` (Elliptical Region)

**Mathematical Definition:**  
Standard ellipse equation with 2D rotation matrix:
$$\left(\frac{x - c_x}{a}\right)^2 \cos^2(\theta) + 2\left(\frac{x - c_x}{a}\right)\left(\frac{y - c_y}{b}\right)\sin(\theta)\cos(\theta) + \left(\frac{y - c_y}{b}\right)^2\sin^2(\theta) \leq 1$$

```python
EllipseGate(
    x_param: str,
    y_param: str,
    center: tuple[float, float],  # Centroid (cx, cy)
    width: float,                  # Full width along x-axis (not semi-axis)
    height: float,                 # Full height along y-axis (not semi-axis)
    angle: float = 0.0,            # Rotation angle in degrees
    name: str = "",
    adaptive: bool = False
)
```

**Important Note:** `width` and `height` are **full axis lengths**, not semi-axes. Internally, semi-axes are computed as `width/2` and `height/2`.

**Example: CD4 Population Ellipse**
```python
gate = EllipseGate(
    'CD3-BV421', 'CD4-PE',
    center=(50000, 75000),
    width=30000,    # ±15,000 in x
    height=25000,   # ±12,500 in y
    angle=15.0,     # 15° rotation
    name='CD4+ T-cells'
)
```

**Performance:** O(n); rotation matrix pre-computed.

---

### `RangeGate` (1D Single-Parameter Range)

**Mathematical Definition:**
$$\text{Gated} = \{x : x_{\min} \leq x \leq x_{\max}\}$$

```python
RangeGate(
    param: str,      # Parameter name (e.g., 'Viability Dye')
    min_val: float,  # Lower threshold
    max_val: float,  # Upper threshold
    name: str = ""
)
```

**Use Cases:**
- Viability marker filtering (low = live cells)
- Area normalization (FSC-H vs FSC-A)
- Single-parameter thresholding

---

### `QuadrantGate` (Automatic 4-Quadrant Division)

**Mathematical Definition:**  
Divides 2D space into 4 mutually exclusive quadrants at a split point:
- **Q1**: $x \geq x_{\text{mid}}, y \geq y_{\text{mid}}$ (upper-right)
- **Q2**: $x < x_{\text{mid}}, y \geq y_{\text{mid}}$ (upper-left)
- **Q3**: $x < x_{\text{mid}}, y < y_{\text{mid}}$ (lower-left)
- **Q4**: $x \geq x_{\text{mid}}, y < y_{\text{mid}}$ (lower-right)

```python
QuadrantGate(
    x_param: str,     # X-axis parameter
    y_param: str,     # Y-axis parameter
    x_mid: float,     # X split point
    y_mid: float,     # Y split point
    name: str = ""    # Base name (children named Q1, Q2, Q3, Q4)
)
```

**Automatic Child Creation:**  
When a `QuadrantGate` is added to the tree, the system automatically creates 4 `QuadrantSubGate` child populations:
- `{name}_Q1`
- `{name}_Q2`
- `{name}_Q3`
- `{name}_Q4`

**Use Cases:**
- Cytokine co-expression (IFN-γ+ TNF-α+, IFN-γ+ TNF-α-, etc.)
- CD4/CD8 classification
- Two-marker immunophenotyping

**Example: CD4/CD8 Quadrant**
```python
gate = QuadrantGate('CD4-PE', 'CD8-APC', x_mid=50000, y_mid=50000, name='CD4_CD8')
# Creates: CD4_CD8_Q1 (CD4+ CD8+), CD4_CD8_Q2 (CD4- CD8+), 
#          CD4_CD8_Q3 (CD4- CD8-), CD4_CD8_Q4 (CD4+ CD8-)
```

---

### `SubsetGate` (Boolean Parent Reference)

**Mathematical Definition:**  
Filters events to a subset of a parent population (Boolean logic):
$$\text{Gated} = \text{Parent Population} \cap \text{Additional Filter}$$

```python
SubsetGate(
    parent_node_id: str,  # Node ID of parent population
    name: str = ""
)
```

**Use Cases:**
- Subset operations in DAG (e.g., "Live Lymphocytes" = Lymphocytes ∩ Viability+)
- Complex Boolean gating (AND, OR, NOT operations)

**Note:** Actual filtering may require boolean logic via `DagEvaluator` for multi-parent nodes.

---

### `QuadrantSubGate` (Individual Quadrant from AutoSplit)

**Mathematical Definition:**  
Single quadrant from an automatic 4-quadrant split (typically auto-generated):
```python
QuadrantSubGate(
    x_param: str,
    y_param: str,
    x_mid: float,
    y_mid: float,
    quadrant: int,  # 1, 2, 3, or 4
    name: str = ""
)
```

**Typically NOT instantiated directly**; created automatically by `QuadrantGate`.

---

## 2. Statistics Engine (`analysis/statistics.py`)

The module computes **13+ statistical parameters** per gated population. Each statistic is defined by a `StatDefinition` and computed via `compute_statistic()`.

### Statistic Types

| Stat Type | Calculation | Formula | Use |
|-----------|-------------|---------|-----|
| **COUNT** | Event count | $\|S\|$ | Population size |
| **MEAN** | Arithmetic mean | $\frac{1}{n}\sum x_i$ | Average fluorescence intensity |
| **MEDIAN** | 50th percentile | $p_{50}$ | Central tendency (robust) |
| **GEOMETRIC_MEAN** | Geometric mean | $(\prod x_i)^{1/n}$ | Central tendency (log-normal data) |
| **MODE** | Modal value | $\arg\max \text{hist}(x)$ | Most frequent value |
| **SD** | Standard deviation | $\sqrt{\frac{1}{n}\sum(x_i - \bar{x})^2}$ | Spread/dispersion |
| **CV** | Coefficient of variation | $\frac{\sigma}{\mu} \times 100\%$ | Relative spread |
| **MFI** | Median fluorescence intensity | Same as MEDIAN | Standard cytometry metric |
| **PERCENT_PARENT** | Percentage of parent | $\frac{\|S\|}{\|P\|} \times 100\%$ | Relative abundance in parent |
| **PERCENT_TOTAL** | Percentage of root | $\frac{\|S\|}{\|R\|} \times 100\%$ | Relative abundance in experiment |
| **PERCENT_GATED** | Percentage of all gated events | $\frac{\|S\|}{\|G\|} \times 100\%$ | Relative abundance in analysis |
| **MIN** | Minimum value | $\min(S)$ | Lower bound |
| **MAX** | Maximum value | $\max(S)$ | Upper bound |

### Statistics Computation API

```python
@dataclass
class StatDefinition:
    """Defines what statistic to compute."""
    stat_type: StatType                  # MEAN, MEDIAN, CV, etc.
    parameter: str | None = None         # Channel name (None for COUNT)
    population_node_id: str | None = None  # Target population
    parent_node_id: str | None = None    # For percentage calculations

@dataclass
class StatResult:
    """Computed statistic result."""
    definition: StatDefinition
    value: float                         # Raw numeric value
    formatted: str                       # Human-readable (e.g., "1.23e4 MFI")

def compute_statistic(
    events: pd.DataFrame,
    stat_def: StatDefinition,
    parent_events: pd.DataFrame | None = None,
    total_events: pd.DataFrame | None = None
) -> StatResult:
    """Compute single statistic."""
    ...
```

### Example Statistic Computation

```python
# Get mean CD4 intensity for CD4+ population
stat = compute_statistic(
    events=gated_cd4_events,
    stat_def=StatDefinition(
        stat_type=StatType.MEAN,
        parameter='CD4-PE',
        population_node_id='CD4_population'
    )
)
print(f"Mean CD4 MFI: {stat.formatted}")  # Output: "Mean CD4 MFI: 5.23e4"
```

---

## 3. Compensation Engine (`analysis/compensation.py`)

Spectral overlap correction using **median-ratio spillover matrix method** (Roederer 2001).

### Algorithm: Spillover Matrix Computation

```python
def calculate_spillover_matrix(
    single_stain_samples: dict[str, FCSData],  # {detector: FCSData}
    unstained: FCSData | None = None,
    use_median: bool = True
) -> CompensationMatrix:
    """Compute spillover matrix from single-stain controls."""
```

**Process:**

1. **Background Subtraction (Optional):**
   - If `unstained` provided, compute per-channel median.
   - Subtract from all single-stain medians for background correction.

2. **Spillover Ratio Computation:**
   - For each single-stain control $s_c$:
     - Identify **primary detector** $d_p$ (highest median after background).
     - For each detector $d_j$:
       - $\text{spillover}[d_p][d_j] = \frac{\text{median}_{\text{singlestain}}(d_j)}{\text{median}_{\text{singlestain}}(d_p)}$
   
3. **Diagonal Normalization:**
   - Set $\text{spillover}[i][i] = 1.0$ (no self-spillover).

4. **Matrix Inversion:**
   - $M_{\text{comp}} = M_{\text{spillover}}^{-1}$
   - Apply via: $\text{compensated} = \text{raw} \times M_{\text{comp}}^T$

### Spillover Matrix Dataclass

```python
@dataclass
class CompensationMatrix:
    """Spillover matrix and metadata."""
    matrix: np.ndarray              # N×N compensation matrix
    channel_names: list[str]        # Column/row labels
    source: str                     # 'single_stain' | 'embedded' | 'manual'
    single_stain_medians: dict[str, float] | None = None  # Backup
```

### Example Usage

```python
# Load single-stain FCS files
singlestain = {
    'FITC': load_fcs('FITC_control.fcs'),
    'PE': load_fcs('PE_control.fcs'),
    'APC': load_fcs('APC_control.fcs'),
}
unstained = load_fcs('unstained_control.fcs')

# Compute spillover matrix
comp_matrix = calculate_spillover_matrix(
    single_stain_samples=singlestain,
    unstained=unstained
)

# Apply compensation
compensated_events = raw_events @ comp_matrix.matrix.T
```

---

## 4. Transform Algorithms (`analysis/transforms.py`)

### Transform Type Definitions

#### LINEAR Transform
$$y = x$$
Identity transformation; no scaling applied.

#### LOG10 Transform
$$y = \frac{\log_{10}(\max(x, \text{min\_value}))}{\text{decades}}$$

**Parameters:**
- `min_value`: Floor to prevent log(0) or log(negative). Default: 0.01.
- `decades`: Display range in orders of magnitude. Default: 4 (display 0.01 → 10,000).

**Use:** Scatter channels (FSC, SSC), some fluorescence measurements with wide dynamic range.

#### BIEXPONENTIAL Transform (Logicle, Parks 2006)

**Mathematical Foundation:**  
Blends linear transformation near zero with logarithmic scaling for large values, enabling visualization of negative populations (e.g., autofluorescence-subtracted data) and positive populations simultaneously.

**Parameters:**
- **T** (`logicle_t`): Top value; maximum parameter value. Default: 262,144.0 (18-bit ADC).
- **W** (`logicle_w`): Width of linear region (in decades). Default: 1.0.
- **M** (`logicle_m`): Display decades (log range). Default: 4.5.
- **A** (`logicle_a`): Additional decades for negative values. Default: 0.0.

**Conceptual Breakdown:**
```
x < 0          :  Linear region (enables negative population plotting)
0 ≤ x ≤ T      :  Blend of linear + logarithmic
x > T          :  Logarithmic (compressed)
```

**Implementation:**  
The module delegates to `flowutils` C-extension (`flowkit.transforms.logicle()`), which implements the original Parks algorithm. Fallback: high-fidelity `np.arcsinh()` approximation.

```python
def biexponential_transform(
    data: np.ndarray,
    top: float = 262144.0,
    width: float = 1.0,
    positive: float = 4.5,
    negative: float = 0.0
) -> np.ndarray:
    """Apply Parks 2006 Logicle transform."""
    # Internally calls flowkit.transforms.logicle() via C-extension
    # Falls back to asinh if unavailable
```

**Use:** Fluorescence channels (all detector types); enables publication-ready visualization per modern flow cytometry standards.

---

## 5. Auto-Ranging Algorithm (`analysis/scaling.py`)

Computes robust axis display ranges based on event distribution, excluding outliers.

### `AxisScale` Dataclass

```python
@dataclass
class AxisScale:
    """Axis transformation and display configuration."""
    transform_type: TransformType           # LINEAR, LOG, BIEXPONENTIAL
    min_val: float | None = None            # Manual lower display bound
    max_val: float | None = None            # Manual upper display bound
    logicle_t: float = 262144.0             # Logicle T parameter
    logicle_w: float = 1.0                  # Logicle W parameter
    logicle_m: float = 4.5                  # Logicle M parameter
    logicle_a: float = 0.0                  # Logicle A parameter
    outlier_percentile: float = 0.1         # Outlier rejection threshold
```

### Auto-Ranging Algorithm

```python
def calculate_auto_range(
    data: np.ndarray,
    axis_scale: AxisScale,
    outlier_percentile: float = 0.1
) -> tuple[float, float]:
    """Compute robust display range excluding outliers."""
    
    # Step 1: Compute percentile boundaries
    lower_percentile = outlier_percentile / 2          # Default: 0.05%
    upper_percentile = 100 - lower_percentile          # Default: 99.95%
    
    p_lower = np.percentile(data, lower_percentile)
    p_upper = np.percentile(data, upper_percentile)
    
    # Step 2: Apply transform (preview display space)
    if axis_scale.transform_type == TransformType.LINEAR:
        display_min = p_lower
        display_max = p_upper
    
    elif axis_scale.transform_type == TransformType.LOG:
        display_min = np.log10(max(p_lower, 0.01))
        display_max = np.log10(p_upper) if p_upper > 0 else 4
    
    elif axis_scale.transform_type == TransformType.BIEXPONENTIAL:
        # Apply Logicle with extended range
        display_min = logicle_transform(p_lower, axis_scale.logicle_t,
                                        axis_scale.logicle_w, axis_scale.logicle_m - 1,
                                        axis_scale.logicle_a)
        display_max = logicle_transform(p_upper, axis_scale.logicle_t,
                                        axis_scale.logicle_w, axis_scale.logicle_m,
                                        axis_scale.logicle_a)
    
    return display_min, display_max
```

**Example:**
```python
# Auto-range for CD4-PE (fluorescence channel)
scale = AxisScale(transform_type=TransformType.BIEXPONENTIAL,
                   logicle_m=4.5, logicle_t=262144.0)
cd4_min, cd4_max = calculate_auto_range(cd4_events, scale, outlier_percentile=0.1)
# Typical output: cd4_min ≈ -0.5, cd4_max ≈ 4.8 (display space)
```

---

## 6. Service Layer Contracts (`analysis/protocols.py`)

Services are defined via **Protocol** interfaces (Python's structural subtyping), enabling loose coupling and dependency inversion.

### `IGateCoordinator` Protocol

```python
@runtime_checkable
class IGateCoordinator(Protocol):
    """Facade for all gating operations."""
    
    def add_gate(
        self,
        sample_id: str,
        gate: Gate,
        parent_node_id: str | None = None,
        name: str | None = None
    ) -> str:
        """Add gate to population tree. Returns node ID."""
        ...
    
    def remove_gate(self, sample_id: str, node_id: str) -> None:
        """Remove population and children."""
        ...
    
    def modify_gate(
        self,
        sample_id: str,
        node_id: str,
        updates: dict[str, Any]
    ) -> None:
        """Update gate parameters (position, size, etc.)."""
        ...
    
    def rename_gate(self, sample_id: str, node_id: str, new_name: str) -> None:
        """Rename population."""
        ...
    
    def add_connection(
        self,
        sample_id: str,
        child_node_id: str,
        parent_node_id: str
    ) -> None:
        """Wire child to additional parent (boolean logic)."""
        ...
```

### `IPopulationService` Protocol

```python
@runtime_checkable
class IPopulationService(Protocol):
    """Read-only population tree queries."""
    
    def get_population_node(
        self,
        sample_id: str,
        node_id: str
    ) -> GateNode | None:
        """Retrieve population node."""
        ...
    
    def get_gated_events(
        self,
        sample_id: str,
        node_id: str
    ) -> pd.DataFrame:
        """Get filtered events for population."""
        ...
    
    def iter_children(
        self,
        sample_id: str,
        parent_node_id: str
    ) -> Iterator[GateNode]:
        """Iterate child populations."""
        ...
    
    def get_population_statistics(
        self,
        sample_id: str,
        node_id: str
    ) -> dict[str, float]:
        """Get cached statistics."""
        ...
```

---

## 7. Key Classes Reference

### `GateNode` (Hierarchical Population)

```python
@dataclass
class GateNode:
    """Population node in DAG."""
    node_id: str
    name: str
    gate: Gate | None              # None for root "All Events"
    children: list[GateNode]
    parents: list[GateNode]        # Multi-parent support (DAG)
    negated: bool = False           # Logical NOT
    logic_operator: str = 'AND'     # 'AND' or 'OR'
    statistics: dict[str, float] = field(default_factory=dict)
    creation_view: dict = field(default_factory=dict)  # Recording display state
```

### `FCSData` (Flow Cytometry Sample)

```python
@dataclass
class FCSData:
    """FCS file parsed data wrapper."""
    file_path: str
    channels: list[str]             # Detector names
    markers: list[str]              # Biological marker names
    events: pd.DataFrame            # Numeric event data (N × P)
    metadata: dict[str, Any]        # FCS keywords
    is_compensated: bool = False
    original_events: pd.DataFrame | None = None  # Pre-compensation backup
```

### `Experiment` (Complete Analysis Session)

```python
@dataclass
class Experiment:
    """Top-level experiment container."""
    samples: dict[str, Sample]      # {sample_id: Sample}
    groups: dict[str, Group]        # {group_id: Group}
    templates: dict[str, WorkflowTemplate]
    channel_scales: dict[str, AxisScale]  # Shared axis configurations
```

---

## 8. References & Further Reading

- **[Architecture Overview](./00_ARCHITECTURE_OVERVIEW.md)**: Module design, service orchestration, data flow.
- **[Services & Dependency Injection](./04_SERVICES_AND_DEPENDENCY_INJECTION.md)**: Complete service layer documentation.
- **[Gating & Compensation Deep Dive](./05_GATING_AND_COMPENSATION_DEEP_DIVE.md)**: Detailed algorithms.
- **[Transforms & Scaling](./06_TRANSFORMS_AND_SCALING.md)**: Mathematical transform details.
- **[UI Engine & Rendering](./02_UI_ENGINE.md)**: Canvas architecture, FSM, rendering pipeline.
- **[Testing & Quality Assurance](./03_TESTING_AND_QA.md)**: Test patterns and guidelines.

### Scientific References
- **Parks, D.R., et al. (2006).** "A new 'Logicle' display method permits expanded and more intuitive graphical representation of flow cytometry data." *Cytometry Part A*, 69A(6), 541-551. DOI: [10.1002/cyto.a.20258](https://doi.org/10.1002/cyto.a.20258)
- **Roederer, M. (2001).** "Spectral compensation for flow cytometry: Visualization artifacts, limitations, and caveats." *Cytometry*, 45(3), 194-205. DOI: [10.1002/1097-0320(20011101)45:3<194::AID-CYTO1163>3.0.CO;2-C](https://doi.org/10.1002/1097-0320(20011101)45:3<194::AID-CYTO1163>3.0.CO;2-C)
- **FlowKit**: [GitHub - whitews/FlowKit](https://github.com/whitews/FlowKit)
