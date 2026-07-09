import pytest

from ragchatbot.config.settings import Settings
from ragchatbot.providers.factory import build_chat_provider, build_embedding_provider
from ragchatbot.providers.ollama_provider import OllamaChatProvider, OllamaEmbeddingProvider


def test_build_ollama_providers_by_default():
    settings = Settings()

    embedding = build_embedding_provider(settings)
    chat = build_chat_provider(settings)

    assert isinstance(embedding, OllamaEmbeddingProvider)
    assert isinstance(chat, OllamaChatProvider)


def test_azure_provider_requires_endpoint_and_key():
    settings = Settings(embedding_provider="azure_openai")

    with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
        build_embedding_provider(settings)


def test_unknown_provider_raises():
    settings = Settings()
    settings.chat_provider = "bogus"  # bypass Literal validation to test the guard clause

    with pytest.raises(ValueError, match="Unknown chat provider"):
        build_chat_provider(settings)
