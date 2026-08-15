"""Real-subprocess integration test for `ui_daemon.py`.

Spawns the actual daemon script under this plugin's own interpreter — the
same way `karcytics_sdk.plugin.PluginUIDaemon` does from the Hub — and speaks
its real msgpack-over-stdio protocol. No mocking of the daemon itself: this
is what proves the module can be hosted standalone (`process_model =
"isolated"`), not just that its Python imports resolve.
"""

from __future__ import annotations

import os
import queue
import struct
import subprocess
import sys
import threading
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


class _DaemonIO:
    """Continuously drains the daemon's stdout (as framed messages) and
    stderr (as raw diagnostics) on background threads.

    A synchronous `stream.read()` on the test thread left stderr completely
    undrained. If the daemon writes enough to stderr to fill the OS pipe
    buffer, it blocks on that write forever while the test blocks reading
    stdout forever — a classic subprocess.PIPE deadlock. Windows' anonymous
    pipe buffers are small enough that this is far more likely to trip there
    than on macOS/Linux. Both streams are drained from the moment the
    process starts, and every read is bounded by a timeout so a stuck daemon
    fails the test instead of hanging CI indefinitely.
    """

    def __init__(self, proc: subprocess.Popen):
        self._proc = proc
        self._frames: queue.Queue[dict] = queue.Queue()
        self._stderr_chunks: list[bytes] = []
        self._stdout_thread = threading.Thread(target=self._pump_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._pump_stderr, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def _pump_stdout(self) -> None:
        stream = self._proc.stdout
        while True:
            header = stream.read(4)
            if not header or len(header) < 4:
                return
            length = struct.unpack(">I", header)[0]
            payload = stream.read(length)
            self._frames.put(msgpack.unpackb(payload, raw=False))

    def _pump_stderr(self) -> None:
        for chunk in iter(lambda: self._proc.stderr.read(4096), b""):
            self._stderr_chunks.append(chunk)

    def read_frame(self, timeout_error: str, timeout: float = 20.0) -> dict:
        try:
            return self._frames.get(timeout=timeout)
        except queue.Empty:
            stderr = b"".join(self._stderr_chunks).decode(errors="replace")
            raise AssertionError(
                f"{timeout_error} (waited {timeout:.0f}s)\n--- daemon stderr ---\n{stderr}"
            ) from None


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


@pytest.fixture
def daemon_io(daemon_process):
    return _DaemonIO(daemon_process)


@pytest.mark.integration
@pytest.mark.slow
class TestUIDaemonIsolatedProcess:
    def test_reaches_ready_with_a_real_window_geometry(self, daemon_io):
        start = time.monotonic()
        frame = daemon_io.read_frame("Daemon never sent a 'ready' event before exiting.")
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

    def test_exit_request_shuts_the_process_down_cleanly(self, daemon_process, daemon_io):
        daemon_io.read_frame("Daemon never sent a 'ready' event before exiting.")

        _write_frame(
            daemon_process.stdin,
            {"kind": "request", "request_id": 1, "method": "exit", "kwargs": {}},
        )

        response = daemon_io.read_frame("Daemon never responded to the 'exit' request.")
        assert response["kind"] == "response"
        assert response["request_id"] == 1
        assert response["payload"] == {"status": "ok"}

        assert daemon_process.wait(timeout=10) == 0

    def test_focus_request_is_answered_after_ready(self, daemon_process, daemon_io):
        daemon_io.read_frame("Daemon never sent a 'ready' event before exiting.")

        _write_frame(
            daemon_process.stdin,
            {"kind": "request", "request_id": 7, "method": "focus", "kwargs": {}},
        )

        response = daemon_io.read_frame("Daemon never responded to 'focus'.")
        assert response == {"kind": "response", "request_id": 7, "payload": {"status": "ok"}}

    def test_phase_2_build_runs_after_ready(self, daemon_io):
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
        daemon_io.read_frame("Daemon never sent a 'ready' event before exiting.")

        for _ in range(20):
            frame = daemon_io.read_frame("Daemon never emitted 'status_message'.")
            if frame.get("kind") == "event" and frame.get("topic") == "status_message":
                assert frame["payload"] == "Ready"
                return

        raise AssertionError("Daemon never emitted a 'status_message' event.")
