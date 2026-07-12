"""Dialect-agnostic access to the source RDBMS (FR-1.1, FR-1.6). All table
reads go through SQLAlchemy Core against a reflected Table, so pagination,
quoting, and type-mapping differences between engines are handled by each
engine's SQLAlchemy dialect rather than hand-written per-engine SQL. Adding a
new supported engine only requires a driver entry in config/settings.py."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import MetaData, Table, create_engine, select
from sqlalchemy.engine import Engine

from ragchatbot.config.settings import DatabaseSettings


def build_engine(db_settings: DatabaseSettings) -> Engine:
    return create_engine(db_settings.sqlalchemy_url(), pool_pre_ping=True, future=True)


def reflect_table(engine: Engine, table_name: str, schema: str | None = None) -> Table:
    metadata = MetaData()
    return Table(table_name, metadata, autoload_with=engine, schema=schema)


class SourceTableReader:
    """Paginated, watermark-aware reader for a single configured table.

    Uses LIMIT/OFFSET generated per-dialect by SQLAlchemy rather than
    keyset pagination — simple and portable across engines, at the cost of
    O(n) page-seek cost on very large tables (acceptable for the Phase 1
    baseline throughput target, NFR-1.3)."""

    def __init__(
        self, engine: Engine, table_name: str, batch_size: int = 500, schema: str | None = None
    ):
        self.engine = engine
        self.table = reflect_table(engine, table_name, schema=schema)
        self.batch_size = batch_size

    def iter_rows(
        self,
        watermark_column: str | None = None,
        watermark_since: object | None = None,
    ) -> Iterator[dict[str, object]]:
        """Yields rows as dicts. If a watermark column + value are given,
        only rows updated since that value are returned (FR-1.5)."""
        order_column = self.table.primary_key.columns.values()[0]
        offset = 0
        with self.engine.connect() as conn:
            while True:
                stmt = select(self.table).order_by(order_column).limit(self.batch_size).offset(offset)
                if watermark_column is not None and watermark_since is not None:
                    stmt = stmt.where(self.table.c[watermark_column] > watermark_since)

                rows = conn.execute(stmt).mappings().all()
                if not rows:
                    return
                for row in rows:
                    yield dict(row)
                if len(rows) < self.batch_size:
                    return
                offset += self.batch_size
