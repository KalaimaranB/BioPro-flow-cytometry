# Windows isolated-daemon import hangs — postmortem and follow-up

Status: **resolved for this plugin** (CI green as of `d763def`), but with an
open SDK-level architectural question we deliberately deferred. This doc is
the handoff for coming back to that question later.

## TL;DR

`tests/integration/test_ui_daemon.py` was hanging/timing out on
`windows-latest` CI only. Two distinct bugs were found and fixed, both in
the same family: **importing a native-extension-heavy module on the main
thread while the SDK's background stdin-reader thread is alive deadlocks on
Windows.** One of the two mechanisms is proven; the other is a strong,
unconfirmed theory. Both were fixed the same way: move the import to before
the reader thread starts, not by changing what's imported.

## Background: the isolated-daemon startup sequence

`karcytics_sdk.plugin.ui_daemon_runtime.run()` (SDK repo, not this one)
hosts a plugin's window in its own subprocess and speaks a msgpack-over-stdio
protocol with the Hub. Simplified sequencing, in order:

1. Confirm the Hub's theme, build `QApplication` + window.
2. `reader.start()` — a background `threading.Thread` starts reading Hub
   requests off stdin, forever, for the life of the process.
3. `window.show()`, then `send_event("ready")`.
4. `panel = panel_factory()` — **Phase 1**: this plugin's `_build_panel()`
   in `src/karcytics_plugins/flow_cytometry/ui_daemon.py`.
5. `QTimer.singleShot(0, panel.begin_async_init)` — schedules **Phase 2**
   (the real widget build, `workspace_builder.py`) for the next event-loop
   tick. Not run yet.
6. `app.exec()` — the Qt event loop actually starts here. `exit`/`focus`/etc.
   requests are delivered via a `pyqtSignal` that queues until this is
   running, so **nothing gated behind app.exec() can respond until Phase 1
   (step 4) has returned.**

`'ready'` is sent *before* Phase 1 runs, specifically so Phase 1's own cost
doesn't delay it. This detail matters for both bugs below.

## Bug 1 — numpy/pandas import deadlock (proven mechanism)

**Symptom:** the daemon subprocess hung indefinitely on `import numpy`,
Windows only, no crash, no exception.

**Mechanism (confirmed):** `sys.stdin.buffer` is an `io.BufferedReader`,
which holds its own object-level lock for the full duration of any in-flight
`.read()` call. The reader thread (step 2 above) was blocked inside
`sys.stdin.buffer.read()`. numpy's Windows-specific console/codepage
detection touches `sys.stdin` at import time and blocks trying to acquire
that same lock — which the reader thread won't release until the Hub sends
more data. Deadlock. Matches numpy/numpy#24290 exactly (same repro shape:
Windows, `Popen` with piped stdio, a thread reading stdin concurrently with
`import numpy`).

