"""Reranking (FR-6.7): a pluggable interface so cross-encoder reranking is a
config toggle, not a hard dependency. `NoopReranker` is the default — it
keeps the vector/hybrid-search ordering as-is, at zero extra cost or install
weight. `CrossEncoderReranker` requires the optional `rerank` extra
(`pip install .[rerank]`) and is only imported when actually enabled."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

from ragchatbot.models import RetrievedChunk


class Reranker(ABC):
    @abstractmethod
    async def rerank(self, query: str, results: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Return `results` reordered (and optionally re-scored) by
        relevance to `query`."""


class NoopReranker(Reranker):
    async def rerank(self, query: str, results: list[RetrievedChunk]) -> list[RetrievedChunk]:
        return results


class CrossEncoderReranker(Reranker):
    def __init__(self, model_name: str):
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError(
                "CrossEncoderReranker requires the 'rerank' extra: "
                "pip install '.[rerank]'"
            ) from exc
        self._model = CrossEncoder(model_name)

    async def rerank(self, query: str, results: list[RetrievedChunk]) -> list[RetrievedChunk]:
        if not results:
            return results
        pairs = [(query, r.chunk.chunk_text) for r in results]
        scores = await asyncio.to_thread(self._model.predict, pairs)
        rescored = [
            RetrievedChunk(chunk=r.chunk, similarity=float(score))
            for r, score in zip(results, scores)
        ]
        rescored.sort(key=lambda r: r.similarity, reverse=True)
        return rescored


def build_reranker(enabled: bool, model_name: str) -> Reranker:
    if not enabled:
        return NoopReranker()
    return CrossEncoderReranker(model_name)
