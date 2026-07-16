from fastapi.testclient import TestClient

from ragchatbot.api.main import create_app
from ragchatbot.providers.base import EmbeddingProvider


class FailingEmbeddingProvider(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Error code: 403 - {'error': {'code': '403', 'message': 'blocked'}}")

    @property
    def dimension(self) -> int:
        raise RuntimeError("never reached")


def _stub_out_session_store(monkeypatch):
    # Session/history lookup runs before the small-talk/data-question
    # branch (both need it for conversation continuity), so it needs a live
    # vector-store DB unless stubbed — irrelevant to what this test is
    # actually checking (that an embedding-provider failure surfaces as a
    # clean 502), so stub it rather than requiring real infrastructure.
    monkeypatch.setattr("ragchatbot.api.routes.chat.get_session_engine", lambda request: object())
    monkeypatch.setattr(
        "ragchatbot.api.routes.chat.get_or_create_session",
        lambda engine, session_id: session_id or "test-session",
    )
    monkeypatch.setattr("ragchatbot.api.routes.chat.get_recent_messages", lambda *a, **k: [])
    monkeypatch.setattr("ragchatbot.api.routes.chat.append_message", lambda *a, **k: None)


def test_chat_returns_502_with_clear_detail_on_embedding_provider_failure(monkeypatch):
    _stub_out_session_store(monkeypatch)
    app = create_app()

    with TestClient(app) as client:
        app.state.embedding_provider = FailingEmbeddingProvider()
        # Not small talk, so this exercises the retrieval path where
        # get_vector_table() calls embedding_provider.embed().
        response = client.post("/chat", json={"message": "What is the price of the Widget?"})

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "Embedding provider call failed" in detail
    assert "403" in detail
