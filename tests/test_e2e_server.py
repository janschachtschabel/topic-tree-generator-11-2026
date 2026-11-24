"""Live end-to-end HTTP tests against the running server and `tests/stub_openai.py` (plan T6.3).

Runs gunicorn (2 workers) on POSIX and `python -m app` on Windows so every platform tests real TCP sockets,
both ports, auth, delegation-token forwarding, trace propagation, metrics and JSON logs without leaking tokens.
"""

import copy
import json
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

from tests.fixtures import spec_examples as ex
from tests.stub_openai import StubOpenAIServer

ROOT = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _request(
    method: str, url: str, *, payload: dict | None = None, headers: dict[str, str] | None = None
) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8")


def _wait_ready(url: str, proc: subprocess.Popen, log_path: Path, seconds: float = 15) -> None:
    end = time.monotonic() + seconds
    last = None
    while time.monotonic() < end:
        if proc.poll() is not None:
            out = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
            raise AssertionError(f"server exited early ({proc.returncode}):\n{out}")
        try:
            last = _request("GET", url)
            if last[0] == 200:
                return
        except OSError as exc:
            last = (0, str(exc))
        time.sleep(0.2)
    raise AssertionError(f"server did not become ready at {url}; last={last}")


def _stop(proc: subprocess.Popen) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], check=False, capture_output=True)
        proc.wait(timeout=10)
    else:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=20)


@pytest.mark.slow
def test_e2e_v2_all_use_cases_bapi_and_standalone(tmp_path: Path) -> None:
    public_port, internal_port = _free_port(), _free_port()
    delegation_token = "bdt_e2e_secret_token_never_log"
    service_key = "svc-e2e-key-secret"
    trace_id = "0123456789abcdef0123456789abcdef"

    with StubOpenAIServer() as stub:
        env = {
            **os.environ,
            "SERVICE_MODE": "auto",
            "SERVICE_API_KEYS": service_key,
            "B_API_BASE_URL": stub.base_url,
            "B_API_ROUTE": "topic-tree-generator",
            "OPENAI_BASE_URL": f"{stub.base_url}/v1",
            "OPENAI_API_KEY": "sk-stub-local-key",
            "OPENAI_MODEL": "gpt-6-luna",
            "PUBLIC_PORT": str(public_port),
            "INTERNAL_PORT": str(internal_port),
            "WEB_CONCURRENCY": "2",
            "PROMETHEUS_MULTIPROC_DIR": str(tmp_path / "prom"),
            "LOG_FORMAT": "json",
        }
        cmd = (
            [sys.executable, "-m", "app"]
            if sys.platform == "win32"
            else [sys.executable, "-m", "gunicorn", "-c", "gunicorn.conf.py", "app.main:app"]
        )
        log_path = tmp_path / "server.log"
        with log_path.open("wb") as log_file:
            proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=log_file, stderr=subprocess.STDOUT)
            try:
                pub = f"http://127.0.0.1:{public_port}"
                internal = f"http://127.0.0.1:{internal_port}"
                _wait_ready(f"{pub}/health", proc, log_path)
                _wait_ready(f"{internal}/health", proc, log_path)

                # 1) b-api mode: delegation token forwarded unchanged, B3 + x-client-trace-id propagated, no X-API-KEY.
                topic_req = copy.deepcopy(ex.TOPIC)
                topic_req["shape"]["depth"] = 2
                status, body = _request(
                    "POST",
                    f"{pub}/v2/topic-tree",
                    payload=topic_req,
                    headers={
                        "Authorization": f"Bearer {delegation_token}",
                        "X-B3-TraceId": trace_id,
                        "X-B3-SpanId": "0123456789abcdef",
                        "x-client-trace-id": "client-e2e-42",
                    },
                )
                assert status == 200, body
                resp = json.loads(body)
                assert len(resp["collection"]) == 6
                assert resp["metadata"]["generation"]["model"] == "topic-tree-generator"
                # 1 full skeleton call + 3 parallel describe_nodes batches (24 nodes / batch 10)
                assert resp["metadata"]["generation"]["usage"]["llm_calls"] == 4
                assert resp["metadata"]["generation"]["usage"]["cached_tokens"] > 0

                assert len(stub.calls) == 4
                assert all(c.path == "/api/v1/llm/router/chat/completions" for c in stub.calls)
                assert all(c.headers.get("authorization") == f"Bearer {delegation_token}" for c in stub.calls)
                assert all("x-api-key" not in c.headers for c in stub.calls)
                assert all(c.headers.get("x-b3-traceid") == trace_id for c in stub.calls)
                assert all(c.headers.get("x-client-trace-id") == "client-e2e-42" for c in stub.calls)
                assert all(c.body.get("stream") in (None, False) for c in stub.calls)
                assert len({c.body["messages"][0]["content"] for c in stub.calls}) == 1

                # 2) Standalone auth enforcement: missing/wrong key rejected with 401.
                status_401, body_401 = _request("POST", f"{pub}/v2/topic-tree", payload=topic_req)
                assert status_401 == 401
                assert json.loads(body_401)["error"]["code"] == "UNAUTHORIZED"

                # 3) Standalone mode with valid SERVICE_API_KEYS: document, folders, contents, refine.
                auth_standalone = {"Authorization": f"Bearer {service_key}"}
                for name, payload in (
                    ("document", ex.DOCUMENT),
                    (
                        "folders",
                        {
                            "mode": "create",
                            "use_case": "folders",
                            "folders": ex.FOLDERS_TREE,
                            "items": ex.FOLDER_ITEMS,
                            "frame": ex.FRAME,
                            "options": {"improve": True},
                        },
                    ),
                    ("contents", ex.CONTENTS),
                    ("refine", ex.FOLDERS_REFINE),
                ):
                    stub.reset()
                    st, raw = _request(
                        "POST", f"{pub}/v2/topic-tree", payload=copy.deepcopy(payload), headers=auth_standalone
                    )
                    assert st == 200, f"{name}: {st} {raw}"
                    parsed = json.loads(raw)
                    assert parsed["collection"], f"{name} returned empty collection"
                    assert parsed["metadata"]["generation"]["model"] == "gpt-6-luna"
                    assert all(c.path == "/v1/chat/completions" for c in stub.calls)
                    assert all("prompt_cache_key" in c.body for c in stub.calls)

                # 4) Internal metrics reflect the live requests and LLM calls.
                m_status, metrics_text = _request("GET", f"{internal}/metrics")
                assert m_status == 200
                assert 'topic_tree_requests_total{route="v2.topic_tree",status="200"}' in metrics_text
                assert 'topic_tree_llm_calls_total{outcome="ok",step="plan_structure"}' in metrics_text
                assert 'topic_tree_llm_tokens_total{kind="cached"}' in metrics_text
            finally:
                _stop(proc)
        output = log_path.read_text(encoding="utf-8", errors="replace")

    # Secrets and delegation tokens must never appear in stdout JSON logs.
    assert delegation_token not in output
    assert service_key not in output
    assert "sk-stub-local-key" not in output
