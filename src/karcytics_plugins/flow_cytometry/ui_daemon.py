"""Flow Cytometry UI Daemon — hosts the module's own window in its own process.

Run by `karcytics_sdk.plugin.PluginUIDaemon` from this plugin's own `.venv`
interpreter (never imported into the Hub's process). Owns its own
`QApplication` and its own copies of numpy/matplotlib/PIL/PyQt6, so switching
to or from this module never touches the Hub's `sys.modules` — the whole
class of shadow-copy/purge collisions this exists to avoid.

Speaks the same length-prefixed msgpack framing as `daemon_worker.py`, but
with `PluginUIDaemon`'s kind-tagged frames ({"kind": "request"|"response"|"event"})
instead of `daemon_worker.py`'s plain request/response protocol, since this
process needs to push events to the Hub unprompted (tutorial hooks,
state_changed) rather than only ever answering a call.

STATUS: the protocol side of this file (framing, ready handshake, request
dispatch, event forwarding) is implemented and lints clean. Standing up the
*real* FlowCytometryPanel through it is not yet fully verified end-to-end:
manual smoke-testing (spawn this script under the plugin's own .venv, wait
for a "ready" frame) got through task_scheduler/event_bus/diagnostics/
tutorial_manager/theme shimming (see `_install_core_shims`) and then hit a
missing `Colors.ACCENT_PRIMARY_PRESSED` constant deep in a widget
(`gate_hierarchy/propagation_toggle.py`). That's a signal, not a one-off: this
plugin has ~80+ call sites importing `karcytics.core.*`/`karcytics.ui.*` directly
(grep for "from karcytics.core" / "from karcytics.ui" across src/) rather than going
through `PluginContext`, assuming it always runs inside the Hub's own
interpreter. `_install_core_shims()` papers over the ones already found;
there are very likely more. The real fix is in the plugin's own code —
composition root and widgets should take `task_scheduler`/`event_bus`/theme
etc. as injected dependencies instead of importing Hub internals directly —
not further shimming here. Treat this file as a correct, working transport
layer sitting in front of a panel that needs that cleanup before it will
construct standalone.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run directly as `python ui_daemon.py` by PluginUIDaemon (see docstring above)
# rather than imported as part of the `karcytics_plugins` package — nothing else
# puts this plugin's own src/ on sys.path for a freestanding subprocess the
# way PluginEnvironmentInjector.inject_path() does for the in-process legacy
# load path, so it has to do that for itself before it can import itself.
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

import struct  # noqa: E402
import threading  # noqa: E402
import traceback  # noqa: E402
from typing import Any  # noqa: E402

import msgpack  # noqa: E402


def write_frame(data: dict[str, Any]) -> None:
    """Write a length-prefixed msgpack frame to stdout."""
    payload = msgpack.packb(data, use_bin_type=True)
    header = struct.pack(">I", len(payload))
    sys.stdout.buffer.write(header + payload)
    sys.stdout.buffer.flush()


def read_frame() -> dict[str, Any] | None:
    """Read a length-prefixed msgpack frame from stdin, or None on EOF."""
    header = sys.stdin.buffer.read(4)
    if not header or len(header) < 4:  # noqa: PLR2004
        return None
    length = struct.unpack(">I", header)[0]
    payload = sys.stdin.buffer.read(length)
    if not payload or len(payload) < length:
        return None
    return msgpack.unpackb(payload, raw=False)


def send_event(topic: str, payload: Any = None) -> None:
    """Push an unsolicited event frame to the Hub (tutorial hooks, state_changed, ...)."""
    write_frame({"kind": "event", "topic": topic, "payload": payload})


class _FakeKarcyticsEvent:
    """Fake stand-in for `karcytics.core.event_bus.KarcyticsEvent`.

    The real thing is an `Enum`; plugin code only ever does attribute access
    on it (`KarcyticsEvent.MODULE_OPENED`) and passes the result straight into
    `event_bus.emit(...)`. Returning the attribute name itself as a plain
    string is sufficient for that and needs no enum machinery — `_EventBusShim
    .emit()` below already expects a string topic.
    """

    def __getattr__(self, name: str) -> str:
        return name


class _ColorsFallback:
    """`Colors` accessor with graceful degradation for undefined constants.

    This plugin's UI code assumes any `Colors.SOME_NAME` access succeeds,
    matching the real Hub theme's exhaustive constant set — the SDK's
    `theme_fallback.DynamicColors` palette doesn't cover every constant a
    given plugin's newer widgets might reference (e.g. `ACCENT_PRIMARY_PRESSED`
    isn't in it). Mirrors the graceful-degradation behavior
    `theme_fallback._ColorsProxy.__getattr__` already has for exactly this
    case (falling back to a safe default color) without that proxy's
    `sys.modules["karcytics.ui.theme"]` self-check, which is what caused the
    infinite recursion `_install_core_shims()` works around by aliasing
    `DynamicColors` instead of the proxy.
    """

    def __getattr__(self, name: str) -> str:
        from karcytics_sdk.plugin.theme_fallback import DynamicColors

        return getattr(DynamicColors, name, "#0d1117")


def _install_core_shims(plugin_module: Any, task_scheduler: _LocalTaskScheduler) -> None:
    r"""Stub the `karcytics.core.*` modules this plugin imports directly, bypassing
    `PluginContext` entirely, so its code can run unmodified out-of-process.

    Grep for `from karcytics\.core` across this repo turns up ~20 call sites
    across `task_scheduler`, `event_bus`, `diagnostics`, and
    `tutorial_manager`/`models.tutorial_models` — this plugin was written
    assuming it always runs inside the Hub's own interpreter. None of that
    resolves out-of-process, and it isn't reasonable to fake all of it (the
    tutorial course content in particular is substantial typed domain data,
    not a service interface). What's stubbed here:

    - `karcytics.core.task_scheduler.task_scheduler` -> the same
      `_LocalTaskScheduler` instance passed to `PluginContext` — one shared
      task scheduler regardless of which import path a given call site uses.
    - `karcytics.core.event_bus.event_bus`/`KarcyticsEvent` -> forwards `.emit()`
      calls to the Hub as "event" frames (see `_EventBusShim`/`send_event`);
      `.subscribe()`/`.unsubscribe()` are no-ops (no cross-process equivalent
      yet — nothing here currently relies on receiving Hub-originated events
      this way).
    - `karcytics.core.diagnostics.diagnostics` -> forwards `.report_error()` to
      the Hub as a "diagnostics_error" event instead of the Hub's real
      diagnostics reporter.
    - `karcytics.core.tutorial_manager.global_tutorial_manager` -> an inert stub,
      *and* `register_courses` is replaced with a no-op on the plugin module
      (a plain name `get_panel_class()` looks up at call time, so this
      intercepts it cleanly) — `register_courses` unconditionally imports
      `tutorials/courses.py`, which pulls in `karcytics.core.models.tutorial_models`,
      before it even looks at what manager it was given, so stubbing
      `tutorial_manager` alone isn't enough to avoid that import.

    Known gap: onboarding courses aren't registered for daemon-hosted modules
    today. Proper support means routing course registration through the Core
    Services channel (see the SDK's `CoreServicesClient`) instead of a direct
    import — a documented follow-up, not something this thin daemon script
    should take on.
    """
    import types

    def _stub_module(name: str, **attrs: Any) -> None:
        if name in sys.modules:
            return
        mod = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(mod, key, value)
        parent, _, leaf = name.rpartition(".")
        if parent:
            _stub_module(parent)
            setattr(sys.modules[parent], leaf, mod)
        sys.modules[name] = mod

    _stub_module("karcytics.core.task_scheduler", task_scheduler=task_scheduler)
    _stub_module(
        "karcytics.core.event_bus", event_bus=_EventBusShim(), KarcyticsEvent=_FakeKarcyticsEvent()
    )
    _stub_module("karcytics.core.diagnostics", diagnostics=_DiagnosticsShim())
    _stub_module(
        "karcytics.core.tutorial_manager",
        global_tutorial_manager=types.SimpleNamespace(courses_by_module={}),
    )

    # karcytics.ui.theme: ~60 call sites across this plugin do
    # `from karcytics.ui.theme import Colors, Fonts[, theme_manager]` for
    # consistent styling. The SDK already ships a fallback for exactly this
    # ("plugin standalone testing") — reuse its color/font values rather than
    # inventing another copy. Exposed as `DynamicColors` (the concrete class),
    # not `theme_fallback.Colors` (a `_ColorsProxy` instance whose
    # `__getattr__` checks `sys.modules["karcytics.ui.theme"]` on every access —
    # aliasing that proxy *as* `karcytics.ui.theme` itself makes it look itself
    # up forever).
    if "karcytics.ui.theme" not in sys.modules:
        import karcytics_sdk.plugin.theme_fallback as _theme_fallback

        _stub_module(
            "karcytics.ui.theme",
            Colors=_ColorsFallback(),
            Fonts=_theme_fallback.Fonts,
            theme_manager=_theme_fallback.theme_manager,
        )

    plugin_module.register_courses = lambda *args, **kwargs: None


class _DiagnosticsShim:
    """Process-local stand-in for the Hub's `diagnostics` service."""

    def report_error(self, message: str, plugin_id: str | None = None, fatal: bool = False) -> None:
        send_event(
            "diagnostics_error", {"message": message, "plugin_id": plugin_id, "fatal": fatal}
        )


class _LocalTaskScheduler:
    """Process-local stand-in for the Hub's shared `task_scheduler` service.

    The Hub's `TaskScheduler` centralizes a single `QThreadPool` specifically
    to stop *multiple concurrently-loaded plugins* from exhausting it against
    each other — see `karcytics/core/task_scheduler.py`. That concern doesn't
    apply here: this process only ever hosts one module, so there's nothing
    to protect this pool from, and routing task submission through the Hub
    over IPC for every analysis run would add latency for no isolation
    benefit. Reuses the same portable `AnalysisWorker`/`AnalysisRunnable`
    plumbing the Hub's own scheduler is built on.
    """

    def __init__(self) -> None:
        from PyQt6.QtCore import QThreadPool

        self._pool: Any = QThreadPool.globalInstance()
        assert self._pool is not None
        self._active: list[Any] = []

    def submit(self, analyzer: Any, state: Any = None) -> Any:
        from karcytics_sdk.plugin import AnalysisRunnable, AnalysisWorker

        worker = AnalysisWorker(analyzer, state)
        self._active.append(worker)
        worker.finished.connect(
            lambda *_: self._active.remove(worker) if worker in self._active else None
        )
        worker.error.connect(
            lambda *_: self._active.remove(worker) if worker in self._active else None
        )
        self._pool.start(AnalysisRunnable(worker))
        return worker

    def cancel_all(self) -> None:
        self._pool.clear()


class _EventBusShim:
    """Process-local stand-in for the Hub's `event_bus` service.

    Covers both call shapes seen in this plugin's code: the SDK's
    `CentralEventBus` (`publish`/`subscribe`) and the Hub's own `EventManager`
    (`emit`/`subscribe`/`unsubscribe`) — `karcytics.core.event_bus.event_bus` is
    stubbed to this same instance for both. `emit`/`publish` forward to the
    Hub as an "event" frame (see module docstring); `subscribe`/`unsubscribe`
    have no cross-process equivalent yet, so they're no-ops — nothing in this
    plugin currently relies on receiving Hub-originated events this way, only
    sending to it.
    """

    def emit(self, event_type: Any, *args: Any, **kwargs: Any) -> None:
        topic = getattr(event_type, "name", None) or str(event_type)
        payload = kwargs or (args[0] if len(args) == 1 else (args or None))
        send_event(topic.lower(), payload)

    def publish(self, topic: str, data: Any = None) -> None:
        send_event(topic, data)

    def subscribe(self, event_type: Any, callback: Any) -> None:  # noqa: ARG002
        pass

    def unsubscribe(self, event_type: Any, callback: Any) -> None:  # noqa: ARG002
        pass


def _build_plugin_context(task_scheduler: _LocalTaskScheduler) -> Any:
    from karcytics_sdk.plugin.context import PluginContext
    from karcytics_sdk.plugin.manifest import PluginManifest

    manifest = PluginManifest(
        name="flow_cytometry",
        entry_point="karcytics_plugins.flow_cytometry:initialize",
        sdk_version="2.0",
        requires=["task_scheduler", "logger", "event_bus"],
    )
    services = {
        "task_scheduler": task_scheduler,
        "logger": __import__("logging").getLogger("plugin.flow_cytometry"),
        "event_bus": _EventBusShim(),
    }
    return PluginContext(services=services, manifest=manifest)


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


class _RequestReader:
    """Background thread draining stdin and delivering requests to the Qt thread.

    Runs on its own thread so a slow/blocking request handler on the Qt side
    never stalls reading the next frame — mirrors `PluginUIDaemon`'s reader
    thread on the Hub side, just for the opposite direction of traffic.
    """

    def __init__(self, on_request: Any) -> None:
        self._on_request = on_request
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _loop(self) -> None:
        while True:
            frame = read_frame()
            if frame is None:
                # Hub process is gone; there is no one left to talk to.
                os._exit(0)  # noqa: SLF001
            self._on_request(frame)


def main() -> None:  # noqa: C901
    from PyQt6.QtCore import QMetaObject, QThread
    from PyQt6.QtWidgets import QApplication, QMainWindow

    app = QApplication.instance() or QApplication(sys.argv)

    from karcytics_plugins.flow_cytometry import initialize

    task_scheduler = _LocalTaskScheduler()
    context = _build_plugin_context(task_scheduler)
    plugin_module = initialize(context)
    _install_core_shims(plugin_module, task_scheduler)
    PanelClass = plugin_module.get_panel_class()  # noqa: N806
    panel = PanelClass()

    window = QMainWindow()
    window.setCentralWidget(panel)
    window.setWindowTitle("Flow Cytometry")
    window.resize(1400, 900)

    if hasattr(panel, "state_changed"):
        panel.state_changed.connect(
            lambda: send_event("state_changed", {"file_count": _extract_file_count(panel)})
        )
    if hasattr(panel, "status_message"):
        panel.status_message.connect(lambda msg: send_event("status_message", msg))

    def handle_request(frame: dict[str, Any]) -> None:
        method = frame.get("method")
        request_id = frame.get("request_id")
        kwargs = frame.get("kwargs", {})

        try:
            if method in {"exit", "close_requested"}:
                QMetaObject.invokeMethod(app, "quit")
                result: Any = {"status": "ok"}
            elif method == "theme_changed":
                # Best-effort: only wired up if the panel supports it.
                if hasattr(panel, "_apply_theme_styles"):
                    panel._apply_theme_styles()
                result = {"status": "ok"}
            elif method == "inject_workflow" and hasattr(panel, "load_workflow"):
                panel.load_workflow(kwargs.get("payload"), filename=kwargs.get("filename"))
                result = {"status": "ok"}
            else:
                result = {"error": f"Unknown method '{method}'"}
        except Exception as exc:  # noqa: BLE001
            result = {"error": f"{exc}\n{traceback.format_exc()}"}

        write_frame({"kind": "response", "request_id": request_id, "payload": result})

    reader = _RequestReader(handle_request)
    reader.start()

    window.show()
    geometry = window.geometry()
    send_event(
        "ready",
        {"geometry": [geometry.x(), geometry.y(), geometry.width(), geometry.height()]},
    )

    assert QThread.currentThread() is app.thread()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
