import pytest

from ragchatbot.models import ChunkRecord, RetrievedChunk
from ragchatbot.retrieval.reranker import CrossEncoderReranker, NoopReranker, build_reranker


def _chunk(chunk_id: str, similarity: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=ChunkRecord(chunk_id=chunk_id, record_id="r:1", chunk_text="text", chunk_index=0),
        similarity=similarity,
    )


@pytest.mark.asyncio
async def test_noop_reranker_returns_input_unchanged():
    results = [_chunk("a", 0.9), _chunk("b", 0.8)]

    reranked = await NoopReranker().rerank("query", results)

    assert reranked == results


def test_build_reranker_defaults_to_noop_when_disabled():
    reranker = build_reranker(enabled=False, model_name="unused")
    assert isinstance(reranker, NoopReranker)


def test_cross_encoder_reranker_without_dependency_raises_clear_error():
    with pytest.raises(RuntimeError, match="rerank' extra"):
        CrossEncoderReranker(model_name="cross-encoder/ms-marco-MiniLM-L-6-v2")
