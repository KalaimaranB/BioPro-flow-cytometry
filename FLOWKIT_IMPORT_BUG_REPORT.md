# FlowKit Import / Bokeh Template Resolution Bug Report

## Summary

A packaged BioPro app on macOS is failing to load FCS files via FlowKit and instead falling back to `fcsparser`. The failure is caused by Bokeh template resolution during FlowKit import, where Bokeh incorrectly resolves its `_templates` path from the PyInstaller app bundle (`/Applications/BioPro.app/Contents/Frameworks`) instead of the plugin-local virtual environment.

The result is a different loader path being executed on end-user devices, causing truncated or filtered FCS data to be loaded and generating skewed graph output.

## Observed Behavior

From end-user logs:

- `analysis.fcs_io._log_import_diagnostics` shows `flowkit` and `fcsparser` are present in the plugin venv.
- `analysis.fcs_io._load_with_flowkit` warns:
  - `FlowKit import failed: 'file.html.jinja' not found in search path: '/Applications/BioPro.app/Contents/Frameworks/bokeh/core/_templates'`
- FlowKit import fails, and the loader falls back to `fcsparser`.
- `fcsparser` then reports a truncated file warning and loads 65,635 events instead of the expected 306,425 events.

This is the exact failure mode reported by the user.

## Root Cause Hypothesis

The app is packaged with PyInstaller, which sets runtime state such as `sys.frozen` and `sys._MEIPASS` and includes an app bundle path under `sys.path`. Although the plugin environment is injected at runtime, Bokeh uses the packaged app bundle path to resolve templates because:

- `sys.frozen` is truthy
- `sys._MEIPASS` points at the app bundle
- `sys.path` still contains the app bundle framework path
- stale `bokeh` / `flowkit` modules may already be loaded from the app bundle

This causes Bokeh to look in the app bundle's `bokeh/core/_templates` directory instead of the plugin venv's package data.

## Code Areas Involved

- `analysis/fcs_io.py`
  - `load_fcs`
  - `_load_with_flowkit`
  - `_prepare_runtime_for_flowkit_import`
  - `_restore_runtime_after_flowkit_import`
  - `_log_import_diagnostics`
  - `_deep_import_diagnostics`
- `tests/unit/analysis/test_fcs_io.py`
  - existing regression coverage for FlowKit tolerant offset retry
  - newly added import-path regression coverage

## What We Tried

### Initial fix

- Added logging in `analysis/fcs_io.py` to capture import diagnostics and deep import details.
- Introduced `_prepare_runtime_for_flowkit_import()` to:
  - temporarily disable `sys.frozen`
  - remove `sys._MEIPASS`
  - clear cached `flowkit` and `bokeh` modules
  - invalidate import caches

### First regression testing

- Created a test that checked whether the helper cleared specific cached modules and reorders the plugin site-packages path.
- The test passed locally, but the real packaged app still failed.

### Identified gap

- The initial helper did not clear all `bokeh.*` submodules or stale `flowkit`/`bokeh` state loaded from the app bundle.
- The initial test did not simulate preloaded app-bundle `bokeh` modules or the actual template resolution failure mode.

### Revised fix

- Updated the helper to:
  - clear all `bokeh` / `bokeh.*` cached submodules from `sys.modules`
  - clear `flowkit` / `flowkit.*` modules only when they appear to be stale or app-bundle-sourced
  - move the plugin site-packages path to the front of `sys.path`
  - remove `BioPro.app` / `/Applications/BioPro.app/Contents/Frameworks` entries from `sys.path`
- Added regression tests that simulate:
  - app-bundle `bokeh` package presence,
  - preloaded `bokeh` submodules,
  - plugin-local `bokeh` package winning after import prep.

### Current test status

- `./.venv/bin/python -m pytest -q tests/unit/analysis/test_fcs_io.py`
- Result: `4 passed`

## Why the bug still persisted

The bug persisted because the earlier patch and test were not comprehensive enough for the actual packaged runtime state. The app-bundle path and stale module cache were still influencing import resolution, and the first regression only covered a narrower path-ordering case.

The real failure mode includes:

- stale `bokeh` modules already imported from the app bundle
- Bokeh resolving templates using the app bundle path even though the plugin venv is present
- `flowkit` import being attempted under a mixed runtime state

## Current Understanding

The remaining issue is not that FlowKit is missing from the plugin environment. The user logs prove FlowKit is present and visible from the plugin venv. Instead, the issue is a packaging/runtime import-resolution mismatch caused by PyInstaller-style bundling and app-bundle `sys.path` contents.

The fix must therefore ensure the import environment is fully neutralized before FlowKit/Bokeh import, and that no stale app-bundle package roots or cached modules remain.

## Proposed Next Steps

1. **Review the `analysis/fcs_io.py` helper carefully**
   - confirm it clears all `bokeh`/`flowkit` cache state that could have been imported from the app bundle.
   - confirm it reorders `sys.path` such that the plugin venv is first.

2. **Test the packaged build directly**
   - build the packaged BioPro.app with the patched plugin.
   - run the actual end-user workflow and inspect `~/.biopro/biopro.log`.
   - confirm the log no longer contains `file.html.jinja not found` from the app bundle path.

3. **If failure remains, collect deeper runtime state**
   - capture `sys.path` head and full contents at the point just before FlowKit import.
   - capture `sys.modules` entries for `bokeh`, `bokeh.*`, `flowkit`, and `flowkit.*`.
   - capture `sys.frozen`, `sys._MEIPASS`, and relevant environment vars.

4. **Consider a wider solution if needed**
   - isolate plugin imports in a subprocess or custom import hook,
   - ensure plugin site-packages are inserted before any app-framework paths very early in boot,
   - and/or patch Bokeh/FlowKit import logic specifically for PyInstaller bundle cases.

## Recommended Questions for the Specialist

- Does the packaged app runtime still expose any stale `sys.modules` or `sys.path` entries from the bundle before the plugin environment is injected?
- Are there other `PyInstaller`-related runtime flags or app-bundle paths that could influence Bokeh import beyond `sys.frozen` / `sys._MEIPASS`?
- Should we isolate flow cytometry plugin imports behind a custom `importlib` loader to avoid app-bundle contamination entirely?
- Is it safer to patch the app bootstrap to force plugin `site-packages` ahead of any bundle paths before any plugin code executes?

## File References

- `analysis/fcs_io.py`
- `tests/unit/analysis/test_fcs_io.py`

## Important Notes

- The issue is not a missing package in the plugin venv.
- The issue is caused by import resolution/ordering in the packaged app.
- The only full validation is the real packaged build on the end-user machine.
