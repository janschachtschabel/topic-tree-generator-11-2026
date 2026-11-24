"""Probe which request features an LLM route supports (plan risks: GWDG models and strict JSON / cache keys).

Run:  B_API_KEY=... uv run python -m scripts.probe_llm --base-url https://b-api.../api/v1/llm/router/ --model topic-tree-generator
The key is read from the environment (B_API_KEY or OPENAI_API_KEY) and never printed.
"""

import argparse
import asyncio
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import openai

_MESSAGES = [{"role": "user", "content": 'Antworte nur mit JSON: {"ok": true}'}]
_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Probe:
    name: str
    body: dict[str, Any]


PROBES = [
    Probe("plain", {"max_tokens": 50}),
    Probe("common_body", {"max_completion_tokens": 50, "reasoning_effort": "none"}),
    Probe("json_object", {"max_completion_tokens": 50, "response_format": {"type": "json_object"}}),
    Probe(
        "json_schema",
        {
            "max_completion_tokens": 50,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "probe", "schema": _SCHEMA, "strict": True},
            },
        },
    ),
    Probe("prompt_cache_key", {"max_completion_tokens": 50, "prompt_cache_key": "topic-tree:probe"}),
]


async def run_probes(factory: Callable[..., Any], *, model: str, api_key: str, base_url: str | None) -> list[dict]:
    client = factory(api_key=api_key, base_url=base_url, max_retries=1)
    results = []
    for probe in PROBES:
        try:
            response = await client.chat.completions.create(model=model, messages=_MESSAGES, **probe.body)
            content = response.choices[0].message.content or ""
            results.append({"probe": probe.name, "ok": True, "valid_json": _is_json(content)})
        except openai.APIStatusError as exc:
            results.append({"probe": probe.name, "ok": False, "status": exc.status_code})
        except openai.APIError as exc:
            results.append({"probe": probe.name, "ok": False, "error": type(exc).__name__})
    return results


def _is_json(text: str) -> bool:
    try:
        json.loads(text)
    except ValueError:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    key = os.environ.get("B_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("set B_API_KEY or OPENAI_API_KEY")
    results = asyncio.run(run_probes(openai.AsyncOpenAI, model=args.model, api_key=key, base_url=args.base_url))
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
