import json

from scripts.loadtest import percentile, summarize
from scripts.probe_llm import PROBES, run_probes
from tests.fakes.openai import FakeOpenAI


def test_percentiles_and_summary() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 10.0]
    assert percentile(values, 50) == 3.0
    assert percentile(values, 90) == 10.0
    # Nearest-rank method: with two successful runs, P50 is the first, P90 the second.
    report = summarize([(200, 1.0), (200, 3.0), (503, 0.5)])
    assert report == {"requests": 3, "errors": 1, "error_rate": 0.333, "p50_s": 1.0, "p90_s": 3.0}


async def test_probes_report_each_capability_without_leaking_the_key() -> None:
    fake = FakeOpenAI([json.dumps({"ok": True})])
    results = await run_probes(fake.factory, model="route-x", api_key="secret-key", base_url="https://b/router/")
    assert [r["probe"] for r in results] == [p.name for p in PROBES]
    assert all(r["ok"] for r in results)
    assert "secret-key" not in json.dumps(results)
    sent = {p.name: call for p, call in zip(PROBES, fake.calls, strict=True)}
    assert sent["json_schema"]["response_format"]["type"] == "json_schema"
    assert sent["prompt_cache_key"]["prompt_cache_key"] == "topic-tree:probe"
    assert sent["common_body"]["reasoning_effort"] == "none"
