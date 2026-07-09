from fastapi.testclient import TestClient

from ragchatbot.api.main import create_app
from ragchatbot.config.settings import get_settings


def test_reset_without_confirm_is_rejected_before_touching_the_db():
    app = create_app()
    with TestClient(app) as client:
        response = client.post("/admin/vector-store/reset", json={"tables": ["products"]})

    assert response.status_code == 400
    assert "confirm=true" in response.json()["detail"]


def test_ingest_unknown_table_is_rejected_before_touching_the_db(tmp_path, monkeypatch):
    tables_yaml = tmp_path / "tables.yaml"
    tables_yaml.write_text("tables:\n  - name: products\n    primary_key: id\n", encoding="utf-8")
    monkeypatch.setenv("TABLES_CONFIG_PATH", str(tables_yaml))
    get_settings.cache_clear()

    try:
        app = create_app()
        with TestClient(app) as client:
            response = client.post("/admin/ingest", json={"tables": ["does_not_exist"]})
    finally:
        get_settings.cache_clear()

    assert response.status_code == 400
    assert "does_not_exist" in response.json()["detail"]


def test_admin_endpoint_rejects_missing_key_when_configured(monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    get_settings.cache_clear()

    try:
        app = create_app()
        with TestClient(app) as client:
            response = client.post("/admin/vector-store/reset", json={"confirm": True})
    finally:
        get_settings.cache_clear()

    assert response.status_code == 401


def test_admin_endpoint_accepts_correct_key(tmp_path, monkeypatch):
    tables_yaml = tmp_path / "tables.yaml"
    tables_yaml.write_text("tables:\n  - name: products\n    primary_key: id\n", encoding="utf-8")
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    monkeypatch.setenv("TABLES_CONFIG_PATH", str(tables_yaml))
    get_settings.cache_clear()

    try:
        app = create_app()
        with TestClient(app) as client:
            response = client.post(
                "/admin/ingest",
                json={"tables": ["does_not_exist"]},
                headers={"X-Admin-Api-Key": "secret"},
            )
    finally:
        get_settings.cache_clear()

    # Auth passes (not 401); rejected instead by the unknown-table check,
    # proving the request reached route logic.
    assert response.status_code == 400
    assert "does_not_exist" in response.json()["detail"]
