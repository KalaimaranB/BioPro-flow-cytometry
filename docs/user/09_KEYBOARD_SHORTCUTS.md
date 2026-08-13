# Keyboard Shortcuts & Quick Reference

Complete list of keyboard shortcuts and quick access commands in Karcytics Flow Cytometry.

---

## Canvas Navigation

| Action | Shortcut | Description |
|--------|----------|-------------|
| Zoom In | **Scroll Up** or **+** | Enlarge plot view |
| Zoom Out | **Scroll Down** or **-** | Reduce plot view |
| Zoom to Fit | **Home** | Auto-fit plot to data range |
| Pan Left | **Left Arrow** | Shift view left |
| Pan Right | **Right Arrow** | Shift view right |
| Pan Up | **Up Arrow** | Shift view up |
| Pan Down | **Down Arrow** | Shift view down |
| Middle-Click Drag | (Mouse) | Free-form panning |
| Reset View | **R** | Return to default zoom/pan |

---

## Gate Editing

| Action | Shortcut | Description |
|--------|----------|-------------|
| Draw Rectangle Gate | **G** then **R** | Activate rectangle tool |
| Draw Polygon Gate | **G** then **P** | Activate polygon tool (click vertices) |
| Draw Ellipse Gate | **G** then **E** | Activate ellipse tool |
| Draw Quadrant Gate | **G** then **Q** | 4-way split gate |
| Draw Range Gate | **G** then **1** | 1D threshold gate |
| Move Gate | **M** | Activate move tool (drag gate) |
| Delete Gate | **Delete** or **Backspace** | Remove selected gate |
| Undo Gate | **Ctrl+Z** | Undo last gate edit |
| Redo Gate | **Ctrl+Y** | Redo last undone gate |
| Finish Polygon | **Right-Click** or **Enter** | Complete polygon vertex entry |
| Cancel Drawing | **Escape** | Cancel active gate drawing |

---

## Sample Selection

| Action | Shortcut | Description |
|--------|----------|-------------|
| Select Sample | (Double-Click in Tree) | Load sample onto canvas |
| Select Population | (Double-Click in Tree) | Filter canvas to population |
| Toggle Population | **Spacebar** | Show/hide selected population |
| Next Sample | **Tab** | Move to next sample in list |
| Previous Sample | **Shift+Tab** | Move to previous sample in list |

---

## Statistics & Export

| Action | Shortcut | Description |
|--------|----------|-------------|
| Export Statistics | **Ctrl+Shift+S** | Export current stats to CSV |
| Export Plot | **Ctrl+Shift+E** | Export plot (PNG/PDF) |
| Print | **Ctrl+P** | Print current plot |
| Copy Statistics | **Ctrl+C** | Copy stats table to clipboard |

---

## File Operations

| Action | Shortcut | Description |
|--------|----------|-------------|
| Open Workspace | **Ctrl+O** | Open existing workspace |
| Save Workspace | **Ctrl+S** | Save current workspace |
| Save As | **Ctrl+Shift+S** | Save workspace with new name |
| New Workspace | **Ctrl+N** | Create new blank workspace |
| Import Gates | **Ctrl+I** | Import gate definitions from file |
| Export Workspace | **Ctrl+E** | Export entire workspace (gates, stats, plots) |

---

## View Options

| Action | Shortcut | Description |
|--------|----------|-------------|
| Switch to Pseudocolor | **V** then **P** | Density plot view |
| Switch to Scatter | **V** then **S** | Dot plot view |
| Switch to Histogram | **V** then **H** | 1D distribution view |
| Switch to Contour | **V** then **C** | Contour plot view |
| Toggle Axis Labels | **Ctrl+L** | Show/hide axis text |
| Toggle Legend | **Ctrl+Shift+L** | Show/hide gate legend |
| Show Node Canvas | **Ctrl+N** | Display DAG visualization |
| Full Screen | **F11** | Maximize canvas view |

---

## Multi-Selection

| Action | Shortcut | Description |
|--------|----------|-------------|
| Select Multiple Gates | **Ctrl+Click** | Add gate to selection |
| Select All Gates | **Ctrl+A** | Select all populations |
| Deselect All | **Escape** | Clear selection |
| Toggle Selection | **Ctrl+Shift+Click** | Add/remove from selection |

---

## Ribbon Quick Access

| Ribbon | Shortcut | Notes |
|--------|----------|-------|
| Workspace | **W** | File/session management |
| Compensation | **C** | Spillover correction |
| Gating | **G** | Gate definition tools |
| Pipeline | **P** | Batch operations |
| Statistics | **S** | Stats/export view |
| Spectral | **Shift+S** | Advanced visualization |
| UMAP | **U** | Dimensionality reduction |

---

## Advanced Shortcuts

| Action | Shortcut | Description |
|--------|----------|-------------|
| Search Gates | **Ctrl+F** | Find population by name |
| Toggle Sidebar | **Ctrl+B** | Show/hide left sidebar |
| Toggle Properties | **Ctrl+P** | Show/hide right sidebar |
| Maximize Canvas | **Ctrl+M** | Maximize plot area |
| Settings | **Ctrl+,** | Open preferences |
| Help | **F1** | Open help documentation |

---

## Mouse Context Menus

**Right-Click in Sample Tree:**
- Rename population
- Delete population
- Export statistics
- Create group
- Edit sample role

**Right-Click on Canvas Gate:**
- Edit gate parameters
- Delete gate
- Rename gate
- Clone to other samples
- Create child gate

**Right-Click on Empty Canvas:**
- Create new gate
- Zoom to fit
- Export plot

---

## Quick Tips

**Pro Tip 1: Template Protocols**
- Set up gating strategy on one representative sample
- Save as template via **Pipeline** → **Save Template**
- Apply template to all samples: **Pipeline** → **Apply Template**

**Pro Tip 2: Batch Gating**
- Select all samples in group (Ctrl+A in Sample Tree)
- Draw gate on one sample
- Auto-propagates to all group samples (200ms debounce)

**Pro Tip 3: Statistics Export**
- Select multiple populations (Ctrl+Click)
- **Statistics** ribbon → **Export** → **CSV**
- All stats export side-by-side for easy comparison

---

## Related Documentation

- **[Getting Started](./01_GETTING_STARTED.md)**: Basic workflow tutorial
- **[Troubleshooting](./10_TROUBLESHOOTING.md)**: Common issues and solutions
