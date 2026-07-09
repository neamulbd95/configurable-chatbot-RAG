"""Shared pipeline record types, mirroring PDR §5 Data Contracts. Each stage
(extraction → normalization → chunking → retrieval) consumes and/or produces
one of these, keeping the stages independently testable and swappable."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Lineage(BaseModel):
    source_table: str
    primary_key: str
    extracted_at: datetime


class SourceRecord(BaseModel):
    """One row extracted from a configured RDBMS table (FR-1.1, FR-1.4)."""

    source_table: str
    primary_key_value: str
    columns: dict[str, object]
    updated_at: datetime | None = None
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def record_id(self) -> str:
        return f"{self.source_table}:{self.primary_key_value}"


class NormalizedRecord(BaseModel):
    """Canonical text form of a SourceRecord (FR-1.3), ready for chunking."""

    record_id: str
    normalized_text: str
    attributes: dict[str, object]
    lineage: Lineage


class ChunkRecord(BaseModel):
    """A chunk of normalized text plus its embedding and retrieval metadata
    (FR-2.1-2.4). `embedding` is None until the embedding stage runs."""

    chunk_id: str
    record_id: str
    chunk_text: str
    chunk_index: int
    embedding: list[float] | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    """A ChunkRecord plus its similarity score, returned by the retrieval
    pipeline (FR-3.1-3.3)."""

    chunk: ChunkRecord
    similarity: float

    @property
    def citation(self) -> dict[str, object]:
        return {
            "source_table": self.chunk.metadata.get("source_table"),
            "primary_key": self.chunk.metadata.get("primary_key"),
            "chunk_id": self.chunk.chunk_id,
            "similarity": round(self.similarity, 4),
        }
