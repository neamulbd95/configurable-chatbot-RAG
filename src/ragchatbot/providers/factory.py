"""Runtime provider selection (FR-5.3) — the only place that branches on the
`embedding_provider` / `chat_provider` config values."""

from __future__ import annotations

from ragchatbot.config.settings import Settings
from ragchatbot.providers.azure_openai_provider import (
    AzureOpenAIChatProvider,
    AzureOpenAIEmbeddingProvider,
)
from ragchatbot.providers.base import ChatProvider, EmbeddingProvider
from ragchatbot.providers.ollama_provider import OllamaChatProvider, OllamaEmbeddingProvider


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(
            base_url=settings.ollama_base_url, model=settings.embedding_model
        )
    if settings.embedding_provider == "azure_openai":
        endpoint, api_key = _require_azure_settings(settings)
        return AzureOpenAIEmbeddingProvider(
            endpoint=endpoint,
            api_key=api_key,
            api_version=settings.azure_openai_api_version,
            deployment=settings.azure_openai_embedding_deployment or settings.embedding_model,
        )
    raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")


def build_chat_provider(settings: Settings) -> ChatProvider:
    if settings.chat_provider == "ollama":
        return OllamaChatProvider(base_url=settings.ollama_base_url, model=settings.chat_model)
    if settings.chat_provider == "azure_openai":
        endpoint, api_key = _require_azure_settings(settings)
        return AzureOpenAIChatProvider(
            endpoint=endpoint,
            api_key=api_key,
            api_version=settings.azure_openai_api_version,
            deployment=settings.azure_openai_chat_deployment or settings.chat_model,
        )
    raise ValueError(f"Unknown chat provider: {settings.chat_provider}")


def _require_azure_settings(settings: Settings) -> tuple[str, str]:
    if not settings.azure_openai_endpoint or not settings.azure_openai_api_key:
        raise ValueError(
            "AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set to use "
            "the azure_openai provider."
        )
    return settings.azure_openai_endpoint, settings.azure_openai_api_key.get_secret_value()
