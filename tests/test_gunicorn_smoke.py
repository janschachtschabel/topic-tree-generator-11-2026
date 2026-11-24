"""Starts the real production server (gunicorn, 2 workers) and checks both ports."""

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _wait(url: str, seconds: float = 20) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            if _get(url)[0] == 200:
                return
        except OSError:
            pass
        time.sleep(0.2)
    raise AssertionError(f"server did not answer on {url}")


@pytest.mark.slow
@pytest.mark.skipif(sys.platform == "win32", reason="gunicorn requires POSIX (fcntl/signals); runs in Linux CI")
def test_gunicorn_serves_public_and_internal_ports(tmp_path: Path) -> None:
    public, internal = _free_port(), _free_port()
    env = {
        **os.environ,
        "PUBLIC_PORT": str(public),
        "INTERNAL_PORT": str(internal),
        "WEB_CONCURRENCY": "2",
        "PROMETHEUS_MULTIPROC_DIR": str(tmp_path / "prom"),
        "LOG_FORMAT": "json",
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "gunicorn", "-c", "gunicorn.conf.py", "app.main:app"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        _wait(f"http://127.0.0.1:{public}/health")
        _wait(f"http://127.0.0.1:{internal}/health")
        for _ in range(6):
            assert _get(f"http://127.0.0.1:{public}/_ping")[0] == 200
        assert _get(f"http://127.0.0.1:{internal}/ready")[0] == 200
        status, body = _get(f"http://127.0.0.1:{internal}/metrics")
        assert status == 200
        assert 'topic_tree_requests_total{route="health",status="200"}' in body
        # The internal paths are not served on the public port.
        assert _get(f"http://127.0.0.1:{public}/metrics")[0] == 404
    finally:
        proc.send_signal(signal.SIGTERM)
        output = proc.communicate(timeout=30)[0].decode()
    assert proc.returncode == 0, output[-2000:]
    workers = {line for line in output.splitlines() if "Booting worker" in line}
    assert len(workers) == 2, output[-2000:]


@pytest.mark.slow
def test_dev_server_serves_public_and_internal_ports(tmp_path: Path) -> None:
    """Cross-platform dual-port check via `python -m app` (runs on Windows and Linux)."""
    public, internal = _free_port(), _free_port()
    env = {
        **os.environ,
        "PUBLIC_PORT": str(public),
        "INTERNAL_PORT": str(internal),
        "LOG_FORMAT": "json",
    }
    log_path = tmp_path / "dev.log"
    with log_path.open("wb") as log_file:
        proc = subprocess.Popen(
            [sys.executable, "-m", "app"], cwd=ROOT, env=env, stdout=log_file, stderr=subprocess.STDOUT
        )
        try:
            _wait(f"http://127.0.0.1:{public}/health")
            _wait(f"http://127.0.0.1:{internal}/health")
            assert _get(f"http://127.0.0.1:{public}/_ping")[0] == 200
            assert _get(f"http://127.0.0.1:{internal}/ready")[0] == 200
            status, body = _get(f"http://127.0.0.1:{internal}/metrics")
            assert status == 200
            assert 'topic_tree_requests_total{route="health",status="200"}' in body
            assert _get(f"http://127.0.0.1:{public}/metrics")[0] == 404
        finally:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], check=False, capture_output=True)
            else:
                proc.terminate()
            proc.wait(timeout=15)
