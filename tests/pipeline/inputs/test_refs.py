import copy
import json

import httpx
import pytest

from app.errors import ApiError
from app.pipeline.inputs import refs
from app.pipeline.inputs.refs import fetch_text, resolve_refs
from app.schemas.request_v2 import TopicTreeRequestV2
from app.settings import Settings
from tests.fixtures import spec_examples as ex

ALLOWED = Settings(_env_file=None, ref_allowed_hosts=["files.example.org", ".cdn.example.org"], ref_max_bytes=1000)


class _Stream(httpx.AsyncByteStream):
    def __init__(self, data: bytes) -> None:
        self.data = data

    async def __aiter__(self):
        yield self.data


def _streamed(handler):
    """Serve the handler's response as a network stream (raw bytes, not read ahead) like a real server."""

    def wrapped(request: httpx.Request) -> httpx.Response:
        response = handler(request)
        if not isinstance(response.stream, httpx.ByteStream):
            return response  # already a live stream (e.g. a slow drip)
        raw = b"".join(response.stream)
        return httpx.Response(response.status_code, headers=response.headers, stream=_Stream(raw))

    return wrapped


def transport(handler):
    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(_streamed(handler)))


@pytest.fixture
def serve(monkeypatch: pytest.MonkeyPatch):
    seen: list[str] = []

    def install(handler):
        def wrapped(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            return handler(request)

        monkeypatch.setattr(refs, "client_factory", transport(wrapped))
        return seen

    return install


async def test_allowed_host_returns_text(serve) -> None:
    serve(lambda r: httpx.Response(200, text="# Lehrplan"))
    assert await fetch_text("https://files.example.org/a.md", ALLOWED) == "# Lehrplan"


async def test_subdomain_rule_with_leading_dot(serve) -> None:
    serve(lambda r: httpx.Response(200, text="ok"))
    assert await fetch_text("https://eu.cdn.example.org/a.md", ALLOWED) == "ok"


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example.com/a.md",
        "https://files.example.org.evil.com/a",
        "https://cdn.example.org/a.md",
        "http://files.example.org/a.md",
        "https://127.0.0.1/a",
    ],
)
async def test_disallowed_urls_are_rejected_without_a_request(serve, url: str) -> None:
    seen = serve(lambda r: httpx.Response(200, text="x"))
    with pytest.raises(ApiError) as err:
        await fetch_text(url, ALLOWED)
    assert (err.value.status, err.value.code) == (422, "REF_NOT_ALLOWED")
    assert seen == []


async def test_empty_allowlist_rejects_everything(serve) -> None:
    serve(lambda r: httpx.Response(200, text="x"))
    with pytest.raises(ApiError) as err:
        await fetch_text("https://files.example.org/a.md", Settings(_env_file=None))
    assert err.value.code == "REF_NOT_ALLOWED"


async def test_redirects_are_not_followed(serve) -> None:
    serve(lambda r: httpx.Response(302, headers={"Location": "https://evil.example.com/"}))
    with pytest.raises(ApiError) as err:
        await fetch_text("https://files.example.org/a.md", ALLOWED)
    assert err.value.code == "REF_FAILED"


async def test_too_large_bodies_are_aborted(serve) -> None:
    serve(lambda r: httpx.Response(200, content=b"x" * 5000))
    with pytest.raises(ApiError) as err:
        await fetch_text("https://files.example.org/a.md", ALLOWED)
    assert err.value.code == "REF_TOO_LARGE"


async def test_errors_and_timeouts_are_ref_failed(serve) -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    serve(boom)
    with pytest.raises(ApiError) as err:
        await fetch_text("https://files.example.org/a.md", ALLOWED)
    assert err.value.code == "REF_FAILED"
    assert "files.example.org" in json.dumps(err.value.details)


