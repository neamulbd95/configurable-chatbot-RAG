"""Turns raw RDBMS rows into SourceRecord objects (FR-1.1, FR-1.4), folding
in related child-table rows when the table config declares relations
(FR-6.2)."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import Table, select
from sqlalchemy.engine import Engine

from ragchatbot.config.tables import RelationConfig, TableConfig
from ragchatbot.db.source_adapter import SourceDBError, SourceTableReader, reflect_table
from ragchatbot.models import SourceRecord


def _fetch_related_rows(
    engine: Engine, related_table: Table, relation: RelationConfig, local_value: object
) -> list[dict[str, object]]:
    fk_col = related_table.c[relation.foreign_key]
    stmt = select(related_table).where(fk_col == local_value).limit(relation.max_related_rows)
    try:
        with engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
    except Exception as exc:
        raise SourceDBError(f"Source DB relation read failed for '{related_table.name}': {exc}") from exc
    return [
        {k: v for k, v in dict(row).items() if k not in relation.exclude_columns} for row in rows
    ]


def extract_table(
    engine: Engine,
    table_config: TableConfig,
    watermark_since: object | None = None,
) -> Iterator[SourceRecord]:
    reader = SourceTableReader(
        engine,
        table_config.name,
        batch_size=table_config.batch_size,
        schema=table_config.schema_name,
    )

    # Reflect each related table once per extraction run, not once per row —
    # reflection is a schema round trip and rows can number in the thousands.
    # Keyed by (schema, table) so two relations with the same table name in
    # different schemas don't collide.
    relation_tables: dict[tuple[str | None, str], Table] = {}
    for relation in table_config.relations:
        key = (relation.schema_name, relation.table)
        relation_tables[key] = reflect_table(engine, relation.table, schema=relation.schema_name)

    for row in reader.iter_rows(
        watermark_column=table_config.watermark_column,
        watermark_since=watermark_since,
    ):
        pk_value = row[table_config.primary_key]
        updated_at = (
            row.get(table_config.watermark_column) if table_config.watermark_column else None
        )
        columns = {
            key: value for key, value in row.items() if key not in table_config.exclude_columns
        }

        for relation in table_config.relations:
            local_value = row[relation.local_key]
            related_table = relation_tables[(relation.schema_name, relation.table)]
            # The dict key stays the bare table name (not schema-qualified)
            # since it doubles as the normalization_template placeholder
            # name, and "{schema.table}" isn't valid str.format syntax.
            columns[relation.table] = _fetch_related_rows(
                engine, related_table, relation, local_value
            )

        yield SourceRecord(
            # Schema-qualified so two same-named tables in different schemas
            # don't collide on record_id / chunk_id (see TableConfig.qualified_name).
            source_table=table_config.qualified_name,
            primary_key_value=str(pk_value),
            columns=columns,
            updated_at=updated_at,
        )
