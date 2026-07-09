"""Embeds chunk texts via the configured EmbeddingProvider and validates
dimension consistency (FR-2.2, FR-2.3) before chunks reach the vector store."""

from __future__ import annotations

from ragchatbot.models import ChunkRecord
from ragchatbot.providers.base import EmbeddingProvider


class EmbeddingDimensionError(ValueError):
    pass


async def embed_chunks(
    chunks: list[ChunkRecord], provider: EmbeddingProvider
) -> list[ChunkRecord]:
    if not chunks:
        return []

    vectors = await provider.embed([c.chunk_text for c in chunks])
    if len(vectors) != len(chunks):
        raise EmbeddingDimensionError(
            f"Provider returned {len(vectors)} embeddings for {len(chunks)} chunks"
        )

    expected_dim = len(vectors[0])
    embedded: list[ChunkRecord] = []
    for chunk, vector in zip(chunks, vectors):
        if len(vector) != expected_dim:
            raise EmbeddingDimensionError(
                f"Chunk {chunk.chunk_id} embedding dimension {len(vector)} "
                f"does not match batch-expected dimension {expected_dim}"
            )
        embedded.append(chunk.model_copy(update={"embedding": vector}))
    return embedded
