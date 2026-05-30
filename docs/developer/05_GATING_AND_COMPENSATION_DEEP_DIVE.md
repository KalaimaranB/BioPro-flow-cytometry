# Gating & Compensation Deep Dive

This document provides exhaustive technical details on the gate evaluation engine (DAG with Boolean logic), all 8 gate types with mathematical proofs, and the spillover matrix compensation algorithm.

---

## 1. Directed Acyclic Graph (DAG) Gating Architecture

### Why DAG Instead of Trees?

Traditional commercial flow cytometers use **hierarchical trees** where each population has exactly one parent. This model is insufficient for modern analysis:

```
Tree Limitation: CD4+ cells defined in isolation
    Lymphocytes
    ├── CD4+                              # Can only reference "Lymphocytes" as parent
    └── CD8+
```

```
DAG Solution: Boolean logic combining multiple populations
    Lymphocytes
    ├── CD4+
    ├── Singlets
    └── Live Cells
    
    CD4+ Viable = CD4+ ∩ Singlets ∩ Live Cells
                  (3 parents, computed via Boolean AND)
```

**Mathematical Formulation:**  
Let $P_i$ denote populations (nodes) and $e \in E$ denote events. A DAG node $N_j$ is gated via:
$$N_j(e) = G(e) \wedge \bigwedge_{i \in \text{parents}(j)} N_i(e)$$

where $G$ is the geometric gate function (Rectangle, Polygon, etc.) and $\wedge$ is the Boolean AND operator.

---

### DAG Evaluation Algorithm

The `DagEvaluator` computes all population gates using **topological sort** to respect parent dependencies:

```python
class DagEvaluator:
    """Evaluate population gates in correct dependency order."""
    
    def evaluate(self, events: pd.DataFrame) -> dict[str, np.ndarray[bool]]:
        """
        Evaluate all nodes in DAG.
        
        Args:
            events: N × P DataFrame of events
        
        Returns:
            {node_id: boolean_mask} for each node
        """
        # Step 1: Topological sort (Kahn's algorithm)
        in_degree = self._compute_in_degree()
        queue = deque([n for n in nodes if in_degree[n] == 0])
        sorted_nodes = []
        
        while queue:
            node = queue.popleft()
            sorted_nodes.append(node)
            
            for child in node.children:
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)
        
        # Verify no cycles
        if len(sorted_nodes) < len(nodes):
            raise ValueError("DAG contains cycles!")
        
        # Step 2: Evaluate in order
        masks = {}
        
        for node in sorted_nodes:
            if node.is_root:
                # Root "All Events" node
                masks[node.id] = np.ones(len(events), dtype=bool)
            else:
                # Evaluate gate
                gate_mask = node.gate.contains(events)  # Gate's geometric mask
                
                # Combine parent masks via Boolean logic
                parent_masks = [masks[p.id] for p in node.parents]
                
                if node.logic_operator == 'AND':
                    # Intersection of parent populations
                    combined_mask = np.logical_and.reduce(parent_masks)
                elif node.logic_operator == 'OR':
                    # Union of parent populations
                    combined_mask = np.logical_or.reduce(parent_masks)
                else:
                    raise ValueError(f"Unknown operator: {node.logic_operator}")
                
                # Apply negation if specified
                if node.negated:
                    combined_mask = ~combined_mask
                
                # Final mask: parent populations AND gate geometry
                masks[node.id] = combined_mask & gate_mask
        
        return masks
    
    def _compute_in_degree(self) -> dict:
        """Count parent dependencies for each node."""
        in_degree = {n: len(n.parents) for n in self.nodes}
        return in_degree
```

**Time Complexity:** $O(n + m + N \cdot m)$
- $n$ = number of nodes
- $m$ = edges (parent-child relationships)
- $N$ = number of events
- Topological sort: $O(n + m)$
- Gate evaluation: $O(N \cdot m)$ (per-event geometric tests)

**Example Evaluation:**

```
Sample: 100,000 events
Gates:
    All Events (root)
    ├── Lymphocytes (Rectangle on FSC, SSC)
    ├── Singlets (Rectangle on FSC-A, FSC-H)
    ├── Live (Range on Viability dye)
    └── CD4+ Viable (Boolean: Lymphocytes ∩ Singlets ∩ Live)

Topological Sort Order:
    [All Events, Lymphocytes, Singlets, Live, CD4+ Viable]

Evaluation:
    1. All Events mask:        [T, T, T, ..., T]  (100,000 true)
    2. Lymphocytes mask:       [T, F, T, ..., F]  (80,000 true)
    3. Singlets mask:          [T, T, F, ..., T]  (75,000 true)
    4. Live mask:              [T, T, T, ..., F]  (95,000 true)
    5. CD4+ Viable mask:
       = Lymphocytes ∩ Singlets ∩ Live
       = [T, F, F, ..., F]     (60,000 true)
```

