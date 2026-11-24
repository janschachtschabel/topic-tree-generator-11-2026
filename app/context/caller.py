"""Who is calling, and through which path: behind the b-api (delegation token) or standalone.

The delegation token is kept only in memory for the duration of one request and is never logged.
"""

import hmac
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from app.errors import ApiError
from app.settings import Settings

DELEGATION_PREFIX = "bdt_"
_BEARER = "Bearer "
_UNAUTHORIZED = {"WWW-Authenticate": "Bearer"}


@dataclass(frozen=True)
class CallerContext:
    mode: Literal["bapi", "standalone"]
    delegation_token: str | None = field(default=None, repr=False)


def _bearer(headers: Mapping[str, str]) -> str | None:
    value = headers.get("authorization")
    # Only the exact scheme spelling counts; the b-api rejects lower-case "bearer" as well.
    if value and value.startswith(_BEARER) and value[len(_BEARER) :].strip():
        return value[len(_BEARER) :].strip()
    return None


def extract_bearer(headers: Mapping[str, str]) -> str | None:
    """Return the token from an exact `Authorization: Bearer <token>` header (case-insensitive header name)."""
    return _bearer({k.lower(): v for k, v in headers.items()})


def _delegation_token(headers: Mapping[str, str], settings: Settings) -> str | None:
    if settings.b_api_delegation_header:
        raw = headers.get(settings.b_api_delegation_header.lower())
        if raw and raw.startswith(DELEGATION_PREFIX):
            return raw.strip()
    token = _bearer(headers)
    return token if token and token.startswith(DELEGATION_PREFIX) else None


def _check_service_key(presented: str | None, settings: Settings) -> None:
    if not settings.service_api_keys:
        return
    valid = presented is not None and any(
        hmac.compare_digest(presented.encode(), key.encode()) for key in settings.service_api_keys
    )
    if not valid:
        raise ApiError(401, "UNAUTHORIZED", "Gültiger Bearer-Schlüssel erforderlich.", headers=_UNAUTHORIZED)


def resolve_caller(headers: Mapping[str, str], settings: Settings) -> CallerContext:
    """Apply the mode table from the design plan (E3)."""
    h = {k.lower(): v for k, v in headers.items()}
    if settings.service_mode != "standalone":
        token = _delegation_token(h, settings)
        if token:
            return CallerContext(mode="bapi", delegation_token=token)
        if settings.service_mode == "bapi":
            raise ApiError(401, "UNAUTHORIZED", "Aufruf nur über die b-api.", headers=_UNAUTHORIZED)
    _check_service_key(_bearer(h), settings)
    return CallerContext(mode="standalone")
