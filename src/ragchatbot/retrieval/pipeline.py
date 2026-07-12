"""Retrieval pipeline (FR-3.1-3.4): embed the query, run similarity or
hybrid search, apply RBAC filtering and optional reranking, and package
results (with a confidence score, FR-6.8) for the chat service."""

from __future__ import annotations

from sqlalchemy import Table
from sqlalchemy.engine import Engine

from ragchatbot.db.vector_store import hybrid_search, similarity_search
from ragchatbot.models import RetrievedChunk
from ragchatbot.providers.base import EmbeddingProvider, EmbeddingProviderError
from ragchatbot.retrieval.reranker import Reranker


class ContextPackage:
    """Standard schema handed to the chat service (FR-3.4)."""

    def __init__(self, query: str, results: list[RetrievedChunk]):
        self.query = query
        self.results = results

    @property
    def is_grounded(self) -> bool:
        return len(self.results) > 0

    @property
    def confidence(self) -> float:
        """Answer confidence score (FR-6.8): the top result's similarity,
        or 0.0 when nothing was retrieved."""
        return self.results[0].similarity if self.results else 0.0

    def as_context_text(self) -> str:
        return "\n\n".join(f"[{i}] {r.chunk.chunk_text}" for i, r in enumerate(self.results, 1))

    def citations(self) -> list[dict[str, object]]:
        return [r.citation for r in self.results]


async def retrieve(
    query: str,
    embedding_provider: EmbeddingProvider,
    vector_engine: Engine,
    vector_table: Table,
    top_k: int,
    similarity_threshold: float,
    keyword_weight: float = 0.0,
    caller_roles: list[str] | None = None,
    reranker: Reranker | None = None,
) -> ContextPackage:
    try:
        [query_embedding] = await embedding_provider.embed([query])
    except EmbeddingProviderError:
        raise
    except Exception as exc:
        raise EmbeddingProviderError(f"Embedding provider call failed: {exc}") from exc

    if keyword_weight > 0:
        results = hybrid_search(
            vector_engine,
            vector_table,
            query,
            query_embedding,
            top_k,
            similarity_threshold,
            keyword_weight,
            caller_roles=caller_roles,
        )
    else:
        results = similarity_search(
            vector_engine,
            vector_table,
            query_embedding,
            top_k,
            similarity_threshold,
            caller_roles=caller_roles,
        )

    if reranker is not None:
        results = await reranker.rerank(query, results)

    return ContextPackage(query=query, results=results)
