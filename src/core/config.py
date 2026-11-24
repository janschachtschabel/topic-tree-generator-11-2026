"""Application configuration via environment variables."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    log_level: str = Field("INFO")

    # B-API / LLM Configuration
    b_api_base_url: str = Field(
        "https://b-api.staging.openeduhub.net/api/v1/llm/router/",
    )
    llm_model: str = Field("topic-tree-generator")
    max_retries: int = Field(4, ge=0)

    # Vocabulary URLs (edu-sharing SKOS vocabs)
    edu_context_vocab_url: str = Field(
        "https://vocabs.openeduhub.de/w3id.org/openeduhub/vocabs/educationalContext/index.json",
    )
    discipline_vocab_url: str = Field(
        "https://vocabs.openeduhub.de/w3id.org/openeduhub/vocabs/discipline/index.json",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
