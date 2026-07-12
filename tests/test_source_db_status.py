from fastapi.testclient import TestClient

from ragchatbot.api.main import create_app
from ragchatbot.config.settings import get_settings


def test_source_db_status_reports_unreachable_connection(monkeypatch):
    # Point at a high, unlikely-to-be-bound port rather than assuming 5432
    # is free — a dev machine with postgres-source running (as ours is,
    # from earlier testing) would otherwise make this test flakily
    # pass/fail depending on ambient local state. build_engine's
    # connect_timeout bounds the worst case if it's filtered rather than
    # cleanly refused.
    monkeypatch.setenv("ADMIN_API_KEY", "")
    monkeypatch.setenv("SOURCE_DB_PORT", "58347")
    monkeypatch.setenv("SOURCE_DB_CONNECT_TIMEOUT_SECONDS", "1")
    get_settings.cache_clear()

    try:
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/admin/source-db/status")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    body = response.json()
    assert body["connected"] is False
    assert body["error"] is not None
    assert body["engine"] == "postgresql"


def test_source_db_status_requires_admin_key_when_configured(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    get_settings.cache_clear()

    try:
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/admin/source-db/status")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 401
