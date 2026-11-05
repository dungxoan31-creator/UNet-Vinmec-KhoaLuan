import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers.auth import get_current_user
from backend.core.case_idempotency import case_create_idempotency_digest
from backend.db.database import (
    SessionLocal,
    StudyModel,
    UserModel,
    _migrate_case_idempotency_on_connection,
)


def test_case_create_replay_returns_same_study_and_rejects_changed_payload(doctor_access):
    key = uuid4()
    headers = {"Idempotency-Key": str(key)}
    payload = {
        "patient_id": f"{uuid4().int % 1_000_000_000:09d}",
        "study_date": "2026-10-29T10:15",
        "active_ovary_side": "LEFT",
        "contralateral_status": "NOT_VISUALIZED",
        "clinical_notes": "Synthetic retry contract case",
    }

    with TestClient(app) as client:
        first = client.post("/api/cases", json=payload, headers=headers)
        replay = client.post("/api/cases", json=payload, headers=headers)
        changed = client.post(
            "/api/cases",
            json={**payload, "study_date": "2026-10-30T10:15"},
            headers=headers,
        )

    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text
    assert replay.json()["study_id"] == first.json()["study_id"]
    assert replay.json()["visit_no"] == first.json()["visit_no"]
    assert "trước đó" in replay.json()["message"]
    assert changed.status_code == 409, changed.text

    digest = case_create_idempotency_digest(key, "test-doctor")
    with SessionLocal() as db:
        studies = db.query(StudyModel).filter_by(idempotency_key_digest=digest).all()
        assert len(studies) == 1
        assert studies[0].id == first.json()["study_id"]
        assert len(studies[0].idempotency_request_digest) == 64
        assert str(key) not in studies[0].idempotency_key_digest


def test_same_client_key_is_scoped_to_the_authenticated_doctor(doctor_access):
    key = uuid4()
    headers = {"Idempotency-Key": str(key)}
    payload = {"patient_id": f"{uuid4().int % 1_000_000_000:09d}", "study_date": "2026-10-29"}

    with TestClient(app) as client:
        first = client.post("/api/cases", json=payload, headers=headers)
        app.dependency_overrides[get_current_user] = lambda: UserModel(
            id="another-test-doctor", username="other-doctor", full_name="Other Doctor", role="DOCTOR", facility_id="FAC-DEFAULT-TEST"
        )
        second_user = client.post("/api/cases", json=payload, headers=headers)

    assert first.status_code == 200, first.text
    assert second_user.status_code == 200, second_user.text
    assert second_user.json()["study_id"] != first.json()["study_id"]


def test_invalid_idempotency_key_is_rejected(doctor_access):
    with TestClient(app) as client:
        response = client.post(
            "/api/cases",
            json={"patient_id": "900000118", "study_date": "2026-10-29"},
            headers={"Idempotency-Key": "not-a-uuid"},
        )
    assert response.status_code == 422, response.text


def test_case_creation_requires_idempotency_key(doctor_access):
    with TestClient(app) as client:
        response = client.post(
            "/api/cases",
            json={"patient_id": "900000119", "study_date": "2026-10-29"},
        )
    assert response.status_code == 422, response.text


def test_idempotency_header_is_allowed_by_cors_preflight():
    from fastapi.middleware.cors import CORSMiddleware

    cors = next(middleware for middleware in app.user_middleware if middleware.cls is CORSMiddleware)
    assert "Idempotency-Key" in cors.kwargs["allow_headers"]


def test_legacy_studies_table_migrates_case_idempotency_columns_and_unique_key():
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE TABLE studies (id VARCHAR(36) PRIMARY KEY)")
        _migrate_case_idempotency_on_connection(connection.cursor())
        columns = {row[1] for row in connection.execute("PRAGMA table_info(studies)")}
        assert {"idempotency_key_digest", "idempotency_request_digest"} <= columns

        digest = "a" * 64
        connection.execute(
            "INSERT INTO studies (id, idempotency_key_digest) VALUES (?, ?)", ("one", digest)
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO studies (id, idempotency_key_digest) VALUES (?, ?)", ("two", digest)
            )
        connection.execute(
            "INSERT INTO studies (id, idempotency_key_digest) VALUES (?, NULL)", ("legacy-one",)
        )
        connection.execute(
            "INSERT INTO studies (id, idempotency_key_digest) VALUES (?, NULL)", ("legacy-two",)
        )
    finally:
        connection.close()
