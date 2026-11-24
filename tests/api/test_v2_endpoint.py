import copy
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.api.examples import REQUEST_EXAMPLES
from app.domain.tree import Node
from app.main import create_app
from app.pipeline import orchestrator
from app.pipeline.orchestrator import StrategyResult
from app.pipeline.run_context import RunContext
from app.schemas.common import OriginType, UseCase
from app.schemas.request_v2 import TopicTreeRequestV2
from app.schemas.response_v2 import Origin
from app.settings import Settings
from scripts.export_schemas import SCHEMA_DIR, schemas
from tests.fakes.llm import FakeLLM
from tests.fixtures import spec_examples as ex


async def fake_topic_strategy(req: TopicTreeRequestV2, rc: RunContext) -> StrategyResult:
    children = [
        Node(key=None, title=t, description="wort " * 60, origin=Origin(type=OriginType.topic))
        for t in ("Licht", "Schatten", "Farben")
    ]
    roots = [
        Node(
            key=None,
            title=f"Thema {i}",
            description="wort " * 60,
            origin=Origin(type=OriginType.topic),
            children=[
                Node(key=None, title=f"{c.title} {i}", description=c.description, origin=c.origin) for c in children
            ],
        )
        for i in range(6)
    ]
    return StrategyResult(roots=roots, title=req.topic, description="Baum")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(orchestrator.STRATEGIES, UseCase.topic, fake_topic_strategy)
    fake = FakeLLM()

    def fake_context() -> RunContext:
        return RunContext(llm=fake, settings=Settings(_env_file=None), deadline=time.monotonic() + 60)

    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[deps.run_context] = fake_context
    return TestClient(app)


def test_v2_returns_a_valid_answer(client: TestClient) -> None:
    payload = copy.deepcopy(ex.TOPIC)
    payload["shape"]["depth"] = 2
    r = client.post("/v2/topic-tree", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["collection"]) == 6
    first = body["collection"][0]
    assert first["key"] == "k-thema-0"
    assert first["status"] == "new"
    assert first["properties"]["ccm:taxonid"] == [ex.DISC]
    assert first["subcollections"][0]["subcollections"] == []
    assert body["metadata"]["version"] == "v1"
    assert body["metadata"]["generation"]["model"] == "fake-route"
    assert body["warnings"] == []


def test_missing_input_is_a_422_with_code(client: TestClient) -> None:
    r = client.post("/v2/topic-tree", json={"mode": "create", "use_case": "topic", "frame": {}})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "MISSING_INPUT"


def test_use_case_without_strategy_yet_is_501(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(orchestrator.STRATEGIES, UseCase.contents, raising=False)
    r = client.post("/v2/topic-tree", json=ex.CONTENTS)
    assert r.status_code == 501
    assert r.json()["error"]["code"] == "NOT_IMPLEMENTED"


async def test_expired_deadline_adds_warning_to_partial_result() -> None:
    req = TopicTreeRequestV2.model_validate(copy.deepcopy(ex.TOPIC))

    async def slow(req: TopicTreeRequestV2, rc: RunContext) -> StrategyResult:
        rc.deadline = time.monotonic() - 1
        return StrategyResult(roots=[Node(key=None, title="A", origin=Origin(type=OriginType.topic))], title="Optik")

    rc = RunContext(llm=FakeLLM(), settings=Settings(_env_file=None), deadline=time.monotonic() + 60)
    resp = await orchestrator.run(req, rc, {UseCase.topic: slow})
    assert "DEADLINE_EXCEEDED" in [w.code for w in resp.warnings]
    assert resp.collection[0].title == "A"


def test_openapi_lists_v2_with_examples_and_bearer(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    op = spec["paths"]["/v2/topic-tree"]["post"]
    examples = op["requestBody"]["content"]["application/json"]["examples"]
    assert {"topic_minimal", "topic_full", "document", "folders", "contents", "refine_feedback"} <= set(examples)
    assert op["security"] == [{"HTTPBearer": []}]


@pytest.mark.parametrize("name", sorted(REQUEST_EXAMPLES))
def test_openapi_examples_are_valid_requests(name: str) -> None:
    TopicTreeRequestV2.model_validate(REQUEST_EXAMPLES[name]["value"])


def test_exported_json_schemas_are_current() -> None:
    for name, schema in schemas().items():
        path = Path(SCHEMA_DIR) / name
        assert path.exists(), f"run: uv run python -m scripts.export_schemas ({name} missing)"
        assert json.loads(path.read_text()) == schema, f"run: uv run python -m scripts.export_schemas ({name} stale)"


@pytest.mark.parametrize(
    ("status", "expected_status", "expected_code"), [(401, 401, "UNAUTHORIZED"), (403, 403, "FORBIDDEN")]
)
async def test_bapi_upstream_auth_errors_return_4xx(status: int, expected_status: int, expected_code: str) -> None:
    from app.errors import ApiError
    from app.llm.client import LLMStepError

    req = TopicTreeRequestV2.model_validate(copy.deepcopy(ex.TOPIC))

    async def fail_auth(req: TopicTreeRequestV2, rc: RunContext) -> StrategyResult:
        raise LLMStepError("plan_structure", "http_error", status)

    rc = RunContext(llm=FakeLLM(), settings=Settings(_env_file=None), deadline=time.monotonic() + 60, mode="bapi")
    with pytest.raises(ApiError) as err:
        await orchestrator.run(req, rc, {UseCase.topic: fail_auth})
    assert (err.value.status, err.value.code) == (expected_status, expected_code)
