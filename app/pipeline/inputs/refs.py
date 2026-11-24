"""Load `items_ref` and `fulltext.ref` (plan E6). Guarded against SSRF: https only, hosts from
REF_ALLOWED_HOSTS only (exact, or `.suffix` for subdomains), no redirects, size and time limits."""

import asyncio
import json
from urllib.parse import urlsplit

import httpx
from pydantic import TypeAdapter, ValidationError

from app.errors import ApiError
from app.schemas.common import ItemUse
from app.schemas.request_v2 import Fulltext, Item, TopicTreeRequestV2
from app.settings import Settings

MAX_REF_ITEMS = 5000
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


async def fetch_text(url: str, settings: Settings) -> str:
    host = _check_url(url, settings)
    failed = ApiError(422, "REF_FAILED", "Verweis konnte nicht geladen werden.", details={"host": host})
    try:
        async with (
            client_factory() as client,
            client.stream("GET", url, timeout=settings.ref_timeout_seconds, follow_redirects=False) as response,
        ):
            if response.status_code != 200:
                raise failed
            declared = int(response.headers.get("content-length") or 0)
            if declared > settings.ref_max_bytes:
                raise _too_large(host)
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > settings.ref_max_bytes:
                    raise _too_large(host)
    except httpx.HTTPError as exc:
        raise failed from exc
    return body.decode("utf-8", errors="replace")


def _too_large(host: str) -> ApiError:
    return ApiError(422, "REF_TOO_LARGE", "Verweis überschreitet die erlaubte Größe.", details={"host": host})


async def _load_items(url: str, settings: Settings) -> list[Item]:
    text = await fetch_text(url, settings)
    try:
        items = _ITEMS.validate_python(json.loads(text))
    except (ValueError, ValidationError) as exc:
        raise ApiError(422, "REF_INVALID", "items_ref liefert keine gültige Liste von Items.") from exc
    if len(items) > MAX_REF_ITEMS:
        raise ApiError(422, "ITEMS_TOO_LARGE", f"items_ref enthält mehr als {MAX_REF_ITEMS} Einträge.")
    return items


async def _with_fulltext(item: Item, settings: Settings) -> Item:
    text = await fetch_text(str(item.fulltext.ref), settings)
    return item.model_copy(update={"fulltext": Fulltext(format=item.fulltext.format, text=text)})


async def resolve_refs(req: TopicTreeRequestV2, settings: Settings) -> TopicTreeRequestV2:
    """Return the request with referenced data loaded inline (same object if there is nothing to load)."""
    items = await _load_items(str(req.items_ref), settings) if req.items_ref else req.items
    probe = req.model_copy(update={"items": items})
    needs_text = [
        i for i in items or [] if i.fulltext and i.fulltext.ref and ItemUse.structure in probe.effective_use(i)
    ]
    if not req.items_ref and not needs_text:
        return req
    loaded = await asyncio.gather(*(_with_fulltext(i, settings) for i in needs_text))
    replaced = {i.id: i for i in loaded}
    items = [replaced.get(i.id, i) for i in items or []]
    return req.model_copy(update={"items": items, "items_ref": None})
