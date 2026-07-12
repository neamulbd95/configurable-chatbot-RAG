from fastapi.testclient import TestClient

from ragchatbot.api.main import create_app
from ragchatbot.providers.base import EmbeddingProvider


class FailingEmbeddingProvider(EmbeddingProvider):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Error code: 403 - {'error': {'code': '403', 'message': 'blocked'}}")

    @property
    def dimension(self) -> int:
        raise RuntimeError("never reached")


def test_chat_returns_502_with_clear_detail_on_embedding_provider_failure():
    # get_vector_table() calls embedding_provider.embed() before any DB
    # access (vector_table starts as None), so this exercises the 502 path
    # without needing a live database.
    app = create_app()
    with TestClient(app) as client:
        app.state.embedding_provider = FailingEmbeddingProvider()
        response = client.post("/chat", json={"message": "anything"})

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "Embedding provider call failed" in detail
    assert "403" in detail