**Fix:** `karcytics_sdk.plugin.ui_daemon_runtime._read_exact_stdin()` (SDK
repo) now reads via raw `os.read(fd, n)` instead of
`sys.stdin.buffer.read()`. `os.read()` talks to the OS pipe directly and
never touches the Python-level `io.BufferedReader` lock, so it can't
contend with an unrelated import on another thread regardless of what that
import is. Shipped in the SDK as commit `531a4a5` ("Repair for windows
daemon").

**This plugin's mitigation (kept, still correct):** `numpy`/`pandas` are
also imported at true module level in `ui_daemon.py`, before `main()` is
ever called — i.e. before the reader thread exists at all. Belt-and-braces
with the SDK fix, not strictly required after it, but harmless and cheap.

## Bug 2 — matplotlib/scipy import hang (mechanism NOT confirmed)

**Symptom:** after Bug 1's fix shipped, a *different* hang appeared at the
same class of test. The daemon stalled indefinitely importing
`karcytics_plugins.flow_cytometry.ui.graph.graph_manager` (which
transitively pulls in `matplotlib.figure`, `scipy.ndimage`/`scipy.stats`,
`matplotlib.path`, etc.) — again Windows only, no crash, no exception,
process alive the whole time.

**What we ruled out:**
- The Bug 1 stdin-lock mechanism itself (already fixed, and `os.read()`
  doesn't hold a Python lock for anything to contend with).
- Windows Defender / AV scanning — confirmed
  `RealTimeProtectionEnabled: False` by default on the GitHub-hosted
  Windows runner (see the `Verify Windows Defender exclusion took effect`
  step in `.github/workflows/release.yml`).
- Qt event-loop reentrancy as *the* variable — we first assumed the hang
  was specific to importing from inside a running `app.exec()` loop
  (dispatched via `QTimer.singleShot` from Phase 2) and "fixed" it by moving
  the import to Phase 1 (`panel_factory()`, before `app.exec()` starts).
  **This did not fix it** — the exact same hang recurred at the exact same
  import, just relocated. That result is what disproved the event-loop
  theory: `panel_factory()` runs on the main thread with no event loop
  running at all, yet the hang still happened there, with the reader thread
  still alive (started in step 2, before Phase 1 in step 4).

**Leading theory (unconfirmed):** a Windows DLL loader-lock deadlock.
Loading many native `.pyd` extensions (matplotlib + scipy pull in dozens of
DLLs) while a second OS thread is alive is a documented Windows-specific
class of deadlock (`LoadLibrary`'s `DllMain` executes while holding the
loader lock; certain concurrent activity on another thread can contend for
it). This is consistent with: Windows-only (loader lock is a Windows OS
concept, not a POSIX one), deterministic given the right conditions, and
explains why an isolated local probe of `import
matplotlib.backends.backend_qtagg` alone (no surrounding daemon machinery)
succeeded in ~8s while the full `GraphManager` chain, inside the real
daemon, hung every time. **It was never isolated to a specific library or
proven against a minimal repro** — only worked around.

**Fix (same shape as Bug 1, mechanism-agnostic):** the six Phase 2 view
modules (`GraphManager`, `NodeCanvas`, `SpectralViewer`,
`PopulationAnalysisViewer`, `StatisticsExplorer`, `ComparisonsViewer`) are
now imported at true module level in `ui_daemon.py`, in the same spot as
`numpy`/`pandas`, before the reader thread exists. This sidesteps the
question of *why* rather than answering it — but it's the one context
proven safe (by Bug 1), and CI has been green since.

**Cost of this fix:** these imports used to happen after `'ready'` was
already on the wire (Phase 1, but after step 3). Now they happen before
`'ready'` is sent at all, so `'ready'` carries their cold-import cost. The
regression guard in `test_reaches_ready_with_a_real_window_geometry` was
widened from 15s to 40s to reflect this — chosen as "real margin under the
Hub's own 45s Ready Gate timeout," not from measured Windows timing data for
this specific cost in isolation.

## The structural problem (why this will recur)

Both bugs are the same shape: **the reader thread (step 2) is alive before
Phase 1 (step 4) runs, and Phase 1 is where a plugin's own heavy imports
naturally want to live.** The "safe zone" — import heavy stuff before the
reader thread starts — currently exists only as:

- A convention hand-rolled directly in this plugin's `ui_daemon.py`
  (the block of module-level imports above `main()`).
- Comments explaining *why*, but nothing in the SDK's `run()` signature or
  docstring that makes this discoverable, let alone enforced.

`ui_daemon_runtime.py` is shared infrastructure for *every* isolated
plugin. Nothing stops a future plugin — or a future change to this one —
from putting a heavy import back inside `panel_factory()` and silently
reopening this exact class of hang. It was rediscovered via ~20-minute CI
hangs twice in this investigation; a plugin without this document would
rediscover it the same way, from scratch.

## Follow-up options (not yet implemented — revisit here)

In priority order, from cheapest/most-actionable to most speculative:

1. **Make the safe import window an explicit SDK contract.** Add a
   `warm_imports` (or similarly named) callback parameter to
   `ui_daemon_runtime.run()`, guaranteed to execute before `reader.start()`,
   with a docstring stating plainly that anything native/heavy belongs
   there and not in `panel_factory()`. Turns tribal knowledge into
   something the API shape enforces. Small, mechanical, closes the actual
   gap for every current and future isolated plugin — not just this one.
2. **Keep a standing timing tripwire.** `ui_daemon.py` already writes
   `[startup] Phase 2 view modules imported in {X}s` to stderr around the
   module-level import block. Worth keeping permanently (not stripping it
   as one-off diagnostic scaffolding) as an early-warning signal if this
   creeps slow again, without needing another multi-round CI investigation
   to get visibility into where the time is going.
3. **Actually confirm Bug 2's mechanism.** The loader-lock theory is
   plausible but unproven. Would need a minimal, isolated Windows repro
   (spawn a real background thread doing blocking I/O, import a
   DLL-heavy package from the main thread, see if it reproduces without
   any of the daemon/Qt/msgpack machinery around it) to move this from
   "worked around" to "understood." Lower urgency now that there's a
   working fix, but worth closing out for real confidence, and because the
   next Windows-only hang in this codebase might not look identical enough
   to pattern-match against this one.
4. **(Bigger, speculative — needs real investigation before committing)**
   Consider replacing the background reader *thread* with a
   `QSocketNotifier` on stdin's fd, so nothing reads until the Qt event
   loop is already pumping — meaning no second thread would ever be alive
   during Phase 1 imports at all, closing the whole class of bug by
   construction rather than by import ordering. Caveat: `QSocketNotifier`
   has known historical limitations with non-socket handles on Windows
   (unlike POSIX, where arbitrary file descriptors work fine) — this may
   not even be viable on the one platform it's meant to fix, and needs to
   be validated before any implementation work starts.

## Relevant files

- `src/karcytics_plugins/flow_cytometry/ui_daemon.py` — this plugin's
  module-level import block (both bugs' mitigations live here).
- `tests/integration/test_ui_daemon.py` — the real-subprocess integration
  tests that caught both bugs; `test_reaches_ready_with_a_real_window_geometry`
  is the regression guard on Bug 2's fix cost.
- `.github/workflows/release.yml` — Windows Defender exclusion/verification
  steps, matplotlib font-cache action (kept permanently, not diagnostic).
- `karcytics_sdk/plugin/ui_daemon_runtime.py` (SDK repo) — `run()`'s
  sequencing (steps 1–6 above), `_read_exact_stdin()` (Bug 1's fix),
  `_RequestReader`/`_RequestBridge` (why `exit`/`focus` can't respond until
  `app.exec()` starts).
