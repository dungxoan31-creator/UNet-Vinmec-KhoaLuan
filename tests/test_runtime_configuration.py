import json
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
    assert caps["research_export"] is False
    assert isinstance(caps["hitl_events"], bool)
    assert caps["manual_review"] is False
    assert caps["remote_lease"] is True
    assert caps["case_leases"] is True


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


def test_missing_secret_fails_actionably(tmp_path):
    """run_prototype.ps1 -CheckOnly fails with code 2 if required secrets are missing or too short."""
    script_path = PROJECT_ROOT / "scripts" / "run_prototype.ps1"
    env = dict(os.environ)
    env["APP_JWT_SECRET"] = "short-secret"
    env["APP_DOCTOR_PASSWORD"] = "doc-pass"
    env["APP_ADMIN_PASSWORD"] = "admin-pass"

    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-CheckOnly", "-RuntimeDir", str(tmp_path)],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "APP_JWT_SECRET" in proc.stdout or "APP_JWT_SECRET" in proc.stderr


@pytest.mark.parametrize("patient_secret", [None, "too-short"])
def test_launcher_requires_patient_id_hmac_secret(tmp_path, patient_secret):
    script_path = PROJECT_ROOT / "scripts" / "run_prototype.ps1"
    env = dict(os.environ)
    env["APP_JWT_SECRET"] = "test-secret-at-least-32-characters-long-2026"
    env["APP_DOCTOR_PASSWORD"] = "doctor-local-test-2026"
    env["APP_ADMIN_PASSWORD"] = "admin-local-test-2026"
    if patient_secret is None:
        env.pop("APP_PATIENT_PID_HMAC_SECRET", None)
    else:
        env["APP_PATIENT_PID_HMAC_SECRET"] = patient_secret

    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-CheckOnly", "-RuntimeDir", str(tmp_path)],
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 2
    assert "APP_PATIENT_PID_HMAC_SECRET" in (proc.stdout + proc.stderr)


def test_check_only_fails_on_missing_checkpoint(tmp_path):
    """run_prototype.ps1 -CheckOnly fails with code 2 if checkpoint path is missing."""
    script_path = PROJECT_ROOT / "scripts" / "run_prototype.ps1"
    env = dict(os.environ)
    env["APP_JWT_SECRET"] = "a" * 32
    env["APP_PATIENT_PID_HMAC_SECRET"] = "patient-id-hmac-secret-at-least-32-bytes"
    env["APP_DOCTOR_PASSWORD"] = "doc-pass"
    env["APP_ADMIN_PASSWORD"] = "admin-pass"
    env["CHECKPOINT_PATH"] = str(tmp_path / "non_existent.pth")

    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-CheckOnly", "-RuntimeDir", str(tmp_path)],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "checkpoint" in (proc.stdout + proc.stderr).lower()


def test_launch_uses_configured_runtime(tmp_path):
    """Technical pre-flight passes without implying synthetic isolation or clinical readiness."""
    script_path = PROJECT_ROOT / "scripts" / "run_prototype.ps1"
    env = dict(os.environ)
    env["APP_JWT_SECRET"] = "test-secret-at-least-32-characters-long-2026"
    env["APP_PATIENT_PID_HMAC_SECRET"] = "patient-id-hmac-secret-at-least-32-bytes"
    env["APP_DOCTOR_PASSWORD"] = "doctor-local-test-2026"
    env["APP_ADMIN_PASSWORD"] = "admin-local-test-2026"
    env.pop("APP_SYNTHETIC_DEMO_MODE", None)

    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-CheckOnly", "-RuntimeDir", str(tmp_path)],
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"CheckOnly failed: {proc.stdout}\n{proc.stderr}"
    output = " ".join((proc.stdout + proc.stderr).lower().split())
    assert "technical pre-flight checks passed" in output
    assert "not a clinical readiness check" in output
    assert "synthetic-only upload restriction is off" in output
    assert "do not use patient data" in output
    assert "clinical readiness or authorization" in output


