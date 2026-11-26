"""Load `items_ref` and `fulltext.ref` (plan E6). Guarded against SSRF: https only, hosts from
REF_ALLOWED_HOSTS only (exact, or `.suffix` for subdomains), no redirects, size and time limits."""

import asyncio
import json
import time
from urllib.parse import urlsplit

import httpx
from pydantic import TypeAdapter, ValidationError

from app.errors import ApiError
from app.schemas.common import ItemUse
from app.schemas.request_v2 import Fulltext, Item, TopicTreeRequestV2
from app.settings import Settings

MAX_REF_ITEMS = 5000
MAX_FULLTEXT_CHARS = 2_000_000
MAX_CONCURRENT_REFS = 8
_ITEMS = TypeAdapter(list[Item])


def client_factory() -> httpx.AsyncClient:
    return httpx.AsyncClient()


def _host_allowed(host: str, rules: list[str]) -> bool:
    host = host.lower().rstrip(".")
    for rule in (r.lower() for r in rules):
        if rule.startswith(".") and host.endswith(rule):
            return True
        if host == rule:
            return True
    return False


def _check_url(url: str, settings: Settings) -> str:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.scheme != "https" or not _host_allowed(host, settings.ref_allowed_hosts):
        raise ApiError(422, "REF_NOT_ALLOWED", "Verweis auf diesen Host ist nicht erlaubt.", details={"host": host})
    return host


def _parse_content_length(raw: str | None) -> int:
    try:
        return int(raw) if raw else 0
    except ValueError:
        return 0


async def _read_response(client: httpx.AsyncClient, url: str, host: str, settings: Settings) -> str:
    failed = ApiError(422, "REF_FAILED", "Verweis konnte nicht geladen werden.", details={"host": host})
    try:
        # httpx timeouts apply per operation; the outer bound limits the whole download (slow-drip servers).
        async with (
            asyncio.timeout(settings.ref_timeout_seconds),
            client.stream("GET", url, timeout=settings.ref_timeout_seconds, follow_redirects=False) as response,
        ):
            if response.status_code != 200:
                raise failed
            if _parse_content_length(response.headers.get("content-length")) > settings.ref_max_bytes:
                raise _too_large(host)
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > settings.ref_max_bytes:
                    raise _too_large(host)
    except (httpx.HTTPError, TimeoutError) as exc:
        raise failed from exc
    return body.decode("utf-8", errors="replace")


async def fetch_text(url: str, settings: Settings, *, client: httpx.AsyncClient | None = None) -> str:
    host = _check_url(url, settings)
    if client is not None:
        return await _read_response(client, url, host, settings)
    async with client_factory() as own_client:
        return await _read_response(own_client, url, host, settings)


def _too_large(host: str) -> ApiError:
    return ApiError(422, "REF_TOO_LARGE", "Verweis überschreitet die erlaubte Größe.", details={"host": host})


async def _load_items(url: str, settings: Settings, client: httpx.AsyncClient) -> list[Item]:
    text = await fetch_text(url, settings, client=client)
    try:
        items = _ITEMS.validate_python(json.loads(text))
    except (ValueError, ValidationError) as exc:
        raise ApiError(422, "REF_INVALID", "items_ref liefert keine gültige Liste von Items.") from exc
    if len(items) > MAX_REF_ITEMS:
        raise ApiError(422, "ITEMS_TOO_LARGE", f"items_ref enthält mehr als {MAX_REF_ITEMS} Einträge.")
    return items


async def _with_fulltext(item: Item, settings: Settings, client: httpx.AsyncClient, gate: asyncio.Semaphore) -> Item:
    url = str(item.fulltext.ref)
    async with gate:
        text = await fetch_text(url, settings, client=client)
    if len(text) > MAX_FULLTEXT_CHARS:
        raise _too_large(urlsplit(url).hostname or "")
    return item.model_copy(update={"fulltext": Fulltext(format=item.fulltext.format, text=text)})


async def resolve_refs(
    req: TopicTreeRequestV2, settings: Settings, deadline: float | None = None
) -> TopicTreeRequestV2:
    """Return the request with referenced data loaded inline (same object if there is nothing to load).

    `deadline` (time.monotonic()) bounds all loading together, so slow refs cannot outlast the request."""
    has_inline_refs = any(
        i.fulltext and i.fulltext.ref and ItemUse.structure in req.effective_use(i) for i in req.items or []
    )
    if not req.items_ref and not has_inline_refs:
        return req
    remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
    try:
        async with asyncio.timeout(remaining):
            items = await _load_all(req, settings)
    except TimeoutError as exc:
        raise ApiError(
            422,
            "REF_FAILED",
            "Verweise konnten nicht innerhalb der Frist der Anfrage geladen werden.",
            details={"reason": "deadline"},
        ) from exc
    return req.model_copy(update={"items": items, "items_ref": None})


async def _load_all(req: TopicTreeRequestV2, settings: Settings) -> list[Item]:
    async with client_factory() as client:
        items = await _load_items(str(req.items_ref), settings, client) if req.items_ref else req.items
        probe = req.model_copy(update={"items": items})
        needs_text = [
            i for i in items or [] if i.fulltext and i.fulltext.ref and ItemUse.structure in probe.effective_use(i)
        ]
        gate = asyncio.Semaphore(MAX_CONCURRENT_REFS)
        loaded = await asyncio.gather(*(_with_fulltext(i, settings, client, gate) for i in needs_text))
    replaced = {i.id: i for i in loaded}
    return [replaced.get(i.id, i) for i in items or []]
