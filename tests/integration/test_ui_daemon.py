"""Real-subprocess integration test for `ui_daemon.py`.

Spawns the actual daemon script under this plugin's own interpreter — the
same way `karcytics_sdk.plugin.PluginUIDaemon` does from the Hub — and speaks
its real msgpack-over-stdio protocol. No mocking of the daemon itself: this
is what proves the module can be hosted standalone (`process_model =
"isolated"`), not just that its Python imports resolve.
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys
import time
from pathlib import Path

import msgpack
import pytest
from karcytics_sdk.host.core_services import CoreServicesServer

REPO_ROOT = Path(__file__).resolve().parents[2]
DAEMON_SCRIPT = REPO_ROOT / "src" / "karcytics_plugins" / "flow_cytometry" / "ui_daemon.py"
FAKE_HUB_COLORS = {"BG_DARKEST": "#0a0a0a", "ACCENT_PRIMARY": "#2f81f7"}


def _write_frame(stream, data: dict) -> None:
    payload = msgpack.packb(data, use_bin_type=True)
    stream.write(struct.pack(">I", len(payload)) + payload)
    stream.flush()


def _read_frame(stream, timeout_error: str) -> dict:
    header = stream.read(4)
    if not header or len(header) < 4:
        raise AssertionError(timeout_error)
    length = struct.unpack(">I", header)[0]
    payload = stream.read(length)
    return msgpack.unpackb(payload, raw=False)


@pytest.fixture
def core_services():
    """A minimal `CoreServicesServer` standing in for the Hub's real one.

    `run()` now blocks on confirming the Hub's real theme before building
    any UI (see `ui_daemon_runtime._confirm_hub_theme_or_exit`) — without a
    reachable `theme.get_current_colors`, the daemon would never reach
    "ready" at all.
    """
    server = CoreServicesServer()
    server.register("theme.get_current_colors", lambda _kwargs: dict(FAKE_HUB_COLORS))
    server.start()
    yield server
    server.stop()


@pytest.fixture
def daemon_process(core_services):
    env = os.environ.copy()
    env["KARCYTICS_CORE_SERVICES_PORT"] = str(core_services.port)
    env["KARCYTICS_CORE_SERVICES_TOKEN"] = core_services.token
    proc = subprocess.Popen(
        [sys.executable, str(DAEMON_SCRIPT)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=REPO_ROOT,
        env=env,
    )
    try:
        yield proc
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)


@pytest.mark.integration
@pytest.mark.slow
class TestUIDaemonIsolatedProcess:
    def test_reaches_ready_with_a_real_window_geometry(self, daemon_process):
        start = time.monotonic()
        frame = _read_frame(
            daemon_process.stdout, "Daemon never sent a 'ready' event before exiting."
        )
        elapsed = time.monotonic() - start

        assert frame["kind"] == "event"
        assert frame["topic"] == "ready"
        assert len(frame["payload"]["geometry"]) == 4  # noqa: PLR2004

        # Regression guard: 'ready' must not be gated behind Phase 2's
        # widget construction (umap/sklearn/matplotlib cold imports) — that
        # once pushed real-world startup past 45s, past the Hub's own Ready
        # Gate timeout, even though nothing about the window itself was
        # slow. 15s is generous for a cold interpreter + Phase 1 skeleton
        # build on a loaded CI machine, but nowhere near what a
        # Phase-2-before-ready regression would cost.
        assert elapsed < 15.0, f"'ready' took {elapsed:.1f}s — Phase 2 may be blocking it again."

    def test_exit_request_shuts_the_process_down_cleanly(self, daemon_process):
        _read_frame(daemon_process.stdout, "Daemon never sent a 'ready' event before exiting.")

        _write_frame(
            daemon_process.stdin,
            {"kind": "request", "request_id": 1, "method": "exit", "kwargs": {}},
        )

        response = _read_frame(
            daemon_process.stdout, "Daemon never responded to the 'exit' request."
        )
        assert response["kind"] == "response"
        assert response["request_id"] == 1
        assert response["payload"] == {"status": "ok"}

        assert daemon_process.wait(timeout=10) == 0

    def test_focus_request_is_answered_after_ready(self, daemon_process):
        _read_frame(daemon_process.stdout, "Daemon never sent a 'ready' event before exiting.")

        _write_frame(
            daemon_process.stdin,
            {"kind": "request", "request_id": 7, "method": "focus", "kwargs": {}},
        )

        response = _read_frame(daemon_process.stdout, "Daemon never responded to 'focus'.")
        assert response == {"kind": "response", "request_id": 7, "payload": {"status": "ok"}}

    def test_phase_2_build_runs_after_ready(self, daemon_process):
        """Regression test: the panel must eventually leave its unstyled
        Phase 1 skeleton — `run_ui_daemon()` calls `panel.begin_async_init()`
        for us, deferred until after the ready handshake (see
        `ui_daemon_runtime.run()`), not `_build_panel()` itself, which would
        block `ready` behind Phase 2's own heavy imports.

        Without begin_async_init() ever running, the center canvas stays on
        `_CenterLoadingPlaceholder` forever and the tab bar's
        `currentChanged` is never connected. Phase 2's last step
        (`WorkspaceBuilder.connect_tab_bar`) emits `status_message`
        ("Ready"), which `_build_panel()` already forwards as a
        `status_message` event — its arrival is proof Phase 2 actually ran.
        """
        _read_frame(daemon_process.stdout, "Daemon never sent a 'ready' event before exiting.")

        for _ in range(20):
            frame = _read_frame(daemon_process.stdout, "Daemon never emitted 'status_message'.")
            if frame.get("kind") == "event" and frame.get("topic") == "status_message":
                assert frame["payload"] == "Ready"
                return

        raise AssertionError("Daemon never emitted a 'status_message' event.")