async def test_resolve_refs_loads_items_and_fulltexts(serve) -> None:
    items = [
        {"id": "d1", "use": ["structure"], "fulltext": {"ref": "https://files.example.org/d1.md"}},
        {"id": "c1", "properties": {"cm:title": ["Licht"]}},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/items.json":
            return httpx.Response(200, json=items)
        return httpx.Response(200, text="## Themenfeld 1")

    serve(handler)
    data = copy.deepcopy(ex.DOCUMENT)
    data["items"] = None
    data["items_ref"] = "https://files.example.org/items.json"
    req = TopicTreeRequestV2.model_validate(data)
    resolved = await resolve_refs(req, Settings(_env_file=None, ref_allowed_hosts=["files.example.org"]))
    assert resolved.items_ref is None
    assert [i.id for i in resolved.items] == ["d1", "c1"]
    assert resolved.items[0].fulltext.text == "## Themenfeld 1"
    assert resolved.items[0].fulltext.ref is None


async def test_invalid_items_document_is_rejected(serve) -> None:
    serve(lambda r: httpx.Response(200, json={"not": "a list"}))
    data = {**copy.deepcopy(ex.CONTENTS), "items": None, "items_ref": "https://files.example.org/items.json"}
    with pytest.raises(ApiError) as err:
        await resolve_refs(TopicTreeRequestV2.model_validate(data), ALLOWED)
    assert err.value.code == "REF_INVALID"


async def test_request_without_refs_is_returned_unchanged() -> None:
    req = TopicTreeRequestV2.model_validate(copy.deepcopy(ex.DOCUMENT))
    assert await resolve_refs(req, ALLOWED) is req


async def test_malformed_content_length_header_does_not_crash(serve) -> None:
    serve(lambda r: httpx.Response(200, content=b"ok", headers={"Content-Length": "not-a-number"}))
    assert await fetch_text("https://files.example.org/a.md", ALLOWED) == "ok"


async def test_fetched_fulltext_exceeding_model_limit_raises_ref_too_large(serve) -> None:
    big = "a" * (refs.MAX_FULLTEXT_CHARS + 1)
    serve(lambda r: httpx.Response(200, text=big))
    data = copy.deepcopy(ex.DOCUMENT)
    data["items"][0]["fulltext"] = {"format": "markdown", "ref": "https://files.example.org/big.md"}
    req = TopicTreeRequestV2.model_validate(data)
    with pytest.raises(ApiError) as err:
        await resolve_refs(
            req, Settings(_env_file=None, ref_allowed_hosts=["files.example.org"], ref_max_bytes=10 * 1024 * 1024)
        )
    assert err.value.code == "REF_TOO_LARGE"


async def test_resolve_refs_caps_concurrent_fetches(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    active = 0
    max_active = 0

    class SlowTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            try:
                await asyncio.sleep(0.02)
                return httpx.Response(200, text="# Ok")
            finally:
                active -= 1

    monkeypatch.setattr(refs, "client_factory", lambda: httpx.AsyncClient(transport=SlowTransport()))
    items = [
        {"id": f"d{i}", "use": ["structure"], "fulltext": {"ref": f"https://files.example.org/{i}.md"}}
        for i in range(20)
    ]
    data = {**copy.deepcopy(ex.DOCUMENT), "items": items}
    await resolve_refs(TopicTreeRequestV2.model_validate(data), ALLOWED)
    assert 1 <= max_active <= refs.MAX_CONCURRENT_REFS


async def test_slow_drip_response_is_cut_at_the_total_time_limit(serve) -> None:
    # Audit 2026-11-25 #5: httpx timeouts apply per read, so a server sending tiny chunks never timed out.
    import asyncio
    import time

    async def drip():
        for _ in range(20):
            await asyncio.sleep(0.2)
            yield b"x"

    serve(lambda r: httpx.Response(200, content=drip()))
    settings = Settings(_env_file=None, ref_allowed_hosts=["files.example.org"], ref_timeout_seconds=1)
    started = time.monotonic()
    with pytest.raises(ApiError) as err:
        await fetch_text("https://files.example.org/a.md", settings)
    assert err.value.code == "REF_FAILED"
    assert time.monotonic() - started < 2


async def test_loading_refs_stops_at_the_request_deadline(serve) -> None:
    # Audit 2026-11-26: refs loaded outside the request deadline (40 slow documents took far longer than allowed).
    import asyncio
    import time

    async def slow():
        await asyncio.sleep(0.5)
        yield b"## Titel"

    serve(lambda r: httpx.Response(200, content=slow()))
    data = copy.deepcopy(ex.DOCUMENT)
    data["items"] = [
        {"id": f"d{i}", "use": ["structure"], "fulltext": {"ref": f"https://files.example.org/{i}.md"}}
        for i in range(40)
    ]
    settings = Settings(_env_file=None, ref_allowed_hosts=["files.example.org"], ref_timeout_seconds=5)
    started = time.monotonic()
    with pytest.raises(ApiError) as err:
        await resolve_refs(TopicTreeRequestV2.model_validate(data), settings, deadline=started + 1)
    assert err.value.code == "REF_FAILED"
    assert time.monotonic() - started < 1.5


def _doc_items(urls: list[str]) -> dict:
    items = [{"id": f"d{i}", "use": ["structure"], "fulltext": {"ref": url}} for i, url in enumerate(urls)]
    return {**copy.deepcopy(ex.DOCUMENT), "items": items}


async def test_the_same_ref_url_is_fetched_once(serve) -> None:
    # Regression: 300 items pointing at one URL meant 300 downloads held in memory at once.
    seen = serve(lambda r: httpx.Response(200, text="# Lehrplan"))
    req = TopicTreeRequestV2.model_validate(_doc_items(["https://files.example.org/a.md"] * 3))
    resolved = await resolve_refs(req, ALLOWED)
    assert len(seen) == 1
    assert [i.fulltext.text for i in resolved.items] == ["# Lehrplan"] * 3


async def test_loaded_full_texts_have_a_total_cap(serve, monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: every ref was capped alone, but many distinct refs together could exhaust the pod's memory.
    monkeypatch.setattr(refs, "MAX_TOTAL_FULLTEXT_CHARS", 25)
    serve(lambda r: httpx.Response(200, text="x" * 10))
    urls = [f"https://files.example.org/{i}.md" for i in range(3)]
    with pytest.raises(ApiError) as err:
        await resolve_refs(TopicTreeRequestV2.model_validate(_doc_items(urls)), ALLOWED)
    assert err.value.code == "REF_TOO_LARGE"


async def test_compressed_bodies_are_limited_by_their_decoded_size(serve) -> None:
    # Regression: Content-Length and the size check saw compressed bytes; a gzip bomb expanded in memory first.
    import gzip

    bomb = gzip.compress(b"a" * 50_000)
    accepted: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        accepted.append(request.headers.get("accept-encoding"))
        return httpx.Response(200, content=bomb, headers={"Content-Encoding": "gzip"})

    serve(handler)
    with pytest.raises(ApiError) as err:
        await fetch_text("https://files.example.org/a.md", ALLOWED)
    assert err.value.code == "REF_TOO_LARGE"
    assert accepted == ["identity"]


async def test_small_compressed_bodies_are_decoded(serve) -> None:
    import gzip

    serve(
        lambda r: httpx.Response(200, content=gzip.compress("# Läuft".encode()), headers={"Content-Encoding": "gzip"})
    )
    assert await fetch_text("https://files.example.org/a.md", ALLOWED) == "# Läuft"


async def test_data_after_the_end_of_a_gzip_stream_is_bounded(serve) -> None:
    # Review: zlib keeps bytes after the gzip end in unused_data, so only the raw size can bound them.
    import gzip

    async def body():  # streamed without Content-Length, so only the read loop can stop it
        yield gzip.compress(b"hi")
        for _ in range(5):
            yield b"\0" * 1000

    serve(lambda r: httpx.Response(200, content=body(), headers={"Content-Encoding": "gzip"}))
    with pytest.raises(ApiError) as err:
        await fetch_text("https://files.example.org/a.md", ALLOWED)
    assert err.value.code == "REF_TOO_LARGE"


async def test_raw_deflate_bodies_are_decoded(serve) -> None:
    import zlib

    packer = zlib.compressobj(wbits=-15)
    raw = packer.compress(b"# Roh") + packer.flush()
    serve(lambda r: httpx.Response(200, content=raw, headers={"Content-Encoding": "deflate"}))
    assert await fetch_text("https://files.example.org/a.md", ALLOWED) == "# Roh"
