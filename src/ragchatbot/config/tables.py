"""Source table configuration (FR-1.2): a list of tables to ingest, each with
its own primary key, excluded columns, optional incremental watermark,
relation joins (FR-6.2), a normalization template (FR-6.4), and access tags
for RBAC filtering at retrieval time (FR-6.10)."""

from __future__ import annotations

from pathlib import Path
from string import Formatter

import yaml
from pydantic import BaseModel, Field, field_validator


class RelationConfig(BaseModel):
    """A one-to-many relation joined into the parent record during
    extraction (FR-6.2): rows from `table` where `foreign_key` equals the
    parent row's `local_key` are folded into the parent's normalized text."""

    table: str
    local_key: str
    foreign_key: str
    # Postgres/SQL Server/Oracle schema the related table lives in, if not
    # the connection's default (e.g. "public"). MySQL treats this as a
    # database name — same SQLAlchemy `schema=` kwarg either way.
    schema_name: str | None = Field(default=None, alias="schema")
    max_related_rows: int = 20
    exclude_columns: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class TableConfig(BaseModel):
    name: str
    primary_key: str
    # Schema the table lives in, if not the connection's default. Kept
    # separate from `name` (rather than asking users to write "schema.table")
    # because reflection needs schema and table name as distinct arguments.
    schema_name: str | None = Field(default=None, alias="schema")
    exclude_columns: list[str] = Field(default_factory=list)
    watermark_column: str | None = None
    batch_size: int = 500
    relations: list[RelationConfig] = Field(default_factory=list)
    normalization_template: str | None = None
    access_tags: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    @property
    def qualified_name(self) -> str:
        """Schema-qualified identity used everywhere a table needs a unique
        string identity: record_id, chunk citations, watermark keys, admin
        API table filters. Without this, two same-named tables in different
        schemas (e.g. sales.products and archive.products) would collide —
        their chunks would overwrite each other in the vector store, since
        chunk_id derives from record_id which derived from the bare table
        name alone."""
        return f"{self.schema_name}.{self.name}" if self.schema_name else self.name

    @field_validator("normalization_template")
    @classmethod
    def _validate_template_syntax(cls, value: str | None) -> str | None:
        """Config-load-time syntax check (FR-6.5). Column *existence* can't
        be checked here — the source schema isn't known until ingestion runs
        — so that's validated per-row at ingestion time instead, failing
        fast with a clear error (see ingestion/normalizer.py)."""
        if value is None:
            return value
        try:
            field_names = [name for _, name, _, _ in Formatter().parse(value) if name is not None]
        except ValueError as exc:
            raise ValueError(f"Invalid normalization_template syntax: {exc}") from exc
        if any(name == "" for name in field_names):
            raise ValueError(
                "normalization_template must use named placeholders like "
                "'{column_name}', not positional '{}'"
            )
        return value


def load_table_configs(path: str | Path) -> list[TableConfig]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Table config file not found: {config_path}. "
            "Copy config/tables.example.yaml to config/tables.yaml and adjust it."
        )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    tables = raw.get("tables", [])
    if not tables:
        raise ValueError(f"No tables defined under 'tables:' in {config_path}")

    return [TableConfig.model_validate(entry) for entry in tables]
