# Troubleshooting Guide

Common issues, error messages, and solutions for BioPro Flow Cytometry analysis.

---

## Data Loading Issues

### Issue: "FCS File Not Found" or "Permission Denied"

**Symptoms:** Error when trying to open FCS file.

**Solutions:**
1. Verify file path is correct (no typos)
2. Check file permissions: right-click file → Properties → Security
3. Ensure file is not locked by another application
4. Try copying file to project `assets/data/` folder
5. On network drives, verify network connection is active

---

### Issue: "Unrecognized FCS Format"

**Symptoms:** "Error parsing FCS header" when loading file.

**Solutions:**
1. Verify file is actually FCS format (not renamed TXT/CSV)
2. Check FCS version compatibility:
   - Supported: FCS 2.0, 3.0, 3.1
   - Unsupported: FCS 1.0 (too old), FCS 4.0 (not yet supported)
3. Download latest FlowKit: `pip install -U flowkit`
4. Try opening with FlowJo or other software to verify file validity
5. Contact instrument core if file corruption suspected

---

### Issue: "Dataset Too Large" or "Out of Memory"

**Symptoms:** Slowness or crash when loading dataset > 5M events.

**Solutions:**
1. Reduce dataset size:
   - **Workspace** ribbon → **Downsample** → select 50% or 10%
   - Or: Use instrument software to gate before export
2. Close other applications to free RAM
3. Switch to "Fast Preview" rendering:
   - **Workspace** ribbon → **Presets** → **Fast Preview**
   - Reduces bin resolution for speed
4. Upgrade system RAM if persistent (recommend ≥16GB)

---

## Visualization Issues

### Issue: "Empty Plot" or "No Events Displayed"

**Symptoms:** Canvas shows blank plot despite data loaded.

**Possible Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Wrong axis selected | Check X/Y parameter selectors at bottom/left of canvas |
| Data out of display range | Click **View** → **Auto-Zoom** to fit data |
| Gate too restrictive | Select parent population in Sample Tree (e.g., "All Events") |
| Transform mismatch | Try different transform (Linear, Log, Logicle) in Properties |
| Compensation not applied | If using compensated data, verify spillover matrix loaded |

> [!TIP]
> Click **Properties** (right panel) → Check "Current Axis" section to verify selected parameters.

---

### Issue: "Plot Rendering is Very Slow"

**Symptoms:** Plot takes > 10 seconds to update after any action.

**Solutions:**
1. **Reduce quality for speed:**
   - **Workspace** ribbon → **Presets** → **Fast Preview**
   - Or manually reduce "Bins" slider in Workspace settings

2. **Check dataset size:**
   - If > 10M events, downsample (see above)
   - Or use scatter plot instead of pseudocolor

3. **Close other applications** to free CPU/GPU

4. **Restart BioPro** to clear memory leaks

5. **Update GPU drivers** if using graphics acceleration

---

### Issue: "Gates Not Visible on Plot"

**Symptoms:** Drew gate but can't see overlay on canvas.

**Solutions:**
1. Check Properties panel → "Show Gate Overlays" is enabled
2. Verify gate is in same population hierarchy as displayed plot
3. Gate may be outside current zoom/pan view:
   - Press **R** key or **Home** to reset view
   - Or click **View** → **Zoom to Fit**
4. Try toggling visibility: **View** → **Toggle Gate Visibility**

---

## Gating Issues

### Issue: "Gates Not Propagating to Other Samples"

**Symptoms:** Drew gate on one sample, but it doesn't appear on other samples in group.

**Solutions:**
1. Verify samples are in same **Group**:
   - **Groups Panel** (left) → drag samples to same group
2. Check auto-propagation setting:
   - **Gating** ribbon → **Auto-Propagate** should be ON
3. For manual propagation:
   - Select gate → **Gating** ribbon → **Propagate to Group**
4. Verify group assignment:
   - Select sample → **Properties** → look for group ID

---

### Issue: "Cannot Draw Gate" or "Gate Creation Fails"

**Symptoms:** Clicking gate tool does nothing; or error when trying to create gate.

**Solutions:**
1. Verify gate tool is active:
   - **Gating** ribbon → click desired gate type (Rectangle, Polygon, etc.)
   - Cursor should change to crosshair
