"""Ollama-backed provider adapters — local development default (FR-5.1)."""

from __future__ import annotations

import httpx

from ragchatbot.providers.base import ChatMessage, ChatProvider, EmbeddingProvider


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        base_url: str,
        model: str,
        dimension: int | None = None,
        timeout: float = 60.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dimension = dimension
        self._timeout = timeout

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": texts},
            )
            resp.raise_for_status()
            data = resp.json()
        embeddings: list[list[float]] = data["embeddings"]
        if self._dimension is None and embeddings:
            self._dimension = len(embeddings[0])
        return embeddings

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            raise RuntimeError(
                "Embedding dimension unknown until embed() has run at least "
                "once, or pass `dimension` explicitly at construction."
            )
        return self._dimension


class OllamaChatProvider(ChatProvider):
    def __init__(self, base_url: str, model: str, timeout: float = 120.0):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    async def generate(self, messages: list[ChatMessage]) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/api/chat",
                json={"model": self._model, "messages": messages, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
        return data["message"]["content"]
