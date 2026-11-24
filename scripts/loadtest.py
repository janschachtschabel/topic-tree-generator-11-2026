"""Send N parallel requests to a running instance and report P50/P90 and the error rate (for the Steckbrief).

Run:  uv run python -m scripts.loadtest --url http://localhost:8000/v2/topic-tree --payload docs/examples/topic_full.json -n 10 -c 5
Pass the bearer via the TOKEN environment variable if the instance needs one (never on the command line).
"""

import argparse
import asyncio
import json
import math
import os
import time
from pathlib import Path

import httpx


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(p / 100 * len(ordered)) - 1)
    return ordered[index]


def summarize(results: list[tuple[int, float]]) -> dict:
    ok = [seconds for status, seconds in results if status == 200]
    errors = len(results) - len(ok)
    return {
        "requests": len(results),
        "errors": errors,
        "error_rate": round(errors / len(results), 3) if results else 0.0,
        "p50_s": percentile(ok, 50) if ok else None,
        "p90_s": percentile(ok, 90) if ok else None,
    }


async def _one(client: httpx.AsyncClient, url: str, payload: dict, gate: asyncio.Semaphore) -> tuple[int, float]:
    async with gate:
        start = time.perf_counter()
        try:
            response = await client.post(url, json=payload)
            status = response.status_code
        except httpx.HTTPError:
            status = 0
        return status, round(time.perf_counter() - start, 2)


async def run(url: str, payload: dict, n: int, concurrency: int) -> dict:
    headers = {"Authorization": f"Bearer {os.environ['TOKEN']}"} if os.environ.get("TOKEN") else {}
    gate = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient(timeout=600, headers=headers) as client:
        results = await asyncio.gather(*(_one(client, url, payload, gate) for _ in range(n)))
    return summarize(list(results))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--payload", required=True, type=Path)
    parser.add_argument("-n", type=int, default=10)
    parser.add_argument("-c", type=int, default=5)
    args = parser.parse_args()
    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    print(json.dumps(asyncio.run(run(args.url, payload, args.n, args.c)), indent=1))


if __name__ == "__main__":
    main()
