import pytest

from ragchatbot.ingestion.embedder import EmbeddingDimensionError, EmbeddingProviderError, embed_chunks
from ragchatbot.models import ChunkRecord
from ragchatbot.providers.base import EmbeddingProvider


class StaticEmbeddingProvider(EmbeddingProvider):
    def __init__(self, vectors: list[list[float]]):
        self._vectors = vectors

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return self._vectors

    @property
    def dimension(self) -> int:
        return len(self._vectors[0]) if self._vectors else 0


class FailingEmbeddingProvider(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Error code: 403 - {'error': {'code': '403', 'message': 'blocked'}}")

    @property
    def dimension(self) -> int:
        raise RuntimeError("never reached")


def _chunk(chunk_id: str) -> ChunkRecord:
    return ChunkRecord(chunk_id=chunk_id, record_id="r:1", chunk_text="text", chunk_index=0)


@pytest.mark.asyncio
async def test_embed_chunks_empty_list_returns_empty_without_calling_provider():
    assert await embed_chunks([], StaticEmbeddingProvider([])) == []


@pytest.mark.asyncio
async def test_embed_chunks_attaches_vectors_in_order():
    chunks = [_chunk("a"), _chunk("b")]
    provider = StaticEmbeddingProvider([[1.0, 2.0], [3.0, 4.0]])

    result = await embed_chunks(chunks, provider)

    assert result[0].embedding == [1.0, 2.0]
    assert result[1].embedding == [3.0, 4.0]


@pytest.mark.asyncio
async def test_embed_chunks_rejects_mismatched_batch_size():
    provider = StaticEmbeddingProvider([[1.0, 2.0]])  # only 1 vector for 2 chunks

    with pytest.raises(EmbeddingDimensionError, match="1 embeddings for 2 chunks"):
        await embed_chunks([_chunk("a"), _chunk("b")], provider)


@pytest.mark.asyncio
async def test_embed_chunks_wraps_provider_failure_with_identifying_prefix():
    with pytest.raises(EmbeddingProviderError, match="Embedding provider call failed"):
        await embed_chunks([_chunk("a")], FailingEmbeddingProvider())
