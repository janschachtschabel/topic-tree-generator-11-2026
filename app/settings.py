"""Service configuration. Every setting comes from the environment (or `.env`) and has a default."""

import re
from functools import lru_cache
from typing import Annotated, Literal, Self

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_ROUTER_PATH = "/api/v1/llm/router"
_HOSTNAME = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
)

_LLM_PATH = re.compile(r"^/(?:[A-Za-z0-9_-]+/)+$")

CommaList = Annotated[list[str], NoDecode]


class Settings(BaseSettings):
    """Runtime settings. See the configuration table in the design plan for the meaning of each value."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    service_id: str = "topic-tree"
    service_mode: Literal["auto", "bapi", "standalone"] = "auto"
    service_api_keys: CommaList = Field(default_factory=list)
    domain: str | None = None

    b_api_base_url: str = "https://b-api.staging.openeduhub.net"
    b_api_route: str = Field(
        "topic-tree-generator",
        validation_alias=AliasChoices("b_api_route", "B_API_ROUTE", "LLM_MODEL", "llm_model"),
    )
    # Alternative to the route: one model (e.g. gpt-6-luna) at the b-api endpoint for single models. When set, v2
    # uses it instead of the router; the frozen legacy endpoints always use the router.
    b_api_model: str | None = None
    b_api_model_path: str | None = None
    b_api_delegation_header: str | None = None
    b_api_dev_key: SecretStr | None = None

    openai_base_url: str | None = None
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-6-luna"

    llm_param_family: Literal["common", "gpt5", "classic"] = "common"
    llm_reasoning_effort: Literal["none", "minimal", "low"] = "none"
    llm_output_mode: Literal["json_schema", "json_object", "prompt"] = "json_schema"
    llm_send_prompt_cache_key: Literal["auto", "true", "false"] = "auto"
    llm_timeout_seconds: float = Field(120, gt=0)
    llm_max_retries: int = Field(3, ge=0)
    llm_max_concurrency: int = Field(20, ge=1)

    # Hard operator cost-control caps enforced on every v2 request (cannot be exceeded by callers).
    max_tree_depth: int = Field(3, ge=1, le=4)
    max_nodes_per_level: int = Field(20, ge=2, le=20)

    # Retry count used by the frozen legacy endpoints (env name kept for backward compatibility).
    legacy_max_retries: int = Field(4, ge=0, validation_alias=AliasChoices("legacy_max_retries", "MAX_RETRIES"))

    request_timeout_seconds: float = Field(280, gt=0)
    web_concurrency: int = Field(2, ge=1)
    # Ports inside the container; Docker Compose publishes the same numbers on the host, so an alternative port for
    # several services on one host is a single change in `.env`.
    public_port: int = Field(8000, ge=1, le=65535)
    internal_port: int = Field(9000, ge=1, le=65535)

    ref_allowed_hosts: CommaList = Field(default_factory=list)
    ref_max_bytes: int = Field(10 * 1024 * 1024, gt=0)
    ref_timeout_seconds: float = Field(20, gt=0)
    items_inline_max: int = Field(500, ge=1)

    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"
    ui_enabled: bool = True

    @field_validator(
        "b_api_delegation_header",
        "b_api_dev_key",
        "b_api_model",
        "b_api_model_path",
        "openai_base_url",
        "openai_api_key",
        "domain",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("domain")
    @classmethod
    def _validate_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        host = value.strip()
        if len(host) > 253 or not _HOSTNAME.match(host):
            raise ValueError(
                f"DOMAIN must be a bare hostname without scheme, path, or port (e.g. 'trees.example.de'), got {value!r}"
            )
        return host

    @field_validator("service_api_keys", "ref_allowed_hosts", mode="before")
    @classmethod
    def _split_comma_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("b_api_base_url")
    @classmethod
    def _strip_router_path(cls, value: str) -> str:
        # Older deployments configured the full router URL; accept both forms.
        value = value.rstrip("/")
        value = value.removesuffix(_ROUTER_PATH)
        return value

    @model_validator(mode="after")
    def _distinct_ports(self) -> Self:
        if self.public_port == self.internal_port:
            raise ValueError(f"PUBLIC_PORT and INTERNAL_PORT must differ (both are {self.public_port})")
        return self

    @model_validator(mode="after")
    def _model_needs_path(self) -> Self:
        if self.b_api_model and not self.b_api_model_path:
            raise ValueError(
                "B_API_MODEL is set but B_API_MODEL_PATH (the b-api endpoint for single models) is missing"
            )
        return self

    @field_validator("b_api_model_path")
    @classmethod
    def _normalize_model_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        path = "/" + value.strip().strip("/") + "/"
        if not _LLM_PATH.match(path):
            raise ValueError(f"B_API_MODEL_PATH must be a plain path such as /api/v1/llm/<endpoint>/, got {value!r}")
        return path

    @property
    def b_api_router_url(self) -> str:
        """Router URL of the frozen legacy endpoints (always the router)."""
        return f"{self.b_api_base_url}{_ROUTER_PATH}/"

    @property
    def b_api_model_url(self) -> str | None:
        """b-api endpoint for a single model (B_API_MODEL_PATH), or None when only routes are used."""
        return f"{self.b_api_base_url}{self.b_api_model_path}" if self.b_api_model_path else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