---

## 2. Boolean Logic Operations

### AND Gate (Intersection)

**Definition:** Population includes events that pass ALL parent populations AND the gate geometry.

$$N_{\text{AND}}(e) = G(e) \wedge \left(\bigcap_{p \in \text{parents}} N_p(e)\right)$$

**Example: CD4+ Viable T cells**
```
Parents: {CD4+, Live, Singlets}
Gate: Additional marker threshold (e.g., CD45+)

Result = CD4+ ∩ Live ∩ Singlets ∩ CD45+
```

**Use Cases:**
- Combining independent gating criteria
- Multi-marker phenotyping
- Quality filtering (Live ∩ Singlets ∩ hCD45+)

### OR Gate (Union)

**Definition:** Population includes events that pass ANY parent population AND the gate geometry.

$$N_{\text{OR}}(e) = G(e) \wedge \left(\bigcup_{p \in \text{parents}} N_p(e)\right)$$

**Example: Pan T-cell Population**
```
Parents: {CD4+, CD8+}
Gate: CD3+ marker threshold

Result = (CD4+ ∪ CD8+) ∩ CD3+
```

**Use Cases:**
- Combining mutually exclusive populations (quadrants Q1 | Q2 | Q3 | Q4)
- Flexible population definitions

### NOT Gate (Negation)

**Definition:** Population includes events OUTSIDE the specified population.

$$N_{\text{NOT}}(e) = \neg N_{\text{parent}}(e) \cap G(e)$$

**Example: Negative Cells**
```
Parent: CD4+ population
Negation: ON

Result = All Events - CD4+
```

**Use Cases:**
- Double-negative populations (CD4- CD8-)
- Exclusion gates (Non-B cells)

---

## 3. All 8 Gate Types with Mathematical Formulas

### 1. RectangleGate (2D Box)

**Mathematical Definition:**
$$G(x, y) = \begin{cases} 1 & \text{if } x_{\min} \leq x \leq x_{\max} \text{ AND } y_{\min} \leq y \leq y_{\max} \\ 0 & \text{otherwise} \end{cases}$$

**Implementation:**
```python
class RectangleGate(Gate):
    def contains(self, events: pd.DataFrame) -> np.ndarray[bool]:
        x_mask = (events[self.x_param] >= self.x_min) & (events[self.x_param] <= self.x_max)
        y_mask = (events[self.y_param] >= self.y_min) & (events[self.y_param] <= self.y_max)
        return x_mask & y_mask
```

**Performance:** O(N) — single pass, vectorized.

**Visual Example:**
```
        SSC-A
         │
    ┌────┴────┐
    │          │ y_max
    │ ┌──────┐ │
    │ │      │ │ Lymphocyte gate
    │ │      │ │
    │ └──────┘ │
    │          │ y_min
    └──────────┴─────────── FSC-A
             x_min x_max
```

---

### 2. PolygonGate (Free-Form N-Gon)

**Mathematical Definition:**  
Uses **Cross-Product Ray Casting** (winding number algorithm):

For point $P$ and polygon vertices $V_0, V_1, ..., V_n$:
$$\text{Inside} = \left| \sum_{i=0}^{n} \text{sign}\left((V_{i+1} - V_i) \times (P - V_i)\right) \right| > 0$$

where $\times$ denotes 2D cross product: $(a, b) \times (c, d) = ad - bc$.

**Implementation:**
```python
class PolygonGate(Gate):
    def contains(self, events: pd.DataFrame) -> np.ndarray[bool]:
        x_vals = events[self.x_param].values
        y_vals = events[self.y_param].values
        
        inside = np.zeros(len(events), dtype=bool)
        
        for i, (x, y) in enumerate(zip(x_vals, y_vals)):
            winding_number = 0
            
            for j in range(len(self.vertices)):
                v1 = self.vertices[j]
                v2 = self.vertices[(j + 1) % len(self.vertices)]
                
                # Cross product to determine side
                cross = (v2[0] - v1[0]) * (y - v1[1]) - (v2[1] - v1[1]) * (x - v1[0])
                
                if cross > 0:
                    winding_number += 1
                elif cross < 0:
                    winding_number -= 1
            
            inside[i] = winding_number != 0
        
        return inside
```

