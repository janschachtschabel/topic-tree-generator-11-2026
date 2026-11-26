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


def test_readiness_checks_bapi_route_or_model_when_required(serve) -> None:
    bapi_empty = Settings(_env_file=None, service_mode="bapi")
    status, body = get(serve(bapi_empty) + "/ready")
    assert status == 503
    assert json.loads(body)["reason"] == "LLM_NOT_CONFIGURED"

    bapi_route = Settings(_env_file=None, service_mode="bapi", b_api_route="topic-tree-generator")
    assert get(serve(bapi_route) + "/ready")[0] == 200

    bapi_model = Settings(_env_file=None, service_mode="bapi", b_api_model="gpt-6-luna")
    assert get(serve(bapi_model) + "/ready")[0] == 200

    dev_incomplete = Settings(_env_file=None, service_mode="standalone", b_api_dev_key="dev-secret")
    assert get(serve(dev_incomplete) + "/ready")[0] == 503


def test_metrics_are_exposed_in_prometheus_format(serve) -> None:
    class DummyDetails:
        cached_tokens = 120

    class DummyUsage:
        prompt_tokens = 200
        completion_tokens = 50
        prompt_tokens_details = DummyDetails()

    metrics.observe_request("v2.topic_tree", 200, 1.5)
    metrics.observe_llm("plan_structure", "ok", 0.8, DummyUsage())
    metrics.count_warning("DESCRIBE_FAILED")
    status, body = get(serve(Settings(_env_file=None)) + "/metrics")
    assert status == 200
    assert 'topic_tree_requests_total{route="v2.topic_tree",status="200"}' in body
    assert 'topic_tree_llm_tokens_total{kind="cached"}' in body
    assert 'topic_tree_warnings_total{code="DESCRIBE_FAILED"}' in body


def test_unknown_internal_path_is_404(serve) -> None:
    assert get(serve(Settings(_env_file=None)) + "/nope")[0] == 404


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "HEAD"])
def test_other_methods_get_a_json_405_instead_of_an_html_page(serve, method: str) -> None:
    # Final audit: the stdlib answered 501 with an HTML error page.
    request = urllib.request.Request(serve(Settings(_env_file=None)) + "/metrics", method=method, data=b"")
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(request, timeout=5)
    assert err.value.code == 405
    assert err.value.headers["Content-Type"] == "application/json"
    assert err.value.headers["Allow"] == "GET"
    if method != "HEAD":
        assert json.loads(err.value.read()) == {"status": "method_not_allowed"}
