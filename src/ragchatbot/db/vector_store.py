"""Vector store access — always PostgreSQL+pgvector, always configured
independently of the source RDBMS (FR-1.7). This is the one component in the
pipeline that is intentionally not RDBMS-agnostic: pgvector is the reference
implementation, and swapping it for Qdrant/Chroma/etc. only requires a new
module behind the same functions, not changes to the rest of the pipeline.

Also implements hybrid vector+keyword search (FR-6.6) and role-based access
filtering (FR-6.9-6.10)."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    inspect,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, insert as pg_insert
from sqlalchemy.engine import Engine
from pgvector.sqlalchemy import Vector

from ragchatbot.config.settings import DatabaseSettings
from ragchatbot.models import ChunkRecord, RetrievedChunk


class DimensionMismatchError(ValueError):
    """Raised when a chunk's embedding length doesn't match the vector
    column's configured dimension (FR-2.3)."""


def build_vector_engine(db_settings: DatabaseSettings) -> Engine:
    return create_engine(db_settings.sqlalchemy_url(), pool_pre_ping=True, future=True)


def get_chunks_table(table_name: str, dimension: int) -> Table:
    metadata = MetaData()
    return Table(
        table_name,
        metadata,
        Column("chunk_id", String, primary_key=True),
        Column("record_id", String, nullable=False, index=True),
        Column("chunk_text", String, nullable=False),
        Column("chunk_index", Integer, nullable=False),
        Column("embedding", Vector(dimension), nullable=False),
        Column("metadata", JSONB, nullable=False),
    )


def ensure_schema(engine: Engine, table_name: str, dimension: int) -> Table:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    table = get_chunks_table(table_name, dimension)
    table.metadata.create_all(engine, checkfirst=True)
    return table


def reflect_existing_chunks_table(engine: Engine, table_name: str) -> Table | None:
    """Loads the chunks table by reflection rather than by declaring its
    Vector(dim) type — used by admin operations (like reset) that only need
    to delete rows and shouldn't have to know the embedding dimension or
    trigger a provider call just to find out. Returns None if the table
    hasn't been created yet (nothing ingested)."""
    if not inspect(engine).has_table(table_name):
        return None
    metadata = MetaData()
    return Table(table_name, metadata, autoload_with=engine)


def delete_chunks(engine: Engine, table: Table, source_tables: list[str] | None = None) -> int:
    """Deletes chunks for the given source tables, or every chunk if
    `source_tables` is None/empty. Used by the vector-store reset API."""
    with engine.begin() as conn:
        stmt = table.delete()
        if source_tables:
            stmt = stmt.where(table.c.metadata["source_table"].astext.in_(source_tables))
        result = conn.execute(stmt)
    return result.rowcount


def upsert_chunks(engine: Engine, table: Table, chunks: list[ChunkRecord]) -> None:
    """Persist chunk + embedding + metadata (FR-2.4), rejecting any chunk
    whose embedding dimension doesn't match the table's vector column."""
    expected_dim = table.c.embedding.type.dim
    rows = []
    for chunk in chunks:
        if chunk.embedding is None:
            raise ValueError(f"Chunk {chunk.chunk_id} has no embedding to store")
        if len(chunk.embedding) != expected_dim:
            raise DimensionMismatchError(
                f"Chunk {chunk.chunk_id} embedding has dimension "
                f"{len(chunk.embedding)}, expected {expected_dim}"
            )
        rows.append(
            {
                "chunk_id": chunk.chunk_id,
                "record_id": chunk.record_id,
                "chunk_text": chunk.chunk_text,
                "chunk_index": chunk.chunk_index,
                "embedding": chunk.embedding,
                "metadata": chunk.metadata,
            }
        )

    if not rows:
        return

    stmt = pg_insert(table).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[table.c.chunk_id],
        set_={
            "chunk_text": stmt.excluded.chunk_text,
            "chunk_index": stmt.excluded.chunk_index,
            "embedding": stmt.excluded.embedding,
            "metadata": stmt.excluded.metadata,
        },
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def passes_access_filter(metadata: dict[str, object], caller_roles: list[str] | None) -> bool:
    """RBAC filter (FR-6.9-6.10): a chunk with no access_tags is public and
    visible to everyone. A chunk with access_tags is default-denied unless
    the caller has at least one matching role."""
    access_tags = metadata.get("access_tags") or []
    if not access_tags:
        return True
    if not caller_roles:
        return False
    return bool(set(access_tags) & set(caller_roles))