**Performance:** O(N × M) where M = number of vertices.

**Optimization:** Use NumPy vectorization for batch processing:
```python
# Vectorized version
X = events[self.x_param].values[:, np.newaxis]  # N × 1
Y = events[self.y_param].values[:, np.newaxis]  # N × 1

# Compute cross product for all events and all edges
crosses = np.zeros((len(events), len(self.vertices)))
for j in range(len(self.vertices)):
    v1, v2 = self.vertices[j], self.vertices[(j + 1) % len(self.vertices)]
    crosses[:, j] = (v2[0] - v1[0]) * (Y - v1[1]) - (v2[1] - v1[1]) * (X - v1[0])

winding = np.sum(np.sign(crosses), axis=1)
return winding != 0
```

**Visual Example:**
```
        Vertices: [(10, 20), (30, 10), (40, 40), (15, 35)]
        
             (40,40)
            /      \
           /        \
       (15,35)      (30,10)
          \        /
           \      /
          (10,20)
        
        Events inside polygon:
        P1 = (25, 25): Inside (winding # ≠ 0)
        P2 = (5, 5):   Outside (winding # = 0)
```

---

### 3. EllipseGate (Rotated 2D Ellipse)

**Mathematical Definition:**  
Standard ellipse with rotation:
$$\left(\frac{x - c_x}{a} \cos\theta + \frac{y - c_y}{b} \sin\theta\right)^2 + \left(-\frac{x - c_x}{a} \sin\theta + \frac{y - c_y}{b} \cos\theta\right)^2 \leq 1$$

where:
- $(c_x, c_y)$ = center
- $a = \text{width}/2$ = semi-major axis
- $b = \text{height}/2$ = semi-minor axis
- $\theta$ = rotation angle

**Implementation:**
```python
class EllipseGate(Gate):
    def contains(self, events: pd.DataFrame) -> np.ndarray[bool]:
        x = events[self.x_param].values
        y = events[self.y_param].values
        
        # Translate to center
        x_centered = x - self.center[0]
        y_centered = y - self.center[1]
        
        # Rotate
        angle_rad = np.radians(self.angle)
        cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)
        
        x_rot = x_centered * cos_a + y_centered * sin_a
        y_rot = -x_centered * sin_a + y_centered * cos_a
        
        # Ellipse equation
        a = self.width / 2
        b = self.height / 2
        
        ellipse_dist = (x_rot / a) ** 2 + (y_rot / b) ** 2
        
        return ellipse_dist <= 1.0
```

**Performance:** O(N) — single pass, vectorized.

**Visual Example:**
```
        Center: (50, 50)
        Width: 30 (a=15), Height: 20 (b=10)
        Angle: 45°
        
              45°
              /
        (50,50) ●
           /    \
          /      \
         ●────────●
        
        Inside: Points ≤ ellipse boundary
        Outside: Points > ellipse boundary
```

---

### 4. RangeGate (1D Single-Parameter)

**Mathematical Definition:**
$$G(x) = \begin{cases} 1 & \text{if } x_{\min} \leq x \leq x_{\max} \\ 0 & \text{otherwise} \end{cases}$$

**Implementation:**
```python
class RangeGate(Gate):
    def contains(self, events: pd.DataFrame) -> np.ndarray[bool]:
        x = events[self.param].values
        return (x >= self.min_val) & (x <= self.max_val)
```

**Performance:** O(N) — single pass.

**Use Cases:**
- Viability gating (low dye intensity = live)
- Area vs. height filtering (FSC-A / FSC-H ratio)
- Threshold-based exclusion

---

### 5. QuadrantGate (Automatic 4-Quadrant Split)

**Mathematical Definition:**  
Creates 4 mutually exclusive quadrants at split point:

$$Q_1 = \{(x, y) : x \geq x_{\text{mid}} \land y \geq y_{\text{mid}}\}$$
$$Q_2 = \{(x, y) : x < x_{\text{mid}} \land y \geq y_{\text{mid}}\}$$
$$Q_3 = \{(x, y) : x < x_{\text{mid}} \land y < y_{\text{mid}}\}$$
$$Q_4 = \{(x, y) : x \geq x_{\text{mid}} \land y < y_{\text{mid}}\}$$

