import os
import subprocess
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_env_is_read_before_app_import(tmp_path):
    """Assert APP_DATA_DIR and APP_DB_PATH redirect storage and do not touch root DB."""
    tmp_data_dir = tmp_path / "data"
    tmp_db_path = tmp_path / "custom_dir" / "custom_test.db"
    
    root_db = PROJECT_ROOT / "ovarian_ai.db"
    root_db_mtime_before = root_db.stat().st_mtime if root_db.exists() else None

    script = f"""
import os, sys
from pathlib import Path

# Verify that env vars direct config and database
from backend.app import config
from backend.db import database

assert Path(config.DATA_DIR).resolve() == Path(r"{tmp_data_dir}").resolve(), f"DATA_DIR mismatch: {{config.DATA_DIR}}"
assert Path(config.UPLOAD_DIR).resolve() == Path(r"{tmp_data_dir / 'uploads'}").resolve(), f"UPLOAD_DIR mismatch: {{config.UPLOAD_DIR}}"
assert Path(database.DB_PATH).resolve() == Path(r"{tmp_db_path}").resolve(), f"DB_PATH mismatch: {{database.DB_PATH}}"

database.init_db()
assert Path(r"{tmp_db_path}").exists(), "Isolated DB file was not created"
print("ENV_TEST_SUCCESS")
"""

    env = dict(os.environ)
    env["APP_DATA_DIR"] = str(tmp_data_dir)
    env["APP_DB_PATH"] = str(tmp_db_path)
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    proc = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"Process failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "ENV_TEST_SUCCESS" in proc.stdout

    # Verify root db was not touched
    if root_db.exists():
        assert root_db.stat().st_mtime == root_db_mtime_before, "Root DB was touched by isolated runtime process!"


def test_health_reports_model_ready_and_capabilities():
    """Assert /api/health reports model_ready, checkpoint_sha256, and system capabilities."""
    from backend.app.main import app

    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert "model_ready" in data, "health response missing model_ready"
    assert isinstance(data["model_ready"], bool)
    assert "checkpoint_sha256" in data, "health response missing checkpoint_sha256"
    assert "capabilities" in data, "health response missing capabilities"

    caps = data["capabilities"]
    assert caps["case_workflow"] is False
    assert caps["research_review"] is True
    assert isinstance(caps["research_export"], bool)
    assert isinstance(caps["hitl_events"], bool)
    assert caps["manual_review"] is False
    assert caps["remote_lease"] is False


def test_health_does_not_claim_model_ready_when_unloaded(monkeypatch):
    """When primary adapter is not loaded, model_ready must be False and sha256 must be None."""
    from backend.app.config import model_registry
    from backend.app.main import app

    primary = model_registry.get_primary_adapter()
    monkeypatch.setattr(primary, "is_loaded", False)
    if hasattr(primary, "engine"):
        monkeypatch.setattr(primary.engine, "is_model_ready", False)

    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()

    assert data["model_ready"] is False
    assert data["checkpoint_sha256"] is None
