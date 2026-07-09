"""Azure OpenAI-backed provider adapters — cloud deployment default (FR-5.2)."""

from __future__ import annotations

from openai import AsyncAzureOpenAI

from ragchatbot.providers.base import ChatMessage, ChatProvider, EmbeddingProvider


class AzureOpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        api_version: str,
        deployment: str,
        dimension: int | None = None,
    ):
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint, api_key=api_key, api_version=api_version
        )
        self._deployment = deployment
        self._dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await self._client.embeddings.create(model=self._deployment, input=texts)
        embeddings = [item.embedding for item in resp.data]
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


class AzureOpenAIChatProvider(ChatProvider):
    def __init__(self, endpoint: str, api_key: str, api_version: str, deployment: str):
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint, api_key=api_key, api_version=api_version
        )
        self._deployment = deployment

    async def generate(self, messages: list[ChatMessage]) -> str:
        resp = await self._client.chat.completions.create(
            model=self._deployment,
            messages=[dict(message) for message in messages],
        )
        return resp.choices[0].message.content or ""
