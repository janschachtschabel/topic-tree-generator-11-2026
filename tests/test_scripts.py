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


def test_preset_summary_counts_levels_descriptions_duplicates_and_assignment() -> None:
    from scripts.run_presets import markdown_table, summarize

    request = {"shape": {"main_topics": {"min": 2, "max": 4}}, "items": [{"id": "a"}, {"id": "n", "use": []}]}
    response = {
        "metadata": {"generation": {"usage": {"llm_calls": 3, "prompt_tokens": 100, "completion_tokens": 20}}},
        "collection": [
            {
                "title": "A",
                "properties": {"cm:description": ["x"]},
                "contents": [{"id": "a", "confidence": 0.9}],
                "subcollections": [{"title": "a", "properties": {}}],
            },
            {"title": "B", "properties": {"cm:description": ["y"]}},
        ],
        "unassigned": [],
        "warnings": [{"code": "DESCRIBE_FAILED"}],
    }
    row = summarize("p", "topic", request, response, 1.234)
    assert row["levels"] == {1: 2, 2: 1}
    assert row["described_pct"] == 67
    assert row["duplicates"] == 1
    assert row["main_in_shape"] is True
    assert row["assigned"] == 1
    assert row["warnings"] == ["DESCRIBE_FAILED"]
    assert "| p | topic | 3 (2/1/0) | 67 % | 1 | 1 / 0 | DESCRIBE_FAILED | 3 | 120 (0) |" in markdown_table([row])
