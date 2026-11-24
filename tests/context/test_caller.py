import pytest

from app.context.caller import resolve_caller
from app.errors import ApiError
from app.settings import Settings

TOKEN = "bdt_abc123"


def settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def bearer(value: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {value}"}


@pytest.mark.parametrize(
    ("mode", "headers", "expected"),
    [
        ("auto", bearer(TOKEN), "bapi"),
        ("auto", bearer("some-service-key"), "standalone"),
        ("auto", {}, "standalone"),
        ("bapi", bearer(TOKEN), "bapi"),
        ("standalone", bearer(TOKEN), "standalone"),
        ("standalone", bearer("other"), "standalone"),
        ("standalone", {}, "standalone"),
    ],
)
def test_mode_table_without_service_keys(mode: str, headers: dict, expected: str) -> None:
    ctx = resolve_caller(headers, settings(service_mode=mode))
    assert ctx.mode == expected
    assert ctx.delegation_token == (TOKEN if expected == "bapi" else None)


@pytest.mark.parametrize("headers", [bearer("other"), {}])
def test_bapi_mode_rejects_calls_without_delegation_token(headers: dict) -> None:
    with pytest.raises(ApiError) as err:
        resolve_caller(headers, settings(service_mode="bapi"))
    assert err.value.status == 401
    assert err.value.headers == {"WWW-Authenticate": "Bearer"}


@pytest.mark.parametrize("mode", ["auto", "standalone"])
def test_service_keys_are_required_when_configured(mode: str) -> None:
    s = settings(service_mode=mode, service_api_keys=["k1", "k2"])
    assert resolve_caller(bearer("k2"), s).mode == "standalone"
    for headers in (bearer("wrong"), {}):
        with pytest.raises(ApiError) as err:
            resolve_caller(headers, s)
        assert err.value.status == 401


def test_delegation_token_bypasses_service_keys_in_auto_mode() -> None:
    s = settings(service_mode="auto", service_api_keys=["k1"])
    assert resolve_caller(bearer(TOKEN), s).mode == "bapi"


def test_custom_delegation_header_carries_the_raw_token() -> None:
    s = settings(b_api_delegation_header="X-Delegation")
    ctx = resolve_caller({"x-delegation": TOKEN}, s)
    assert ctx.mode == "bapi"
    assert ctx.delegation_token == TOKEN


def test_lowercase_bearer_is_treated_as_missing() -> None:
    ctx = resolve_caller({"authorization": f"bearer {TOKEN}"}, settings())
    assert ctx.mode == "standalone"
    assert ctx.delegation_token is None


def test_token_is_hidden_from_repr() -> None:
    ctx = resolve_caller(bearer(TOKEN), settings())
    assert TOKEN not in repr(ctx)
