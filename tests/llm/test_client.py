import asyncio
import time

import httpx
import openai
import pytest
from pydantic import BaseModel

from app.llm.backend import LLMBackend
from app.llm.client import LLMClient, LLMStepError
from app.llm.usage import UsageTracker
from app.settings import Settings
from tests.fakes.openai import FakeOpenAI, as_json


class Answer(BaseModel):
    title: str
    keywords: list[str]


GOOD = as_json({"title": "Optik", "keywords": ["Licht"]})
BACKEND = LLMBackend(
    kind="bapi", base_url="https://b/api/v1/llm/router/", model="route-x", send_cache_key=False, api_key="bdt_tok"
)


def make_client(fake: FakeOpenAI, deadline: float | None = None, backend: LLMBackend = BACKEND, **settings_kw):
    settings = Settings(_env_file=None, **settings_kw)
    return LLMClient(
        backend,
        settings,
        system_prompt="SYSTEM",
        usage=UsageTracker(),
        deadline=deadline,
        client_factory=fake.factory,
    )


async def test_common_family_sends_completion_tokens_and_no_reasoning() -> None:
    fake = FakeOpenAI([GOOD])
    result = await make_client(fake).complete_json("plan", "USER", Answer, max_tokens=900)
    assert result == Answer(title="Optik", keywords=["Licht"])
    call = fake.calls[0]
    assert call["model"] == "route-x"
    assert call["max_completion_tokens"] == 900
    assert call["reasoning_effort"] == "none"
    assert "temperature" not in call and "max_tokens" not in call
    assert call.get("stream") in (None, False)
    assert call["messages"] == [{"role": "system", "content": "SYSTEM"}, {"role": "user", "content": "USER"}]


async def test_classic_family_sends_max_tokens() -> None:
    fake = FakeOpenAI([GOOD])
    await make_client(fake, llm_param_family="classic").complete_json("plan", "USER", Answer, max_tokens=500)
    assert fake.calls[0]["max_tokens"] == 500
    assert "max_completion_tokens" not in fake.calls[0]
    assert "reasoning_effort" not in fake.calls[0]


async def test_common_family_allows_low_reasoning_effort() -> None:
    fake = FakeOpenAI([GOOD])
    await make_client(fake, llm_param_family="common", llm_reasoning_effort="low").complete_json("plan", "U", Answer)
    assert fake.calls[0]["reasoning_effort"] == "low"


async def test_gpt5_family_caps_reasoning_effort_at_low() -> None:
    fake = FakeOpenAI([GOOD])
    await make_client(fake, llm_param_family="gpt5").complete_json("plan", "U", Answer, max_tokens=700)
    assert fake.calls[0]["max_completion_tokens"] == 700
    assert fake.calls[0]["reasoning_effort"] == "low"

    fake_min = FakeOpenAI([GOOD])
    await make_client(fake_min, llm_param_family="gpt5", llm_reasoning_effort="minimal").complete_json(
        "plan", "U", Answer
    )
    assert fake_min.calls[0]["reasoning_effort"] == "minimal"


