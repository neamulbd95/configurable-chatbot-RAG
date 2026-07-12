import pytest

from ragchatbot.providers.base import EmbeddingProvider, EmbeddingProviderError
from ragchatbot.retrieval.pipeline import retrieve


class FailingEmbeddingProvider(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Error code: 403 - {'error': {'code': '403', 'message': 'blocked'}}")

    @property
    def dimension(self) -> int:
        raise RuntimeError("never reached")


@pytest.mark.asyncio
async def test_retrieve_wraps_embedding_provider_failure():
    # vector_engine/vector_table are never touched — the query embedding
    # call fails first, so this doesn't need a live vector store.
    with pytest.raises(EmbeddingProviderError, match="Embedding provider call failed"):
        await retrieve(
            query="anything",
            embedding_provider=FailingEmbeddingProvider(),
            vector_engine=None,  # type: ignore[arg-type]
            vector_table=None,  # type: ignore[arg-type]
            top_k=5,
            similarity_threshold=0.65,
        )
