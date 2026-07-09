from fastapi.testclient import TestClient

from ragchatbot.api.main import create_app


def test_health_and_ready_endpoints():
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/ready").json() == {"status": "ready"}
