"""
Tests for UI event telemetry batch ingestion endpoint (POST /api/hitl/events)
and KPI calculation script.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

os.environ["APP_JWT_SECRET"] = "production-ready-jwt-secret-key-32-chars-minimum"
os.environ["APP_PATIENT_PID_HMAC_SECRET"] = "production-ready-hmac-secret-key-32-chars-min"

from backend.app.main import app
from backend.app.security import create_access_token, hash_password
from backend.db.database import PatientModel, SessionLocal, StudyModel, UIEventModel, UserModel, init_db


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    init_db()
    with SessionLocal() as db:
        user = db.query(UserModel).filter(UserModel.username == "doctor_telemetry_test").first()
        if not user:
            user = UserModel(
                id="user-telemetry-test",
                username="doctor_telemetry_test",
                full_name="Dr. Test Telemetry",
                password_hash=hash_password("doctor123password"),
                role="DOCTOR",
                is_active=True,
            )
            db.add(user)
            db.commit()


@pytest.fixture
def auth_headers():
    token = create_access_token(
        data={"sub": "doctor_telemetry_test", "role": "DOCTOR", "user_id": "user-telemetry-test"},
        expires_delta=timedelta(hours=1),
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_study():
    with SessionLocal() as db:
        patient_id = str(uuid.uuid4())
        patient = PatientModel(
            id=patient_id,
            anonymized_pid=f"ANON-{patient_id[:8]}",
            created_at=datetime.now(UTC),
        )
        db.add(patient)
        study_id = str(uuid.uuid4())
        study = StudyModel(
            id=study_id,
            patient_id=patient_id,
            study_code="STU-TELEMETRY-001",
            status="PENDING",
            study_date="2026-10-25T14:00",
            created_at=datetime.now(UTC),
        )
        db.add(study)
        db.commit()
        return study_id


def test_post_ui_events_batch(auth_headers, test_study):
    client = TestClient(app)
    payload = {
        "events": [
            {
                "case_id": test_study,
                "event": "case_open",
                "t_ms": 1729860000000.0,
                "payload": {"source": "worklist"},
            },
            {
                "case_id": test_study,
                "event": "side_switch",
                "t_ms": 1729860002500.0,
                "payload": {"from": "L", "to": "R"},
            },
            {
                "case_id": test_study,
                "event": "field_edit",
                "t_ms": 1729860008000.0,
                "payload": {
                    "field": "oradsScore",
                    "old": "2",
                    "new": "3",
                    "source": "manual",
                },
            },
            {
                "case_id": test_study,
                "event": "print_click",
                "t_ms": 1729860015000.0,
                "payload": {"status": "SUCCESS"},
            },
        ]
    }
    response = client.post("/api/hitl/events", json=payload, headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["received"] == 4

    # Verify rows persisted in DB
    with SessionLocal() as db:
        events = (
            db.query(UIEventModel)
            .filter(UIEventModel.case_id == test_study)
            .order_by(UIEventModel.t_ms.asc())
            .all()
        )
        assert len(events) >= 4
        assert events[0].event_type == "case_open"
        assert events[1].event_type == "side_switch"
        assert events[2].event_type == "field_edit"
        assert events[2].payload_json["field"] == "oradsScore"
        assert events[3].event_type == "print_click"

        # Verify KPI report script calculations
        from scripts.kpi_report import calculate_case_kpis, generate_kpi_summary
        kpi = calculate_case_kpis(db, test_study)
        assert kpi["t_total_sec"] == 15.0  # 1729860015000 - 1729860000000 = 15000ms = 15s
        assert kpi["n_actions"] == 4
        assert kpi["n_fields_manual"] == 1

        summary = generate_kpi_summary(db)
        assert summary["total_cases"] >= 1
        assert summary["avg_t_total_sec"] > 0


def test_post_ui_events_discards_batch_entries_for_deleted_cases(auth_headers):
    client = TestClient(app)
    response = client.post(
        "/api/hitl/events",
        json={
            "events": [
                {
                    "case_id": "deleted-synthetic-study",
                    "event": "case_open",
                    "t_ms": 1729860000000.0,
                    "payload": {"source": "synthetic-test"},
                }
            ]
        },
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "SUCCESS",
        "received": 0,
        "discarded_unknown_case": 1,
    }
