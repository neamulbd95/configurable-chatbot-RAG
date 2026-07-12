"""Central runtime configuration. Every value that differs between a local
Ollama/PostgreSQL setup and a cloud Azure OpenAI/other-RDBMS deployment lives
here, sourced from env vars — never hardcoded in pipeline code (NFR-1.6, FR-5.3)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# SQLAlchemy driver per supported RDBMS engine (FR-1.1, FR-1.6). Adding a new
# engine is a one-line addition here plus the matching extras group in
# pyproject.toml — no changes to extraction/normalization code.
RDBMS_DRIVERS: dict[str, str] = {
    "postgresql": "postgresql+psycopg",
    "mysql": "mysql+pymysql",
    "mssql": "mssql+pyodbc",
    "oracle": "oracle+oracledb",
}

# Each DBAPI names its connect-timeout kwarg differently — without this, a
# genuinely unreachable host relies on the OS's TCP connect timeout, which
# can be 20s+ (or hang indefinitely on a filtered/blackholed port) rather
# than failing fast. Used by db/source_adapter.py::build_engine.
RDBMS_CONNECT_TIMEOUT_KWARG: dict[str, str] = {
    "postgresql": "connect_timeout",
    "mysql": "connect_timeout",
    "mssql": "timeout",
    "oracle": "tcp_connect_timeout",
}

RDBMSEngine = Literal["postgresql", "mysql", "mssql", "oracle"]
ProviderName = Literal["ollama", "azure_openai"]


def _normalize_literal(value: object) -> object:
    """Env vars are easy to typo with hyphens/case that don't match the
    Literal exactly (e.g. "azure-openai" instead of "azure_openai"). Rather
    than fail with a cryptic pydantic error, normalize before validating."""
    if isinstance(value, str):
        return value.strip().lower().replace("-", "_")
    return value


class DatabaseSettings(BaseSettings):
    """Connection settings shared by the source RDBMS and the vector store.
    Two independent instances of this are used so the vector store is never
    assumed to be co-located with the source database (FR-1.7)."""

    engine: RDBMSEngine = "postgresql"
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: SecretStr = SecretStr("postgres")
    database: str = "postgres"
    driver_override: str | None = None

    _normalize_engine = field_validator("engine", mode="before")(_normalize_literal)

    def sqlalchemy_url(self) -> str:
        driver = self.driver_override or RDBMS_DRIVERS[self.engine]
        return (
            f"{driver}://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.database}"
        )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        env_prefix="",
        extra="ignore",
    )

    # -- App / API --
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # -- Admin API (vector store reset, ingestion trigger/status) --
    # If unset, /admin/* endpoints are unauthenticated — fine for local dev,
    # not for anything reachable outside your own machine.
    admin_api_key: str | None = None

    # -- Source RDBMS (FR-1.1, FR-1.6) --
    source_db_engine: RDBMSEngine = "postgresql"
    source_db_host: str = "localhost"
    source_db_port: int = 5432
    source_db_user: str = "postgres"
    source_db_password: SecretStr = SecretStr("postgres")
    source_db_name: str = "app"
    source_db_driver_override: str | None = None
    # Bounds how long a connection attempt (e.g. /admin/source-db/status,
    # or any ingestion run) waits before giving up on an unreachable host —
    # without this, the OS's own TCP timeout applies, which can be 20s+ or
    # effectively indefinite against a filtered/blackholed port.
    source_db_connect_timeout_seconds: int = 10
    # Default schema for tables that don't set their own `schema:` in
    # tables.yaml. Deliberately an env var, not a tables.yaml field-only
    # concept: which schema holds your tables is a per-environment fact
    # (varies machine to machine, dev vs. prod), not something that should
    # be hardcoded in a config file that's typically shared/committed.
    # Per-table `schema:` in tables.yaml still overrides this when set.
    source_db_schema: str | None = None

    # -- Vector store (FR-1.7): independently configured, defaults to a
    # dedicated pgvector-enabled PostgreSQL instance regardless of what the
    # source RDBMS engine is. --
    vector_db_host: str = "localhost"
    vector_db_port: int = 5433
    vector_db_user: str = "postgres"
    vector_db_password: SecretStr = SecretStr("postgres")
    vector_db_name: str = "vectorstore"
    vector_table_name: str = "chunks"

    # -- Table config (FR-1.2) --
    tables_config_path: str = "config/tables.yaml"

    # -- Chunking (FR-2.1) --
    chunk_size: int = 800
    chunk_overlap: int = 120

    # -- Retrieval (FR-3.1, FR-3.2) --
    retrieval_top_k: int = 5
    retrieval_similarity_threshold: float = 0.65

    # -- Hybrid retrieval & reranking (FR-6.6-6.8) --
    # keyword_weight=0 disables hybrid scoring entirely (pure vector search,
    # the Phase 1 default behavior).
    retrieval_keyword_weight: float = 0.0
    rerank_enabled: bool = False
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # -- Conversational context (FR-6.11-6.13) --
    history_max_messages: int = 6
    history_max_chars: int = 4000

    # -- Providers (FR-5.1-5.3): runtime-selectable, no code change to switch --
    embedding_provider: ProviderName = "ollama"
    embedding_model: str = "nomic-embed-text"
    chat_provider: ProviderName = "ollama"
    chat_model: str = "qwen3:8b"

    ollama_base_url: str = "http://localhost:11434"

    azure_openai_endpoint: str | None = None
    azure_openai_api_key: SecretStr | None = None
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_chat_deployment: str | None = None
    azure_openai_embedding_deployment: str | None = None

    _normalize_source_db_engine = field_validator("source_db_engine", mode="before")(
        _normalize_literal
    )
    _normalize_embedding_provider = field_validator("embedding_provider", mode="before")(
        _normalize_literal
    )
    _normalize_chat_provider = field_validator("chat_provider", mode="before")(_normalize_literal)

    def source_db(self) -> DatabaseSettings:
        return DatabaseSettings(
            engine=self.source_db_engine,
            host=self.source_db_host,
            port=self.source_db_port,
            user=self.source_db_user,
            password=self.source_db_password,
            database=self.source_db_name,
            driver_override=self.source_db_driver_override,
        )

    def vector_db(self) -> DatabaseSettings:
        return DatabaseSettings(
            engine="postgresql",
            host=self.vector_db_host,
            port=self.vector_db_port,
            user=self.vector_db_user,
            password=self.vector_db_password,
            database=self.vector_db_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
