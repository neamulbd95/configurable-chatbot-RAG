"""Per-table incremental watermark persistence (FR-6.3). Stored in the
vector-store database (our own infra) rather than the source RDBMS, since
the pipeline never writes to the source system."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, MetaData, String, Table, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

_metadata = MetaData()

watermarks_table = Table(
    "ingestion_watermarks",
    _metadata,
    Column("table_name", String, primary_key=True),
    Column("watermark_value", String, nullable=True),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
)


def ensure_watermark_schema(engine: Engine) -> None:
    _metadata.create_all(engine, tables=[watermarks_table], checkfirst=True)


def get_watermark(engine: Engine, table_name: str) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(
            select(watermarks_table.c.watermark_value).where(
                watermarks_table.c.table_name == table_name
            )
        ).first()
    return row[0] if row else None


def set_watermark(engine: Engine, table_name: str, value: str) -> None:
    stmt = pg_insert(watermarks_table).values(table_name=table_name, watermark_value=value)
    stmt = stmt.on_conflict_do_update(
        index_elements=[watermarks_table.c.table_name],
        set_={"watermark_value": stmt.excluded.watermark_value},
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def delete_watermarks(engine: Engine, table_names: list[str] | None = None) -> None:
    """Clears persisted watermarks for the given tables, or all tables if
    `table_names` is None/empty. Paired with a vector-store reset so a wiped
    table doesn't silently skip rows on the next incremental ingestion."""
    with engine.begin() as conn:
        stmt = watermarks_table.delete()
        if table_names:
            stmt = stmt.where(watermarks_table.c.table_name.in_(table_names))
        conn.execute(stmt)
