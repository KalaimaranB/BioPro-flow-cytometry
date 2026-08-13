"""Real-subprocess integration test for `ui_daemon.py`.

Spawns the actual daemon script under this plugin's own interpreter — the
same way `karcytics_sdk.plugin.PluginUIDaemon` does from the Hub — and speaks
its real msgpack-over-stdio protocol. No mocking of the daemon itself: this
is what proves the module can be hosted standalone (`process_model =
"isolated"`), not just that its Python imports resolve.
"""

from __future__ import annotations

import struct
import subprocess
import sys
from pathlib import Path

import msgpack
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DAEMON_SCRIPT = REPO_ROOT / "src" / "karcytics_plugins" / "flow_cytometry" / "ui_daemon.py"


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
def daemon_process():
    proc = subprocess.Popen(
        [sys.executable, str(DAEMON_SCRIPT)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=REPO_ROOT,
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
        frame = _read_frame(
            daemon_process.stdout, "Daemon never sent a 'ready' event before exiting."
        )

        assert frame["kind"] == "event"
        assert frame["topic"] == "ready"
        assert len(frame["payload"]["geometry"]) == 4  # noqa: PLR2004

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