2. Ensure you're drawing ON the canvas (not on labels/axes)
3. Try different gate type (if Rectangle doesn't work, try Polygon)
4. For polygon gates: right-click to finish (don't drag)
5. Verify selected parent population is valid:
   - Select population in Sample Tree before drawing

---

### Issue: "Gate Evaluation Error" or "Invalid Gate Parameters"

**Symptoms:** Gate created but shows error or doesn't filter events correctly.

**Solutions:**
1. Check gate bounds are within data range:
   - Verify X_min < X_max and Y_min < Y_max
   - Use **View** → **Auto-Zoom** to see full data range
2. For polygon gates: ensure vertices form valid shape (no self-intersecting edges)
3. For ellipse gates: ensure width/height > 0
4. Try recreating gate with slightly adjusted bounds

---

## Compensation Issues

### Issue: "Spillover Matrix Computation Failed"

**Symptoms:** "Error computing spillover" or "Singular matrix" error.

**Solutions:**
1. Verify you've assigned correct sample **Roles**:
   - Each single-stain control must have role = "Single-Stain"
   - Unstained must have role = "Unstained"
2. Check data quality:
   - Single-stain controls should have high signal in primary detector
   - Use scatter plot to visualize: is there a clear population?
3. Verify detector names match across controls
4. Try excluding problematic detectors:
   - Recompute spillover with subset of detectors
5. See [Scientific Logic](./03_SCIENTIFIC_LOGIC.md) for algorithm details

---

### Issue: "Compensation Distorts Data"

**Symptoms:** After applying compensation, plots look strange (inverted colors, negative values).

**Possible Causes:**

| Cause | Solution |
|-------|----------|
| Spillover matrix incorrect | Recompute with high-quality single-stain controls |
| Controls labeled incorrectly | Verify each control contains correct dye only |
| Matrix over-inverted | Normal - display is adjusted; check stats panel for correct values |
| Applied to already-compensated data | Check if data was pre-compensated; clear and reapply |

---

## Statistics & Export Issues

### Issue: "Statistics Show '0' or 'NaN'"

**Symptoms:** Statistics table displays 0, NaN, or -inf values.

**Solutions:**
1. Check population has events:
   - **Properties** (right) → "Count" should be > 0
   - If count = 0, gate was too restrictive
2. Verify statistics type is appropriate:
   - "Mean" requires numerical data (not categorical)
   - "CV" requires data with variance > 0
3. For CV = 0: Population has no variance (all events same intensity)
4. For "Inf" (infinity): Log transform of zero (normal in edge cases)

---

### Issue: "Export File is Empty or Corrupted"

**Symptoms:** Exported CSV/PDF appears empty or won't open in Excel.

**Solutions:**
1. **For CSV:**
   - Verify population has statistics computed (see above)
   - Open with text editor to check for non-printing characters
   - Try different encoding: **Properties** → **Export Encoding** → UTF-8

2. **For PDF:**
   - Verify Adobe Reader/Acrobat is updated
   - Try opening with browser (Chrome, Firefox)
   - Reexport with different quality: **Properties** → **DPI** → try 150 or 300

3. **Verify file saved to correct location:**
   - Default: `~/Downloads/` (check download folder)
   - Look for partial files (*.tmp, *.part)

---

## Performance Issues

### Issue: "BioPro Crashes" or "Unexpectedly Quits"

**Symptoms:** Program suddenly closes without error.

**Possible Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Out of memory | See "Dataset Too Large" section above |
| Infinite loop in gating | Restart; verify DAG has no cycles |
| GPU driver issue | Update graphics drivers; disable GPU acceleration in Settings |
| File corruption | Restart BioPro; reload FCS files |
| Software bug | Submit crash report (Help → Report Bug) with error log |

**Error Logs Location:**
- Windows: `C:\Users\<username>\AppData\Local\BioPro\logs\`
- Mac: `~/Library/Logs/BioPro/`
- Linux: `~/.local/share/BioPro/logs/`

---

### Issue: "Slow Response When Dragging Gates"

**Symptoms:** Dragging a gate causes lag/stuttering.

**Solutions:**
1. **Reduce quality:**
   - **Workspace** → **Presets** → **Fast Preview**
   - Reduces histogram resolution for speed

2. **Decrease dataset size:**
   - Downsample to 10% for testing
   - Use full data for final analysis

3. **Check CPU usage:**
   - Open Task Manager (Windows) / Activity Monitor (Mac)
   - If CPU > 80%, close other apps

4. **Disable features:**
   - Disable "Show Statistics in Real-Time"
   - Disable "Show Gate Overlays During Drag"

---

## Feature-Specific Issues

### UMAP Issues

**"UMAP Takes Too Long"**
- Normal for 1M+ events (~5-10 minutes)
- To speed up: subsample to 100k events
- Or: increase `min_dist` parameter (less detail but faster)

**"UMAP Plot Shows Disconnected Clusters"**
- Try reducing `n_neighbors` (default 15 → try 10)
- Or reducing `min_dist` (default 0.1 → try 0.05)

### Spectral Unmixing Issues

**"Spillover Heatmap Doesn't Match Expected Values"**
- Verify single-stain controls are high-quality
- Check detector configurations are correct in FCS metadata
- Try recomputing spillover matrix

---

## When All Else Fails

### Reset Settings
1. **Preferences** → **Reset to Defaults**
2. Restart BioPro

### Check System Requirements
- **OS**: Windows 10+, macOS 10.14+, or Linux (Ubuntu 18.04+)
- **RAM**: Minimum 8GB (recommended 16GB+)
- **Disk**: 500MB free space
- **Python**: 3.11+

### Contact Support

If issue persists:
1. Collect error log (see above)
2. Prepare minimal reproducible example:
   - Small FCS file that reproduces issue
   - Exact steps to reproduce
3. Submit to: BioPro Support (BioPro → Help → Report Issue)
4. Or: GitHub Issues: [BioPro-flow-cytometry/issues](https://github.com/KalaimaranB/BioPro-flow-cytometry/issues)

---

## Related Documentation

- **[Getting Started](./01_GETTING_STARTED.md)**: Basic workflow
- **[Keyboard Shortcuts](./09_KEYBOARD_SHORTCUTS.md)**: Quick reference
- **[Scientific Logic](./03_SCIENTIFIC_LOGIC.md)**: Mathematical principles
