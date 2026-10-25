from fastapi.testclient import TestClient

from backend.app.main import app
from backend.db import database


def test_readiness_does_not_return_database_exception_details(monkeypatch, caplog):
    secret_detail = "sqlite:///private/runtime/patient-records.db"

    def failing_connect(*_args, **_kwargs):
        raise RuntimeError(secret_detail)

    monkeypatch.setattr(database.engine, "connect", failing_connect)

    response = TestClient(app).get("/api/health/ready")

    assert response.status_code == 503
    assert response.json()["database"] == "disconnected"
    assert "database_error" not in response.json()
    assert secret_detail not in response.text
    assert secret_detail not in caplog.text
