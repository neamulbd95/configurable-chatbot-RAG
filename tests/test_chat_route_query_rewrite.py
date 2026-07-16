from fastapi.testclient import TestClient

from ragchatbot.api.main import create_app
from ragchatbot.retrieval.pipeline import ContextPackage


def _stub_out_session_store(monkeypatch, history=None):
    monkeypatch.setattr("ragchatbot.api.routes.chat.get_session_engine", lambda request: object())
    monkeypatch.setattr(
        "ragchatbot.api.routes.chat.get_or_create_session",
        lambda engine, session_id: session_id or "test-session",
    )
    monkeypatch.setattr(
        "ragchatbot.api.routes.chat.get_recent_messages", lambda *a, **k: history or []
    )
    monkeypatch.setattr("ragchatbot.api.routes.chat.append_message", lambda *a, **k: None)


def _stub_out_vector_table(monkeypatch):
    # get_vector_table() would otherwise probe the embedding provider and
    # touch the vector store — irrelevant to what this test checks (that
    # the rewritten query reaches retrieve()), so bypass it.
    async def fake_get_vector_table(request):
        return object()

    monkeypatch.setattr("ragchatbot.api.routes.chat.get_vector_table", fake_get_vector_table)


def test_route_passes_rewritten_query_to_retrieval(monkeypatch):
    history = [
        {"role": "user", "content": "give a short summary on ESG Factsheet"},
        {"role": "assistant", "content": "The ESG Factsheet is ..."},
    ]
    _stub_out_session_store(monkeypatch, history=history)
    _stub_out_vector_table(monkeypatch)

    async def fake_rewrite_query(chat_provider, message, history):
        assert message == "who is the owner of this asset?"
        return "Who is the owner of the ESG Factsheet?"

    monkeypatch.setattr("ragchatbot.api.routes.chat.rewrite_query", fake_rewrite_query)

    captured = {}

    async def fake_retrieve(*, query, **kwargs):
        captured["query"] = query
        return ContextPackage(query=query, results=[])

    monkeypatch.setattr("ragchatbot.api.routes.chat.retrieve", fake_retrieve)

    app = create_app()
    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "who is the owner of this asset?"})

    assert response.status_code == 200
    assert captured["query"] == "Who is the owner of the ESG Factsheet?"
    # The raw message is still what's shown as ungrounded/used for the
    # final answer — rewriting only ever targets retrieval.
    assert response.json()["answer"]


def test_route_skips_rewrite_when_disabled(monkeypatch):
    _stub_out_session_store(monkeypatch, history=[{"role": "user", "content": "x"}])
    _stub_out_vector_table(monkeypatch)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("rewrite_query should not be called when disabled")

    monkeypatch.setattr("ragchatbot.api.routes.chat.rewrite_query", fail_if_called)

    captured = {}

    async def fake_retrieve(*, query, **kwargs):
        captured["query"] = query
        return ContextPackage(query=query, results=[])

    monkeypatch.setattr("ragchatbot.api.routes.chat.retrieve", fake_retrieve)

    from ragchatbot.config.settings import get_settings

    monkeypatch.setenv("QUERY_REWRITE_ENABLED", "false")
    get_settings.cache_clear()

    try:
        app = create_app()
        with TestClient(app) as client:
            response = client.post("/chat", json={"message": "who is the owner of this?"})
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert captured["query"] == "who is the owner of this?"
