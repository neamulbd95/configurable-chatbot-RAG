"""End-to-end ingestion: extract -> normalize -> chunk -> embed -> store.
One run processes every table listed in config/tables.yaml (FR-1.2),
resuming from each table's persisted watermark (FR-1.5, FR-6.3)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import Table
from sqlalchemy.engine import Engine

from ragchatbot.config.settings import Settings
from ragchatbot.config.tables import TableConfig, load_table_configs
from ragchatbot.db.source_adapter import build_engine
from ragchatbot.db.vector_store import build_vector_engine, ensure_schema, upsert_chunks
from ragchatbot.db.watermark_store import ensure_watermark_schema, get_watermark, set_watermark
from ragchatbot.ingestion.chunker import chunk_normalized_record
from ragchatbot.ingestion.embedder import embed_chunks
from ragchatbot.ingestion.extractor import extract_table
from ragchatbot.ingestion.normalizer import normalize_record
from ragchatbot.models import ChunkRecord
from ragchatbot.providers.base import EmbeddingProvider
from ragchatbot.providers.factory import build_embedding_provider

logger = logging.getLogger(__name__)


def _parse_watermark(value: str | None) -> object | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return value


async def _flush(
    chunks: list[ChunkRecord],
    embedding_provider: EmbeddingProvider,
    vector_engine: Engine,
    table_name: str,
    vector_table: Table | None,
) -> Table:
    embedded = await embed_chunks(chunks, embedding_provider)
    if vector_table is None:
        vector_table = ensure_schema(vector_engine, table_name, embedding_provider.dimension)
    upsert_chunks(vector_engine, vector_table, embedded)
    return vector_table


async def _ingest_table(
    source_engine: Engine,
    vector_engine: Engine,
    embedding_provider: EmbeddingProvider,
    table_config: TableConfig,
    vector_table_name: str,
    chunk_size: int,
    chunk_overlap: int,
    vector_table: Table | None,
) -> tuple[int, Table | None]:
    chunk_count = 0
    pending: list[ChunkRecord] = []
    max_watermark: datetime | None = None

    watermark_since = _parse_watermark(get_watermark(vector_engine, table_config.name))

    for source_record in extract_table(source_engine, table_config, watermark_since=watermark_since):
        if table_config.watermark_column and source_record.updated_at is not None:
            if max_watermark is None or source_record.updated_at > max_watermark:
                max_watermark = source_record.updated_at

        normalized = normalize_record(source_record, template=table_config.normalization_template)
        pending.extend(
            chunk_normalized_record(
                normalized, chunk_size, chunk_overlap, access_tags=table_config.access_tags
            )
        )

        if len(pending) >= table_config.batch_size:
            vector_table = await _flush(
                pending, embedding_provider, vector_engine, vector_table_name, vector_table
            )
            chunk_count += len(pending)
            pending = []

    if pending:
        vector_table = await _flush(
            pending, embedding_provider, vector_engine, vector_table_name, vector_table
        )
        chunk_count += len(pending)

    if max_watermark is not None:
        set_watermark(vector_engine, table_config.name, max_watermark.isoformat())

    return chunk_count, vector_table


async def run_ingestion_for_tables(
    source_engine: Engine,
    vector_engine: Engine,
    embedding_provider: EmbeddingProvider,
    table_configs: list[TableConfig],
    vector_table_name: str,
    chunk_size: int,
    chunk_overlap: int,
) -> dict[str, int]:
    """Resource-based entry point: reuses already-built engines/provider
    (e.g. the ones the API already holds in `app.state`) instead of
    constructing new connection pools per call. Used by both the CLI
    (`run_ingestion` below) and the `/admin/ingest` API."""
    ensure_watermark_schema(vector_engine)

    stats: dict[str, int] = {}
    vector_table: Table | None = None

    for table_config in table_configs:
        chunk_count, vector_table = await _ingest_table(
            source_engine,
            vector_engine,
            embedding_provider,
            table_config,
            vector_table_name,
            chunk_size,
            chunk_overlap,
            vector_table,
        )
        stats[table_config.name] = chunk_count
        logger.info("Ingested %s chunks from table %s", chunk_count, table_config.name)

    return stats


async def run_ingestion(settings: Settings) -> dict[str, int]:
    table_configs = load_table_configs(settings.tables_config_path)
    source_engine = build_engine(settings.source_db())
    vector_engine = build_vector_engine(settings.vector_db())
    embedding_provider = build_embedding_provider(settings)

    return await run_ingestion_for_tables(
        source_engine,
        vector_engine,
        embedding_provider,
        table_configs,
        settings.vector_table_name,
        settings.chunk_size,
        settings.chunk_overlap,
    )


def main() -> None:
    """CLI entry point (`python -m ragchatbot.ingestion.pipeline`) — still
    useful for cron/one-off bootstrap runs. For operational/interactive use,
    prefer the `/admin/ingest` API, which is trackable and doesn't require
    shell access to the service host."""
    settings = Settings()
    logging.basicConfig(level=settings.log_level)
    stats = asyncio.run(run_ingestion(settings))
    logger.info("Ingestion complete: %s", stats)


if __name__ == "__main__":
    main()