def test_launcher_distinguishes_synthetic_mode_requested_from_runtime_validation(tmp_path):
    script_path = PROJECT_ROOT / "scripts" / "run_prototype.ps1"
    env = dict(os.environ)
    env["APP_JWT_SECRET"] = "test-secret-at-least-32-characters-long-2026"
    env["APP_PATIENT_PID_HMAC_SECRET"] = "patient-id-hmac-secret-at-least-32-bytes"
    env["APP_DOCTOR_PASSWORD"] = "doctor-local-test-2026"
    env["APP_ADMIN_PASSWORD"] = "admin-local-test-2026"
    env["APP_SYNTHETIC_DEMO_MODE"] = "true"

    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-CheckOnly", "-RuntimeDir", str(tmp_path)],
        env=env,
        capture_output=True,
        text=True,
    )

    output = " ".join((proc.stdout + proc.stderr).lower().split())
    assert proc.returncode == 0, f"CheckOnly failed: {proc.stdout}\n{proc.stderr}"
    assert "synthetic-only demo mode was requested" in output
    assert "backend startup must still validate" in output
    assert "synthetic-only upload restriction is off" not in output
    assert "not a clinical readiness check" in output


def test_launcher_preflight_verifies_selected_manifest_checkpoint(tmp_path):
    """The launcher must verify the same checkpoint the application loads from its model manifest."""
    script_path = PROJECT_ROOT / "scripts" / "run_prototype.ps1"
    selected_manifest = PROJECT_ROOT / "evaluation" / "selected_model.json"
    selection = json.loads(selected_manifest.read_text(encoding="utf-8"))
    manifest_path = tmp_path / "selected-model.json"
    manifest_path.write_text(json.dumps(selection), encoding="utf-8")
    env = dict(os.environ)
    env["APP_JWT_SECRET"] = "test-secret-at-least-32-characters-long-2026"
    env["APP_PATIENT_PID_HMAC_SECRET"] = "patient-id-hmac-secret-at-least-32-bytes"
    env["APP_DOCTOR_PASSWORD"] = "doctor-local-test-2026"
    env["APP_ADMIN_PASSWORD"] = "admin-local-test-2026"
    env["MODEL_SELECTION_MANIFEST"] = str(manifest_path)

    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-CheckOnly", "-RuntimeDir", str(tmp_path / "runtime")],
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, f"CheckOnly failed: {proc.stdout}\n{proc.stderr}"
    assert selection["checkpoint_sha256"] in proc.stdout


def test_launcher_preflight_rejects_manifest_checkpoint_hash_mismatch(tmp_path):
    """The launcher must fail before startup if the selected checkpoint differs from its manifest hash."""
    script_path = PROJECT_ROOT / "scripts" / "run_prototype.ps1"
    selection = json.loads((PROJECT_ROOT / "evaluation" / "selected_model.json").read_text(encoding="utf-8"))
    selection["checkpoint_sha256"] = "0" * 64
    manifest_path = tmp_path / "selected-model.json"
    manifest_path.write_text(json.dumps(selection), encoding="utf-8")
    env = dict(os.environ)
    env["APP_JWT_SECRET"] = "test-secret-at-least-32-characters-long-2026"
    env["APP_PATIENT_PID_HMAC_SECRET"] = "patient-id-hmac-secret-at-least-32-bytes"
    env["APP_DOCTOR_PASSWORD"] = "doctor-local-test-2026"
    env["APP_ADMIN_PASSWORD"] = "admin-local-test-2026"
    env["MODEL_SELECTION_MANIFEST"] = str(manifest_path)

    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-CheckOnly", "-RuntimeDir", str(tmp_path / "runtime")],
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 2
    assert "SHA-256 hash mismatch" in (proc.stdout + proc.stderr)


def test_no_secrets_in_logs(tmp_path):
    """Launcher output must never print actual secret strings."""
    script_path = PROJECT_ROOT / "scripts" / "run_prototype.ps1"
    secret_jwt = "super-secret-jwt-key-not-for-logs-12345"
    patient_hmac_secret = "super-secret-patient-hmac-key-not-for-logs-12345"
    doc_pass = "super-secret-doctor-password-xyz"
    admin_pass = "super-secret-admin-password-xyz"

    env = dict(os.environ)
    env["APP_JWT_SECRET"] = secret_jwt
    env["APP_PATIENT_PID_HMAC_SECRET"] = patient_hmac_secret
    env["APP_DOCTOR_PASSWORD"] = doc_pass
    env["APP_ADMIN_PASSWORD"] = admin_pass

    proc = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-CheckOnly", "-RuntimeDir", str(tmp_path)],
        env=env,
        capture_output=True,
        text=True,
    )
    output = proc.stdout + proc.stderr
    assert secret_jwt not in output, "JWT secret leaked in launcher output!"
    assert patient_hmac_secret not in output, "Patient HMAC secret leaked in launcher output!"
    assert doc_pass not in output, "Doctor password leaked in launcher output!"
    assert admin_pass not in output, "Admin password leaked in launcher output!"

