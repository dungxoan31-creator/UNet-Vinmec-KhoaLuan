import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")


def test_migration_is_idempotent(tmp_path):
    """Test that init_db safely adds review_revision and provenance_json to existing DBs."""
    legacy_db_path = tmp_path / "legacy_test.db"
    conn = sqlite3.connect(legacy_db_path)
    cursor = conn.cursor()
    # Create minimal legacy tables without review_revision and provenance_json
    cursor.execute("""
    CREATE TABLE studies (
        id VARCHAR(36) PRIMARY KEY,
        patient_id VARCHAR(36) NOT NULL,
        study_code VARCHAR(64),
        study_date VARCHAR(20) NOT NULL,
        status VARCHAR(30) DEFAULT 'PENDING',
        created_at DATETIME
    );
    """)
    cursor.execute("""
    CREATE TABLE images (
        id VARCHAR(36) PRIMARY KEY,
        study_id VARCHAR(36) NOT NULL,
        filename VARCHAR(255) NOT NULL,
        raw_path VARCHAR(500) NOT NULL,
        created_at DATETIME
    );
    """)
    cursor.execute("""
    CREATE TABLE predictions (
        id VARCHAR(36) PRIMARY KEY,
        image_id VARCHAR(36) NOT NULL,
        model_version VARCHAR(50),
        raw_mask_rle JSON,
        measurements JSON,
        created_at DATETIME
    );
    """)
    cursor.execute("""
    CREATE TABLE reviews (
        id VARCHAR(36) PRIMARY KEY,
        image_id VARCHAR(36) NOT NULL,
        verified_mask_rle JSON,
        created_at DATETIME
    );
    """)
    conn.commit()
    conn.close()

    # Import database module with custom DB_PATH
    from backend.db import database
    original_db_path = database.DB_PATH
    try:
        database.DB_PATH = str(legacy_db_path)
        database.DATABASE_URL = f"sqlite:///{legacy_db_path}"

        # First migration pass
        database.init_db()

        # Check columns were added
        conn = sqlite3.connect(legacy_db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(studies);")
        study_cols = [row[1] for row in cursor.fetchall()]
        assert "review_revision" in study_cols, "studies missing review_revision"

        cursor.execute("PRAGMA table_info(predictions);")
        pred_cols = [row[1] for row in cursor.fetchall()]
        assert "provenance_json" in pred_cols, "predictions missing provenance_json"
        conn.close()

        # Second migration pass (idempotent)
        database.init_db()
    finally:
        database.DB_PATH = original_db_path
        database.DATABASE_URL = f"sqlite:///{original_db_path}"


def test_old_prediction_provenance_remains_unknown(tmp_path):
    """Legacy predictions with provenance_json=None must not have active checkpoint hash fabricated."""
    from backend.app.main import app
    from backend.db import database

    client = TestClient(app)
    db = next(database.get_db())
    try:
        patient = database.PatientModel(
            id=str(uuid.uuid4()),
            anonymized_pid=f"TEST_PID_{uuid.uuid4().hex[:6]}",
        )
        db.add(patient)
        study = database.StudyModel(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            study_code="LEGACY_STUDY",
            study_date="2026-10-16",
            status="ANALYZED",
            review_revision=0,
        )
        db.add(study)
        image = database.ImageModel(
            id=str(uuid.uuid4()),
            study_id=study.id,
            filename="legacy_sample.png",
            raw_path="nonexistent.png",
            width=640,
            height=480,
        )
        db.add(image)
        pred = database.PredictionModel(
            id=str(uuid.uuid4()),
            image_id=image.id,
            model_version="LegacyModel-v1.0",
            raw_mask_rle={"counts": [307200], "first_val": 0, "shape": [512, 512]},
            measurements={},
            provenance_json=None,
        )
        db.add(pred)
        db.commit()

        study_id = study.id
    finally:
        db.close()

    from backend.app.routers.auth import create_access_token
    token = create_access_token({"sub": "doctor"})
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get(f"/api/cases/{study_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["review_revision"] == 0
    img_data = data["images"][0]
    pred_data = img_data["prediction"]
    assert pred_data is not None
    # Provenance should be None or not claim a fabricated active sha256
    prov = pred_data.get("provenance")
    if prov:
        assert prov.get("checkpoint_sha256") is None or prov.get("status") == "UNKNOWN"
        assert prov.get("model_version") == "LegacyModel-v1.0"


def test_prediction_provenance_survives_restart(tmp_path):
    """New prediction persists full provenance_json and reopens accurately."""
    from backend.app.config import model_registry
    from backend.app.main import app
    from backend.db import database

    adapter = model_registry.get_primary_adapter()
    active_checksum = getattr(getattr(adapter, "engine", None), "model_checksum", None)

    client = TestClient(app)
    db = next(database.get_db())
    try:
        patient = database.PatientModel(
            id=str(uuid.uuid4()),
            anonymized_pid=f"TEST_PROV_{uuid.uuid4().hex[:6]}",
        )
        db.add(patient)
        study = database.StudyModel(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            study_code="PROV_STUDY",
            study_date="2026-10-16",
            status="ANALYZED",
            review_revision=0,
        )
        db.add(study)
        image = database.ImageModel(
            id=str(uuid.uuid4()),
            study_id=study.id,
            filename="prov_sample.png",
            raw_path="nonexistent.png",
            width=640,
            height=480,
        )
        db.add(image)

        prov_payload = {
            "checkpoint_sha256": active_checksum,
            "serving_config_sha256": "abc123canonical",
            "architecture": "Attention U-Net",
            "threshold": 0.5,
            "native_shape": [480, 640],
            "transform": {
                "scale": 0.8,
                "pad_w": 0,
                "pad_h": 64,
                "new_w": 512,
                "new_h": 384,
                "orig_w": 640,
                "orig_h": 480,
            },
            "created_at": datetime.now(UTC).isoformat(),
        }
        pred = database.PredictionModel(
            id=str(uuid.uuid4()),
            image_id=image.id,
            model_version="AttentionUNet-v1.2",
            raw_mask_rle={"counts": [262144], "first_val": 0, "shape": [512, 512]},
            measurements={},
            provenance_json=prov_payload,
        )
        db.add(pred)
        db.commit()

        study_id = study.id
    finally:
        db.close()

    from backend.app.routers.auth import create_access_token
    token = create_access_token({"sub": "doctor"})
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get(f"/api/cases/{study_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["review_revision"] == 0
    img_data = data["images"][0]
    pred_data = img_data["prediction"]
    assert pred_data is not None
    prov = pred_data.get("provenance")
    assert prov is not None
    assert prov["checkpoint_sha256"] == active_checksum
    assert prov["architecture"] == "Attention U-Net"
    assert prov["threshold"] == 0.5
    assert prov["native_shape"] == [480, 640]
    assert prov["transform"]["scale"] == 0.8
    assert prov["transform"]["pad_h"] == 64
