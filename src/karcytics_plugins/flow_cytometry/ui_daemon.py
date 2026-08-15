"""Flow Cytometry UI Daemon — hosts the module's own window in its own process.

Run by `karcytics_sdk.plugin.PluginUIDaemon` from this plugin's own `.venv`
interpreter (never imported into the Hub's process). Owns its own
`QApplication` and its own copies of numpy/matplotlib/PIL/PyQt6, so switching
to or from this module never touches the Hub's `sys.modules` — the whole
class of shadow-copy/purge collisions this exists to avoid.

Everything protocol-related (frame transport, the ready handshake, request
dispatch, noticing a native window close) lives in the SDK's
`karcytics_sdk.plugin.run_ui_daemon` and is identical for every isolated
plugin; this file only does what's genuinely plugin-specific: sys.path
setup, env vars that must be set before numpy imports, and building this
plugin's `PluginContext` from the SDK's `runtime_services` singletons —
the same `task_scheduler`/`event_bus` instances this plugin's own widgets
import directly (see `karcytics_sdk.plugin.runtime_services`), so there is
exactly one shared scheduler/event bus per process, not two.

No shimming: every `karcytics.core.*`/`karcytics.ui.*` import this plugin's
own code used to make has been migrated to import the real thing from
`karcytics_sdk.plugin` directly, since this plugin's standalone `.venv`
never had the Hub's `karcytics` package to begin with.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Run directly as `python ui_daemon.py` by PluginUIDaemon (see module docstring
# above) rather than imported as part of the `karcytics_plugins` package —
# nothing else puts this plugin's own src/ on sys.path for a freestanding
# subprocess the way PluginEnvironmentInjector.inject_path() does for the
# in-process legacy load path, so it has to do that for itself before it can
# import itself.
_SRC_DIR = Path(__file__).resolve().parents[2]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# CRITICAL: same reasoning as karcytics_plugins.flow_cytometry.__init__ — must be
# set before any numpy/scipy import, which is why the plugin package import
# below happens before anything else that could pull those in transitively.
import os  # noqa: E402

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")


def _extract_file_count(panel: Any) -> int:
    """Mirror workspace_window._on_wizard_state_changed()'s file-count heuristic.

    Kept in sync deliberately rather than shared, since that method reads a
    live in-process `wizard_panel` and this reads a panel living in this
    process instead — but the payload shape sent to the Hub must match what
    `WorkspaceWindow._on_daemon_state_changed()` expects.
    """
    state = getattr(panel, "state", None) or {}
    if isinstance(state, dict) or hasattr(state, "get"):
        files = state.get("files") or state.get("loaded_files") or state.get("file_list") or []
    else:
        try:
            files = state.data.experiment.samples
        except AttributeError:
            files = []
    return len(files) if hasattr(files, "__len__") else 0


def _build_plugin_context() -> Any:
    from karcytics_sdk.plugin.context import PluginContext
    from karcytics_sdk.plugin.manifest import PluginManifest
    from karcytics_sdk.plugin.runtime_services import event_bus, task_scheduler

    manifest = PluginManifest(
        name="flow_cytometry",
        entry_point="karcytics_plugins.flow_cytometry:initialize",
        sdk_version="2.0",
        requires=["task_scheduler", "logger", "event_bus"],
    )
    services = {
        "task_scheduler": task_scheduler,
        "logger": __import__("logging").getLogger("plugin.flow_cytometry"),
        "event_bus": event_bus,
    }
    return PluginContext(services=services, manifest=manifest)


def main() -> None:
    from karcytics_sdk.plugin import run_ui_daemon
    from karcytics_sdk.plugin.ui_daemon_runtime import send_event

    def _build_panel() -> Any:
        from karcytics_plugins.flow_cytometry import initialize

        context = _build_plugin_context()
        plugin_module = initialize(context)

        panel_class = plugin_module.get_panel_class()
        panel = panel_class()

        if hasattr(panel, "state_changed"):
            panel.state_changed.connect(
                lambda: send_event("state_changed", {"file_count": _extract_file_count(panel)})
            )
        if hasattr(panel, "status_message"):
            panel.status_message.connect(lambda msg: send_event("status_message", msg))

        # In-process, karcytics.ui.windows.workspace.plugin_loader.PluginLoaderManager
        # calls panel.begin_async_init() immediately after construction (its
        # "Phase 2" — the real graph canvas/ribbons/tabs; construction above
        # only builds the static skeleton). Nothing plays that role for an
        # isolated module — but that call must NOT happen here: begin_async_init()
        # imports WorkspaceBuilder, which pulls in umap/sklearn/hdbscan/matplotlib
        # at module load, a cold-start that can comfortably exceed the Hub's 45s
        # Ready Gate timeout on its own. run_ui_daemon() calls it for us, deferred
        # until *after* the ready handshake, exactly like the in-process path
        # always guaranteed (Phase 1's fast panel_ready before any Phase 2 import).
        return panel

    # No local "inject_workflow" handler here — ui_daemon_runtime.run() already
    # registers one that's aware of the Ready Gate protocol (stages the
    # payload onto panel._deferred_workflow_payload and only then calls
    # begin_async_init(), instead of calling load_workflow() on a
    # skeleton-only panel that hasn't built _population_analysis_viewer and
    # friends yet). A local override here with the same method name would
    # silently replace that one (RequestDispatcher.register() replaces on
    # name collision) — this file used to do exactly that, which is why a
    # pending-workflow module open used to crash with AttributeError deep in
    # _refresh_all() and show data loading live instead of behind the
    # hyperspace loader.
    run_ui_daemon(
        _build_panel,
        window_title="Flow Cytometry",
        window_size=(1400, 900),
        plugin_id="flow_cytometry",
    )


if __name__ == "__main__":
    main()
