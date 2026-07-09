"""Sentence-aware chunking with configurable size/overlap (FR-2.1)."""

from __future__ import annotations

import re

from ragchatbot.models import ChunkRecord, NormalizedRecord

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_SCALAR_TYPES = (str, int, float, bool)


def split_sentences(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(stripped) if s.strip()]


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Greedily packs sentences up to `chunk_size` characters per chunk,
    carrying the trailing `chunk_overlap` characters into the next chunk.
    A single sentence longer than `chunk_size` is kept whole rather than
    split mid-sentence."""
    sentences = split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > chunk_size and current:
            chunks.append(current)
            overlap_tail = current[-chunk_overlap:] if chunk_overlap > 0 else ""
            current = f"{overlap_tail} {sentence}".strip()
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def chunk_normalized_record(
    record: NormalizedRecord,
    chunk_size: int,
    chunk_overlap: int,
    access_tags: list[str] | None = None,
) -> list[ChunkRecord]:
    texts = chunk_text(record.normalized_text, chunk_size, chunk_overlap)
    scalar_attributes = {
        key: value
        for key, value in record.attributes.items()
        if value is None or isinstance(value, _SCALAR_TYPES)
    }

    chunks = []
    for index, text in enumerate(texts):
        chunks.append(
            ChunkRecord(
                chunk_id=f"{record.record_id}::{index}",
                record_id=record.record_id,
                chunk_text=text,
                chunk_index=index,
                metadata={
                    "source_table": record.lineage.source_table,
                    "primary_key": record.lineage.primary_key,
                    "extracted_at": record.lineage.extracted_at.isoformat(),
                    # access_tags drives RBAC filtering at retrieval time
                    # (FR-6.9-6.10); kept separate from scalar_attributes
                    # since it's structural metadata, not a business column.
                    "access_tags": access_tags or [],
                    **scalar_attributes,
                },
            )
        )
    return chunks
