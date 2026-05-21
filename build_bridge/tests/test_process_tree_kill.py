"""Verify that cancelling an upload kills the full process tree, not just the
parent. Reproduces the butler/steamcmd-leak scenario without doing any real
publishing: a fake "uploader" Python process spawns two long-lived children
and stays alive. We then call the same kill helper UploadPane.cancel() uses
and assert the parent and both children are gone.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
import time

import pytest
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import QApplication

from build_bridge.views.dialogs.publish_dialog import _kill_process_tree


_FAKE_UPLOADER = textwrap.dedent(
    """
    import subprocess, sys, time
    # Spawn two long-lived children, mirroring butler/steamcmd helper processes.
    sleeper = "import time; time.sleep(120)"
    c1 = subprocess.Popen([sys.executable, "-c", sleeper])
    c2 = subprocess.Popen([sys.executable, "-c", sleeper])
    print(c1.pid, flush=True)
    print(c2.pid, flush=True)
    print("READY", flush=True)
    time.sleep(120)
    """
).strip()


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        # tasklist exits 0 even with no match; check the output instead.
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        return str(pid) in out.stdout
    else:
        try:
            import os
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True


def _wait_dead(pids, timeout=5.0):
    deadline = time.monotonic() + timeout
    remaining = list(pids)
    while remaining and time.monotonic() < deadline:
        remaining = [p for p in remaining if _pid_alive(p)]
        if remaining:
            time.sleep(0.1)
    return remaining


def test_kill_process_tree_kills_children(qapp):
    proc = QProcess()
    proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
    proc.start(sys.executable, ["-u", "-c", _FAKE_UPLOADER])
    assert proc.waitForStarted(5000), "fake uploader failed to start"

    parent_pid = int(proc.processId())
    child_pids: list[int] = []

    deadline = time.monotonic() + 10.0
    buf = b""
    while time.monotonic() < deadline:
        if proc.waitForReadyRead(500):
            buf += bytes(proc.readAllStandardOutput())
        if b"READY" in buf:
            break

    lines = buf.decode("utf-8", "replace").splitlines()
    for line in lines:
        line = line.strip()
        if line.isdigit():
            child_pids.append(int(line))

    assert len(child_pids) == 2, f"expected 2 child pids, got {child_pids!r} (buf={buf!r})"
    assert all(_pid_alive(p) for p in child_pids), "children not alive before kill"
    assert _pid_alive(parent_pid), "parent not alive before kill"

    _kill_process_tree(parent_pid)
    proc.kill()
    proc.waitForFinished(2000)

    still_alive = _wait_dead([parent_pid] + child_pids, timeout=5.0)
    assert not still_alive, f"these pids survived tree-kill: {still_alive}"