def _row_to_retrieved_chunk(row: dict[str, object], similarity: float) -> RetrievedChunk:
    chunk = ChunkRecord(
        chunk_id=row["chunk_id"],
        record_id=row["record_id"],
        chunk_text=row["chunk_text"],
        chunk_index=row["chunk_index"],
        embedding=None,
        metadata=row["metadata"],
    )
    return RetrievedChunk(chunk=chunk, similarity=similarity)


def similarity_search(
    engine: Engine,
    table: Table,
    query_embedding: list[float],
    top_k: int,
    similarity_threshold: float,
    caller_roles: list[str] | None = None,
    candidate_multiplier: int = 4,
) -> list[RetrievedChunk]:
    """Cosine similarity search (FR-3.1, FR-3.2). pgvector's cosine_distance
    returns distance in [0, 2]; similarity = 1 - distance. Fetches a wider
    candidate pool than top_k so RBAC filtering (FR-6.9) doesn't starve the
    result set."""
    distance = table.c.embedding.cosine_distance(query_embedding)
    pool_size = max(top_k * candidate_multiplier, top_k)
    stmt = select(table, distance.label("distance")).order_by(distance).limit(pool_size)

    with engine.connect() as conn:
        rows = conn.execute(stmt).mappings().all()

    results: list[RetrievedChunk] = []
    for row in rows:
        similarity = 1.0 - float(row["distance"])
        if similarity < similarity_threshold:
            continue
        if not passes_access_filter(row["metadata"], caller_roles):
            continue
        results.append(_row_to_retrieved_chunk(dict(row), similarity))
        if len(results) >= top_k:
            break
    return results


def hybrid_search(
    engine: Engine,
    table: Table,
    query_text: str,
    query_embedding: list[float],
    top_k: int,
    similarity_threshold: float,
    keyword_weight: float,
    caller_roles: list[str] | None = None,
    candidate_multiplier: int = 4,
) -> list[RetrievedChunk]:
    """Vector + keyword (BM25-style, via Postgres full-text ranking) hybrid
    retrieval (FR-6.6). `keyword_weight` in [0, 1] controls the blend; the
    similarity_threshold safety gate still applies to the vector score
    alone, so hybrid ranking never lets a purely keyword-matched but
    semantically unrelated chunk through ungrounded."""
    distance = table.c.embedding.cosine_distance(query_embedding)
    keyword_rank = func.ts_rank_cd(
        func.to_tsvector("english", table.c.chunk_text),
        func.plainto_tsquery("english", query_text),
    )
    pool_size = max(top_k * candidate_multiplier, top_k)
    stmt = (
        select(table, distance.label("distance"), keyword_rank.label("keyword_rank"))
        .order_by(distance)
        .limit(pool_size)
    )

    with engine.connect() as conn:
        rows = conn.execute(stmt).mappings().all()

    candidates = []
    max_keyword_rank = 0.0
    for row in rows:
        similarity = 1.0 - float(row["distance"])
        if similarity < similarity_threshold:
            continue
        if not passes_access_filter(row["metadata"], caller_roles):
            continue
        keyword_score = float(row["keyword_rank"])
        max_keyword_rank = max(max_keyword_rank, keyword_score)
        candidates.append((row, similarity, keyword_score))

    scored: list[tuple[float, dict[str, object], float]] = []
    for row, similarity, keyword_score in candidates:
        normalized_keyword = keyword_score / max_keyword_rank if max_keyword_rank else 0.0
        combined = (1 - keyword_weight) * similarity + keyword_weight * normalized_keyword
        scored.append((combined, dict(row), similarity))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [_row_to_retrieved_chunk(row, similarity) for _, row, similarity in scored[:top_k]]