**Implementation:**
```python
class QuadrantGate(Gate):
    def contains(self, events: pd.DataFrame) -> np.ndarray[bool]:
        # Note: Base QuadrantGate itself doesn't filter;
        # instead, it creates 4 QuadrantSubGate children
        return np.ones(len(events), dtype=bool)

class QuadrantSubGate(Gate):
    def contains(self, events: pd.DataFrame) -> np.ndarray[bool]:
        x = events[self.x_param].values
        y = events[self.y_param].values
        
        x_cond = x >= self.x_mid if self.quadrant in [1, 4] else x < self.x_mid
        y_cond = y >= self.y_mid if self.quadrant in [1, 2] else y < self.y_mid
        
        return x_cond & y_cond
```

**Automatic Child Creation:**  
When a `QuadrantGate` is added, the system auto-generates 4 `QuadrantSubGate` children.

**Visual Example:**
```
            y_mid
              │
        ┌─────┼─────┐
        │ Q2  │ Q1  │
    y   │─────●─────│
        │ Q3  │ Q4  │
        └─────┼─────┘
              x_mid ──→ x

Example: CD4/CD8 Quadrant
    Q1: CD4+ CD8+  (upper-right)
    Q2: CD4- CD8+  (upper-left)
    Q3: CD4- CD8-  (lower-left)
    Q4: CD4+ CD8-  (lower-right)
```

---

### 6. SubsetGate (Parent Reference)

**Mathematical Definition:**
$$G_{\text{subset}}(e) = N_{\text{parent}}(e)$$

Filtering is purely from parent population; no geometric gate applied.

**Implementation:**
```python
class SubsetGate(Gate):
    parent_node_id: str
    
    def contains(self, events: pd.DataFrame) -> np.ndarray[bool]:
        # This is handled by DAG evaluator via parent reference
        # Base implementation: pass-through
        return np.ones(len(events), dtype=bool)
```

**Use Case:** Explicit subset definition in Boolean logic DAG.

---

### 7 & 8. QuadrantSubGate (Auto-Generated from QuadrantGate)

See section 5 above; automatically created as children of `QuadrantGate`.

---

## 4. Spillover Matrix Compensation Algorithm

### Background: Spectral Overlap

In modern flow cytometry, multiple fluorophores are excited by the same laser. Each fluorophore emits light into multiple detectors:

```
Laser (488nm)
│
├─→ FITC      Emits → BL1, BL2, YL1 (spillover)
├─→ PE        Emits → YL1, YL2, RL1 (spillover)
└─→ PerCP     Emits → RL1, RL2 (spillover)
```

**Raw measured fluorescence = True signal + Spillover from other fluorophores**

**Goal:** Remove spillover to recover true signal.

### Roederer Median-Ratio Method (2001)

**Algorithm:**

1. **Single-Stain Controls:** One sample per fluorophore (only that fluorophore labeled).

2. **Background Subtraction (Optional):**
   - Unstained control provides baseline autofluorescence.
   - Subtract median of unstained from each single-stain median.

3. **Spillover Ratio Computation:**
   ```
   For each single-stain sample S with fluorophore F:
     primary_detector = argmax(median(detector_i))
     
     For each detector D:
       spillover[primary][D] = median(S[D]) / median(S[primary])
   ```

4. **Diagonal Normalization:**
   ```
   spillover[i][i] = 1.0  (100% of signal in primary detector)
   ```

5. **Matrix Inversion:**
   ```
   compensation_matrix = inverse(spillover_matrix)
   ```

6. **Application:**
   ```
   compensated_events = raw_events @ compensation_matrix.T
   ```

### Mathematical Formulation

**Spillover Matrix $S$:**
$$S_{ij} = \frac{\text{median}_{\text{single-stain}_i}(D_j)}{\text{median}_{\text{single-stain}_i}(D_i)}$$

where $D_i$ is detector $i$ and $S$ is N×N (N = number of detectors).

**Example 3×3 Matrix (FITC, PE, PerCP):**
```
         FITC   PE   PerCP
FITC  [  1.0  0.02  0.01  ]  = spillover
PE    [  0.05 1.0   0.03  ]
PerCP [  0.01 0.05  1.0   ]

Then:
         FITC   PE    PerCP
FITC  [  1.03 -0.02 -0.01 ]
PE    [ -0.05  1.04 -0.03 ]     = inverse(spillover)
PerCP[ -0.01 -0.05  1.01  ]
```

**Apply Compensation:**
$$\text{Compensated} = \text{Raw} \times \text{Compensation}^T$$

### Implementation