async def test_json_schema_mode_sends_strict_schema_named_after_step() -> None:
    fake = FakeOpenAI([GOOD])
    await make_client(fake).complete_json("plan_structure", "USER", Answer)
    rf = fake.calls[0]["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["name"] == "plan_structure"
    assert rf["json_schema"]["strict"] is True
    schema = rf["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert sorted(schema["required"]) == ["keywords", "title"]


@pytest.mark.parametrize("mode", ["json_object", "prompt"])
async def test_other_modes_append_schema_at_the_end_of_the_user_message(mode: str) -> None:
    fake = FakeOpenAI([GOOD])
    await make_client(fake, llm_output_mode=mode).complete_json("plan", "USER", Answer)
    user = fake.calls[0]["messages"][1]["content"]
    assert user.startswith("USER")
    assert '"keywords"' in user and "JSON" in user
    if mode == "json_object":
        assert fake.calls[0]["response_format"] == {"type": "json_object"}
    else:
        assert "response_format" not in fake.calls[0]


async def test_code_fences_are_tolerated() -> None:
    fake = FakeOpenAI([f"```json\n{GOOD}\n```"])
    assert (await make_client(fake).complete_json("plan", "U", Answer)).title == "Optik"


async def test_invalid_json_gets_exactly_one_repair_attempt() -> None:
    fake = FakeOpenAI(["not json", GOOD])
    result = await make_client(fake).complete_json("plan", "USER", Answer)
    assert result.title == "Optik"
    assert len(fake.calls) == 2
    repair = fake.calls[1]["messages"]
    assert repair[:2] == fake.calls[0]["messages"]
    assert repair[2] == {"role": "assistant", "content": "not json"}
    assert repair[3]["role"] == "user" and "JSON" in repair[3]["content"]


async def test_second_invalid_answer_raises_step_error() -> None:
    fake = FakeOpenAI(["nope", as_json({"title": 1})])
    with pytest.raises(LLMStepError) as err:
        await make_client(fake).complete_json("plan", "USER", Answer)
    assert err.value.step == "plan"
    assert err.value.reason == "invalid_output"
    assert len(fake.calls) == 2


async def test_transport_errors_become_step_errors_with_status() -> None:
    request = httpx.Request("POST", "https://b/x")
    error = openai.APIStatusError("boom", response=httpx.Response(503, request=request), body=None)
    fake = FakeOpenAI([error])
    with pytest.raises(LLMStepError) as err:
        await make_client(fake).complete_json("plan", "USER", Answer)
    assert (err.value.reason, err.value.status) == ("http_error", 503)


async def test_client_is_built_with_token_retries_and_trace_headers_only() -> None:
    fake = FakeOpenAI([GOOD])
    await make_client(fake, llm_max_retries=5).complete_json("plan", "USER", Answer)
    built = fake.constructed[0]
    assert built["api_key"] == "bdt_tok"
    assert built["base_url"] == "https://b/api/v1/llm/router/"
    assert built["max_retries"] == 5
    headers = {k.lower() for k in built["default_headers"]}
    assert "x-b3-traceid" in headers
    assert not any(h.startswith("x-edu") or h == "x-api-key" for h in headers)


async def test_prompt_cache_key_only_when_backend_allows_it() -> None:
    fake = FakeOpenAI([GOOD])
    await make_client(fake).complete_json("plan", "U", Answer)
    assert "prompt_cache_key" not in fake.calls[0].get("extra_body", {}) and "prompt_cache_key" not in fake.calls[0]
    on = LLMBackend(kind="openai", base_url=None, model="m", send_cache_key=True, api_key="k")
    fake2 = FakeOpenAI([GOOD])
    await make_client(fake2, backend=on).complete_json("plan", "U", Answer)
    assert fake2.calls[0]["prompt_cache_key"] == "topic-tree:plan"


async def test_concurrency_is_capped_per_process() -> None:
    fake = FakeOpenAI([GOOD], delay=0.02)
    client = make_client(fake, llm_max_concurrency=3)
    await asyncio.gather(*(client.complete_json("plan", "U", Answer) for _ in range(12)))
    assert fake.max_active == 3


async def test_usage_is_accumulated() -> None:
    fake = FakeOpenAI([GOOD])
    client = make_client(fake)
    await client.complete_json("plan", "U", Answer)
    await client.complete_json("plan_structure", "U", Answer)
    u = client.usage.snapshot()
    assert (u["llm_calls"], u["prompt_tokens"], u["cached_tokens"], u["completion_tokens"]) == (2, 200, 0, 100)


async def test_timeout_is_bounded_by_the_request_deadline() -> None:
    fake = FakeOpenAI([GOOD])
    await make_client(fake, deadline=time.monotonic() + 30).complete_json("plan", "U", Answer)
    assert 25 < fake.calls[0]["timeout"] <= 30


async def test_expired_deadline_raises_without_calling() -> None:
    fake = FakeOpenAI([GOOD])
    with pytest.raises(LLMStepError) as err:
        await make_client(fake, deadline=time.monotonic() - 1).complete_json("plan", "U", Answer)
    assert err.value.reason == "deadline"
    assert fake.calls == []


async def test_request_deadline_bounds_the_whole_call_including_sdk_retries() -> None:
    # Audit 2026-11-25 #4: the SDK applies `timeout` per attempt, so retries could run past the deadline.
    fake = FakeOpenAI([GOOD], delay=5)
    started = time.monotonic()
    with pytest.raises(LLMStepError) as err:
        await make_client(fake, deadline=time.monotonic() + 1.5).complete_json("plan", "USER", Answer)
    assert err.value.reason == "deadline"
    assert time.monotonic() - started < 2.5


async def test_waiting_for_a_concurrency_slot_counts_against_the_deadline() -> None:
    fake = FakeOpenAI([GOOD], delay=1.2)
    client = make_client(fake, deadline=time.monotonic() + 1.6, llm_max_concurrency=1)
    started = time.monotonic()
    results = await asyncio.gather(
        client.complete_json("a", "USER", Answer), client.complete_json("b", "USER", Answer), return_exceptions=True
    )
    assert sum(isinstance(r, LLMStepError) and r.reason == "deadline" for r in results) == 1
    assert time.monotonic() - started < 2.2


async def test_attempt_timeout_with_request_time_left_stays_a_retryable_timeout() -> None:
    # Review of audit fix #4: only the request deadline is "deadline"; a slow attempt is still "timeout".
    fake = FakeOpenAI([GOOD], delay=5, honor_timeout=True)
    client = make_client(fake, deadline=time.monotonic() + 60, llm_timeout_seconds=1, llm_max_retries=0)
    with pytest.raises(LLMStepError) as err:
        await client.complete_json("plan", "USER", Answer)
    assert err.value.reason == "timeout"
