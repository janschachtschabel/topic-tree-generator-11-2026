"""Run every test UI preset against a running service and report quality, run time and tokens per preset.

Run:  uv run python -m scripts.run_presets --url http://localhost:8000 [--only topic_sek1,refine_changes] [--out dir]
A service key (standalone mode) is read from SERVICE_KEY and never printed. Each answer is saved as JSON in --out,
and a Markdown table is printed. A follow-up refine of the first `topic` result checks the combination
"generate, then change and add materials".
"""

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

from app.ui.presets import PRESETS

CHAIN_FEEDBACK = "Ergänze ein Hauptthema zu Alltagsanwendungen und beschreibe es kurz."
CHAIN_ITEMS = [
    {"id": "chain1", "use": ["content"], "properties": {"cm:title": ["Alltagsbeispiele sammeln"]}},
    {"id": "chain2", "use": ["content"], "properties": {"cm:title": ["Kochrezept Linsensuppe"]}},
]


def _walk(nodes: list[dict], depth: int = 1):
    for node in nodes:
        yield node, depth
        yield from _walk(node.get("subcollections") or [], depth + 1)


def _description(node: dict) -> str:
    values = (node.get("properties") or {}).get("cm:description") or [""]
    return str(values[0])


def summarize(preset_id: str, task: str, request: dict, response: dict, seconds: float) -> dict[str, Any]:
    """Key figures of one answer; pure so it can be tested without a service."""
    nodes = list(_walk(response.get("collection") or []))
    by_level: dict[int, int] = {}
    for _, depth in nodes:
        by_level[depth] = by_level.get(depth, 0) + 1
    described = sum(1 for node, _ in nodes if _description(node).strip())
    titles = [(node.get("title") or "").strip().lower() for node, _ in nodes]
    usage = (response.get("metadata") or {}).get("generation", {}).get("usage") or {}
    sent_content = {i["id"] for i in request.get("items") or [] if "content" in i.get("use", ["content"])}
    placed = {c["id"] for node, _ in nodes for c in node.get("contents") or []}
    shape = request.get("shape") or {}
    main = shape.get("main_topics") or {}
    main_count = by_level.get(1, 0)
    return {
        "id": preset_id,
        "task": task,
        "nodes": len(nodes),
        "levels": dict(sorted(by_level.items())),
        "described_pct": round(100 * described / len(nodes)) if nodes else 0,
        "duplicates": len(titles) - len(set(titles)),
        "main_in_shape": (main.get("min") or 0) <= main_count <= (main.get("max") or 10**6),
        "assigned": len(placed & sent_content) if sent_content else len(placed),
        "unassigned": [u.get("id") for u in response.get("unassigned") or []],
        "warnings": [w.get("code") for w in response.get("warnings") or []],
        "questions": len(response.get("questions") or []),
        "llm_calls": usage.get("llm_calls", 0),
        "failed_calls": usage.get("failed_calls", 0),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "cached_tokens": usage.get("cached_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "service_s": round(usage.get("duration_ms", 0) / 1000, 1),
        "wall_s": round(seconds, 1),
    }


def chain_request(base_response: dict) -> dict:
    """Refine of an earlier answer with text feedback plus new materials (one fits, one is off topic)."""
    generation = base_response["metadata"]["generation"]
    current = {
        "title": base_response["metadata"]["title"],
        "version": base_response["metadata"]["version"],
        "generation": generation,
        "collection": base_response["collection"],
    }
    return {
        "mode": "refine",
        "use_case": generation["use_case"],
        "frame": generation["frame"],
        "current_tree": current,
        "feedback": {"text": CHAIN_FEEDBACK},
        "items": CHAIN_ITEMS,
    }


def markdown_table(rows: list[dict]) -> str:
    head = "| Beispiel | Aufgabe | Knoten (je Ebene) | beschr. | Dupl. | zugeord. / nicht | Warnungen | Calls | Tokens (Cache) | Zeit s |"
    lines = [head, "|" + "---|" * 10]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['id']} | {r['task']} | Fehler: {r['error']} | | | | | | | {r.get('wall_s', '')} |")
            continue
        depth = max([3, *(int(k) for k in r["levels"])])
        levels = "/".join(str(r["levels"].get(k, r["levels"].get(str(k), 0))) for k in range(1, depth + 1))
        tokens = r["prompt_tokens"] + r["completion_tokens"]
        lines.append(
            f"| {r['id']} | {r['task']} | {r['nodes']} ({levels}) | {r['described_pct']} % | {r['duplicates']} | "
            f"{r['assigned']} / {len(r['unassigned'])} | {', '.join(r['warnings']) or '–'} | {r['llm_calls']} | "
            f"{tokens} ({r['cached_tokens']}) | {r['service_s']} |"
        )
    return "\n".join(lines)


def _save(path: Path, data: Any) -> None:
    """UTF-8 regardless of the platform's default encoding (cp1252 on Windows)."""
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _post(client: httpx.Client, url: str, body: dict) -> tuple[dict, float]:
    started = time.monotonic()
    resp = client.post(f"{url}/v2/topic-tree", json=body)
    seconds = time.monotonic() - started
    if resp.status_code != 200:
        try:
            code = (resp.json().get("error") or {}).get("code", "")
        except ValueError:
            code = ""
        raise RuntimeError(f"HTTP {resp.status_code} {code}".strip())
    return resp.json(), seconds


def run(url: str, only: set[str] | None, out: Path, timeout: float) -> list[dict]:
    headers = {"Authorization": f"Bearer {os.environ['SERVICE_KEY']}"} if os.environ.get("SERVICE_KEY") else {}
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    chain_base = None
    with httpx.Client(timeout=timeout, headers=headers) as client:
        for preset in PRESETS:
            if only and preset["id"] not in only:
                continue
            body = preset["payload"]
            try:
                answer, seconds = _post(client, url, body)
            except (RuntimeError, httpx.HTTPError) as exc:
                rows.append({"id": preset["id"], "task": preset["task"], "error": str(exc)[:80]})
                continue
            _save(out / f"{preset['id']}.json", answer)
            rows.append(summarize(preset["id"], preset["task"], body, answer, seconds))
            if chain_base is None and preset["task"] == "topic":
                chain_base = answer
        if chain_base is not None and (not only or "chain_refine" in only):
            body = chain_request(chain_base)
            try:
                answer, seconds = _post(client, url, body)
                _save(out / "chain_refine.json", answer)
                rows.append(summarize("chain_refine", "refine", body, answer, seconds))
            except (RuntimeError, httpx.HTTPError) as exc:
                rows.append({"id": "chain_refine", "task": "refine", "error": str(exc)[:80]})
    _save(out / "summary.json", rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument(
        "--only", default="", help="comma-separated preset ids; chain_refine also needs a topic preset in the list"
    )
    parser.add_argument("--out", default="preset-runs")
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    only = {p.strip() for p in args.only.split(",") if p.strip()} or None
    print(markdown_table(run(args.url.rstrip("/"), only, Path(args.out), args.timeout)))


if __name__ == "__main__":
    main()
