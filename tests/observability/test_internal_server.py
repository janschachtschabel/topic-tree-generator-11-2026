import json
import urllib.error
import urllib.request

import pytest

from app.internal_server import start_internal_server
from app.observability import metrics
from app.settings import Settings


@pytest.fixture
def serve():
    servers = []

    def _start(settings: Settings) -> str:
        server = start_internal_server(settings, host="127.0.0.1", port=0)
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield _start
    for server in servers:
        server.shutdown()
        server.server_close()


def get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()


def test_health_reports_ok_version_and_vocab_snapshot(serve) -> None:
    status, body = get(serve(Settings(_env_file=None)) + "/health")
    data = json.loads(body)
    assert status == 200
    assert data["status"] == "ok"
    assert data["service"] == "topic-tree"
    assert data["version"]
    assert len(data["vocab_snapshot"]) == 10


def test_ready_in_auto_mode_without_local_llm(serve) -> None:
    assert get(serve(Settings(_env_file=None)) + "/ready")[0] == 200


def test_not_ready_in_standalone_mode_without_llm(serve) -> None:
    status, body = get(serve(Settings(_env_file=None, service_mode="standalone")) + "/ready")
    assert status == 503
    assert json.loads(body)["reason"] == "LLM_NOT_CONFIGURED"


def test_ready_in_standalone_mode_with_openai_key(serve) -> None:
    s = Settings(_env_file=None, service_mode="standalone", openai_api_key="sk-x")
    status, body = get(serve(s) + "/ready")
    assert status == 200
    assert "sk-x" not in body


def test_metrics_are_exposed_in_prometheus_format(serve) -> None:
    metrics.observe_request("v2.topic_tree", 200, 1.5)
    metrics.count_warning("DESCRIBE_FAILED")
    status, body = get(serve(Settings(_env_file=None)) + "/metrics")
    assert status == 200
    assert 'topic_tree_requests_total{route="v2.topic_tree",status="200"}' in body
    assert 'topic_tree_warnings_total{code="DESCRIBE_FAILED"}' in body


def test_unknown_internal_path_is_404(serve) -> None:
    assert get(serve(Settings(_env_file=None)) + "/nope")[0] == 404
