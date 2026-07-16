from fastapi.testclient import TestClient

from ragchatbot.api.main import create_app
from ragchatbot.providers.base import ChatMessage, ChatProvider, EmbeddingProvider


class ExplodingEmbeddingProvider(EmbeddingProvider):
    """If retrieval runs at all for a small-talk message, this fails the
    test loudly instead of silently succeeding for the wrong reason."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("embedding provider should not be called for small talk")

    @property
    def dimension(self) -> int:
        raise AssertionError("embedding provider should not be called for small talk")


class StaticChatProvider(ChatProvider):
    async def generate(self, messages: list[ChatMessage]) -> str:
        return "Hello! How can I help you with your data today?"


def _stub_out_session_store(monkeypatch):
    monkeypatch.setattr("ragchatbot.api.routes.chat.get_session_engine", lambda request: object())
    monkeypatch.setattr(
        "ragchatbot.api.routes.chat.get_or_create_session",
        lambda engine, session_id: session_id or "test-session",
    )
    monkeypatch.setattr("ragchatbot.api.routes.chat.get_recent_messages", lambda *a, **k: [])
    monkeypatch.setattr("ragchatbot.api.routes.chat.append_message", lambda *a, **k: None)


def test_small_talk_skips_retrieval_entirely(monkeypatch):
    _stub_out_session_store(monkeypatch)
    app = create_app()

    with TestClient(app) as client:
        app.state.embedding_provider = ExplodingEmbeddingProvider()
        app.state.chat_provider = StaticChatProvider()
        response = client.post("/chat", json={"message": "good morning"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Hello! How can I help you with your data today?"
    assert body["grounded"] is False
    assert body["citations"] == []