```python
def calculate_spillover_matrix(
    single_stain_samples: dict[str, Sample],
    unstained: Sample | None = None
) -> np.ndarray:
    """
    Compute spillover matrix from single-stain controls.
    
    Args:
        single_stain_samples: {detector_name: Sample}
        unstained: Background control (optional)
    
    Returns:
        N×N spillover matrix
    """
    detectors = list(single_stain_samples.keys())
    n = len(detectors)
    spillover = np.zeros((n, n))
    
    # Background medians (if unstained provided)
    bg_medians = {}
    if unstained:
        for i, detector in enumerate(detectors):
            bg_medians[detector] = np.median(unstained.fcs_data.events[detector])
    else:
        bg_medians = {d: 0 for d in detectors}
    
    # Compute spillover ratios
    for i, (stain_name, sample) in enumerate(single_stain_samples.items()):
        events = sample.fcs_data.events
        
        # Background-corrected medians
        medians = {}
        for j, detector in enumerate(detectors):
            raw_median = np.median(events[detector])
            medians[detector] = max(raw_median - bg_medians[detector], 1e-4)
        
        # Identify primary detector (highest median)
        primary_idx = np.argmax([medians[d] for d in detectors])
        primary = detectors[primary_idx]
        
        # Compute spillover ratios
        for j, detector in enumerate(detectors):
            spillover[primary_idx, j] = medians[detector] / medians[primary]
    
    return spillover

def compensate_events(
    events: pd.DataFrame,
    detectors: list[str],
    spillover_matrix: np.ndarray
) -> pd.DataFrame:
    """
    Apply compensation matrix to events.
    
    Args:
        events: N × P DataFrame
        detectors: List of detector names
        spillover_matrix: N × N matrix
    
    Returns:
        Compensated events DataFrame
    """
    # Invert spillover matrix
    comp_matrix = np.linalg.inv(spillover_matrix)
    
    # Extract detector columns
    X = events[detectors].values  # N × N array
    
    # Apply: compensated = raw @ comp_matrix.T
    compensated = X @ comp_matrix.T
    
    # Create output DataFrame
    result = events.copy()
    for i, detector in enumerate(detectors):
        result[detector] = compensated[:, i]
    
    return result
```

### Example Compensation Workflow

```python
# Load controls
fitc_control = load_fcs('FITC_control.fcs')  # Only FITC-labeled
pe_control = load_fcs('PE_control.fcs')      # Only PE-labeled
percpe_control = load_fcs('PerCP_control.fcs')  # Only PerCP-labeled
unstained_control = load_fcs('unstained.fcs')

# Compute spillover
single_stains = {
    'FITC': fitc_control,
    'PE': pe_control,
    'PerCP': percpe_control
}

spillover = calculate_spillover_matrix(single_stains, unstained_control)
print("Spillover Matrix:\n", spillover)

# Example output:
# [[ 1.     0.015  0.008]
#  [ 0.042  1.     0.028]
#  [ 0.005  0.038  1.   ]]

# Apply to experimental sample
sample = load_fcs('experimental_sample.fcs')
detectors = ['FITC', 'PE', 'PerCP']
compensated = compensate_events(sample.events, detectors, spillover)

# Result: Spillover removed from experimental data
print(f"Before: {sample.events['FITC'].mean():.0f}")
print(f"After:  {compensated['FITC'].mean():.0f}")
```

---

## 5. Performance Optimizations

### Vectorization

All gate evaluation uses NumPy vectorization to process millions of events efficiently:

```python
# Naive: O(N) with Python loop
mask = []
for event in events:
    mask.append(event[x_param] >= x_min and event[x_param] <= x_max)

# Optimized: O(N) with NumPy (100x faster on large N)
mask = (events[x_param] >= x_min) & (events[x_param] <= x_max)
```

### DAG Caching

Statistics are computed once during `DAG Evaluation` and cached in `GateNode.statistics`:
```python
node.statistics = {
    'count': gated_event_count,
    'percent_parent': percentage,
    'mean_mfi': median_intensity,
    ...
}
```

On subsequent queries, retrieve from cache without re-evaluation.

### Invalidation Strategy

Cache is invalidated when:
1. Gate geometry changes (user moves/resizes).
2. Parent population modified.
3. Compensation applied.
4. Axis transform changed.

---

## References

- **Parks, D.R., et al. (2006).** *Cytometry Part A*, 69A(6), 541-551. [DOI: 10.1002/cyto.a.20258](https://doi.org/10.1002/cyto.a.20258)
- **Roederer, M. (2001).** *Cytometry*, 45(3), 194-205. [DOI: 10.1002/1097-0320(20011101)45:3](https://doi.org/10.1002/1097-0320(20011101)45:3)
- **Ormerod, M. (Ed., 2015).** *Flow Cytometry: A Practical Approach* (4th ed.). Oxford University Press.
