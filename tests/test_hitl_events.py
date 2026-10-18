"""
Unit and integration tests for authenticated HITL session and event ingestion (Task 12).
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")


@pytest.fixture
def auth_tokens():
    from backend.app.routers.auth import create_access_token
    doc_token = create_access_token({"sub": "doctor"})
    other_token = create_access_token({"sub": "bacsi"})
    admin_token = create_access_token({"sub": "admin"})
    return {
        "doctor": {"Authorization": f"Bearer {doc_token}"},
        "other_doctor": {"Authorization": f"Bearer {other_token}"},
        "admin": {"Authorization": f"Bearer {admin_token}"},
    }


@pytest.fixture
def test_case_setup():
    from backend.db import database
    db = next(database.get_db())
    try:
        patient = database.PatientModel(
            id=str(uuid.uuid4()),
            anonymized_pid=f"TEST_HITL_{uuid.uuid4().hex[:8]}",
        )
        db.add(patient)
        study = database.StudyModel(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            study_code="STUDY_HITL_001",
            study_date="2026-10-16",
            status="ANALYZED",
            ovary_side="BOTH",
            review_revision=0,
        )
        db.add(study)

        img_l = database.ImageModel(
            id=str(uuid.uuid4()),
            study_id=study.id,
            filename="left.png",
            laterality="L",
            raw_path="left.png",
            width=512,
            height=512,
        )
        img_r = database.ImageModel(
            id=str(uuid.uuid4()),
            study_id=study.id,
            filename="right.png",
            laterality="R",
            raw_path="right.png",
            width=512,
            height=512,
        )
        db.add_all([img_l, img_r])

        pred_l = database.PredictionModel(
            id=str(uuid.uuid4()),
            image_id=img_l.id,
            model_version="AttentionUNet-v1.2",
            raw_mask_rle={"shape": [512, 512], "first_val": 0, "counts": [262144]},
            measurements={},
        )
        pred_r = database.PredictionModel(
            id=str(uuid.uuid4()),
            image_id=img_r.id,
            model_version="AttentionUNet-v1.2",
            raw_mask_rle={"shape": [512, 512], "first_val": 0, "counts": [262144]},
            measurements={},
        )
        db.add_all([pred_l, pred_r])
        db.commit()

        return {
            "study_id": study.id,
            "img_l_id": img_l.id,
            "img_r_id": img_r.id,
            "pred_l_id": pred_l.id,
            "pred_r_id": pred_r.id,
        }
    finally:
        db.close()


def test_owner_and_sequence_validation(auth_tokens, test_case_setup):
    from backend.app.main import app
    client = TestClient(app)
    c = test_case_setup

    # 1. Doctor creates session
    res_sess = client.post(
        "/api/hitl/sessions",
        json={
            "study_id": c["study_id"],
            "participant_code": "CLINICIAN_01",
            "participant_role": "clinician",
            "data_origin": "live",
        },
        headers=auth_tokens["doctor"],
    )
    assert res_sess.status_code == 200, res_sess.text
    session_id = res_sess.json()["id"]

    # 2. Other doctor cannot append events to doctor's session -> 403
    task_id = str(uuid.uuid4())
    event_payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "task_id": task_id,
                "image_id": c["img_l_id"],
                "prediction_id": c["pred_l_id"],
                "seq": 1,
                "event_type": "PREDICTION_VIEWED",
                "client_utc": "2026-10-16T12:00:00Z",
                "elapsed_ms": 100.0,
                "session_elapsed_ms": 100.0,
            }
        ]
    }
    res_other = client.post(
        f"/api/hitl/sessions/{session_id}/events",
        json=event_payload,
        headers=auth_tokens["other_doctor"],
    )
    assert res_other.status_code == 403

    # 3. Owner can append events
    res_owner = client.post(
        f"/api/hitl/sessions/{session_id}/events",
        json=event_payload,
        headers=auth_tokens["doctor"],
    )
    assert res_owner.status_code == 200, res_owner.text
    assert res_owner.json()["accepted_count"] == 1


def test_event_duplicate_is_idempotent(auth_tokens, test_case_setup):
    from backend.app.main import app
    client = TestClient(app)
    c = test_case_setup

    res_sess = client.post(
        "/api/hitl/sessions",
        json={
            "study_id": c["study_id"],
            "participant_code": "TECH_01",
            "participant_role": "technical_tester",
            "data_origin": "live",
        },
        headers=auth_tokens["doctor"],
    )
    session_id = res_sess.json()["id"]

    ev_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    payload = {
        "events": [
            {
                "event_id": ev_id,
                "task_id": task_id,
                "image_id": c["img_l_id"],
                "seq": 1,
                "event_type": "PREDICTION_VIEWED",
                "client_utc": "2026-10-16T12:00:00Z",
                "elapsed_ms": 50.0,
                "session_elapsed_ms": 50.0,
            }
        ]
    }

    # First send -> accepted 1
    resp1 = client.post(f"/api/hitl/sessions/{session_id}/events", json=payload, headers=auth_tokens["doctor"])
    assert resp1.status_code == 200
    assert resp1.json()["accepted_count"] == 1

    # Exact replay -> duplicate_count 1, accepted 0, status 200
    resp2 = client.post(f"/api/hitl/sessions/{session_id}/events", json=payload, headers=auth_tokens["doctor"])
    assert resp2.status_code == 200
    assert resp2.json()["duplicate_count"] == 1
    assert resp2.json()["accepted_count"] == 0


def test_event_id_payload_conflict(auth_tokens, test_case_setup):
    from backend.app.main import app
    client = TestClient(app)
    c = test_case_setup

    res_sess = client.post(
        "/api/hitl/sessions",
        json={
            "study_id": c["study_id"],
            "participant_code": "TECH_02",
            "participant_role": "technical_tester",
            "data_origin": "live",
        },
        headers=auth_tokens["doctor"],
    )
    session_id = res_sess.json()["id"]

    ev_id = str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    payload1 = {
        "events": [
            {
                "event_id": ev_id,
                "task_id": task_id,
                "image_id": c["img_l_id"],
                "seq": 1,
                "event_type": "PREDICTION_VIEWED",
                "client_utc": "2026-10-16T12:00:00Z",
                "elapsed_ms": 50.0,
                "session_elapsed_ms": 50.0,
                "payload": {"zoom": 1.0},
            }
        ]
    }
    client.post(f"/api/hitl/sessions/{session_id}/events", json=payload1, headers=auth_tokens["doctor"])

    # Reusing same event_id with different payload -> 409
    payload2 = {
        "events": [
            {
                "event_id": ev_id,
                "task_id": task_id,
                "image_id": c["img_l_id"],
                "seq": 1,
                "event_type": "PREDICTION_VIEWED",
                "client_utc": "2026-10-16T12:00:00Z",
                "elapsed_ms": 50.0,
                "session_elapsed_ms": 50.0,
                "payload": {"zoom": 2.0},
            }
        ]
    }
    resp = client.post(f"/api/hitl/sessions/{session_id}/events", json=payload2, headers=auth_tokens["doctor"])
    assert resp.status_code == 409


def test_rejects_negative_nonfinite_duration(auth_tokens, test_case_setup):
    from backend.app.main import app
    client = TestClient(app)
    c = test_case_setup

    res_sess = client.post(
        "/api/hitl/sessions",
        json={"study_id": c["study_id"], "participant_code": "TECH_03", "participant_role": "technical_tester", "data_origin": "live"},
        headers=auth_tokens["doctor"],
    )
    session_id = res_sess.json()["id"]

    # Negative elapsed_ms -> 422
    payload_neg = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "task_id": str(uuid.uuid4()),
                "image_id": c["img_l_id"],
                "seq": 1,
                "event_type": "PREDICTION_VIEWED",
                "client_utc": "2026-10-16T12:00:00Z",
                "elapsed_ms": -10.0,
                "session_elapsed_ms": 10.0,
            }
        ]
    }
    resp = client.post(f"/api/hitl/sessions/{session_id}/events", json=payload_neg, headers=auth_tokens["doctor"])
    assert resp.status_code == 422


def test_rejects_wrong_case_and_demo(auth_tokens, test_case_setup):
    from backend.app.main import app
    client = TestClient(app)
    c = test_case_setup

    res_sess = client.post(
        "/api/hitl/sessions",
        json={"study_id": c["study_id"], "participant_code": "TECH_04", "participant_role": "technical_tester", "data_origin": "live"},
        headers=auth_tokens["doctor"],
    )
    session_id = res_sess.json()["id"]

    # Image that does not belong to study -> 422
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "task_id": str(uuid.uuid4()),
                "image_id": "non-existent-img-id",
                "seq": 1,
                "event_type": "PREDICTION_VIEWED",
                "client_utc": "2026-10-16T12:00:00Z",
                "elapsed_ms": 10.0,
                "session_elapsed_ms": 10.0,
            }
        ]
    }
    resp = client.post(f"/api/hitl/sessions/{session_id}/events", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 422


def test_only_server_can_confirm_session(auth_tokens, test_case_setup):
    from backend.app.main import app
    client = TestClient(app)
    c = test_case_setup

    res_sess = client.post(
        "/api/hitl/sessions",
        json={"study_id": c["study_id"], "participant_code": "TECH_05", "participant_role": "technical_tester", "data_origin": "live"},
        headers=auth_tokens["doctor"],
    )
    session_id = res_sess.json()["id"]

    # Client attempting to submit CONFIRM_SUCCEEDED -> rejected (422 or 403)
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "task_id": str(uuid.uuid4()),
                "image_id": c["img_l_id"],
                "seq": 1,
                "event_type": "CONFIRM_SUCCEEDED",
                "client_utc": "2026-10-16T12:00:00Z",
                "elapsed_ms": 500.0,
                "session_elapsed_ms": 500.0,
            }
        ]
    }
    resp = client.post(f"/api/hitl/sessions/{session_id}/events", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code in (403, 422)


def test_missing_final_ack_is_incomplete(auth_tokens, test_case_setup):
    from backend.app.main import app
    client = TestClient(app)
    c = test_case_setup

    # Create session
    res_sess = client.post(
        "/api/hitl/sessions",
        json={"study_id": c["study_id"], "participant_code": "TECH_06", "participant_role": "technical_tester", "data_origin": "live"},
        headers=auth_tokens["doctor"],
    )
    session_id = res_sess.json()["id"]
    task_l = str(uuid.uuid4())
    task_r = str(uuid.uuid4())

    # Send client events without CONFIRM_ACK
    events_payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "task_id": task_l,
                "image_id": c["img_l_id"],
                "seq": 1,
                "event_type": "PREDICTION_VIEWED",
                "client_utc": "2026-10-16T12:00:00Z",
                "elapsed_ms": 10.0,
                "session_elapsed_ms": 10.0,
            },
            {
                "event_id": str(uuid.uuid4()),
                "task_id": task_r,
                "image_id": c["img_r_id"],
                "seq": 1,
                "event_type": "PREDICTION_VIEWED",
                "client_utc": "2026-10-16T12:00:01Z",
                "elapsed_ms": 10.0,
                "session_elapsed_ms": 20.0,
            },
        ]
    }
    client.post(f"/api/hitl/sessions/{session_id}/events", json=events_payload, headers=auth_tokens["doctor"])

    # Perform batch review linked to session
    req_id = str(uuid.uuid4())
    batch_payload = {
        "study_id": c["study_id"],
        "expected_revision": 0,
        "request_id": req_id,
        "hitl_session_id": session_id,
        "reviews": [
            {
                "image_id": c["img_l_id"],
                "prediction_id": c["pred_l_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": {"shape": [512, 512], "first_val": 0, "counts": [262144]},
            },
            {
                "image_id": c["img_r_id"],
                "prediction_id": c["pred_r_id"],
                "doctor_action": "ACCEPTED_RAW",
                "verified_mask_rle": {"shape": [512, 512], "first_val": 0, "counts": [262144]},
            },
        ],
    }
    res_batch = client.post("/api/reviews/batch", json=batch_payload, headers=auth_tokens["doctor"])
    assert res_batch.status_code == 200

    # Query session: because CONFIRM_ACK was never sent by client, status must be INCOMPLETE
    res_info = client.get(f"/api/hitl/sessions/{session_id}", headers=auth_tokens["doctor"])
    assert res_info.status_code == 200
    sess_data = res_info.json()
    assert sess_data["status"] == "INCOMPLETE"
    assert sess_data["completed_at"] is None

    # Now client sends matching CONFIRM_ACK for both tasks
    ack_payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "task_id": task_l,
                "image_id": c["img_l_id"],
                "seq": 2,
                "event_type": "CONFIRM_ACK",
                "client_utc": "2026-10-16T12:00:05Z",
                "elapsed_ms": 5000.0,
                "session_elapsed_ms": 5000.0,
                "payload": {"batch_request_id": req_id},
            },
            {
                "event_id": str(uuid.uuid4()),
                "task_id": task_r,
                "image_id": c["img_r_id"],
                "seq": 2,
                "event_type": "CONFIRM_ACK",
                "client_utc": "2026-10-16T12:00:05Z",
                "elapsed_ms": 5000.0,
                "session_elapsed_ms": 5000.0,
                "payload": {"batch_request_id": req_id},
            },
        ]
    }
    client.post(f"/api/hitl/sessions/{session_id}/events", json=ack_payload, headers=auth_tokens["doctor"])

    # Now session becomes COMPLETED!
    res_info2 = client.get(f"/api/hitl/sessions/{session_id}", headers=auth_tokens["doctor"])
    assert res_info2.json()["status"] == "COMPLETED"
    assert res_info2.json()["completed_at"] is not None


def test_event_limits(auth_tokens, test_case_setup):
    from backend.app.main import app
    client = TestClient(app)
    c = test_case_setup

    res_sess = client.post(
        "/api/hitl/sessions",
        json={"study_id": c["study_id"], "participant_code": "LIMIT_01", "participant_role": "technical_tester", "data_origin": "live"},
        headers=auth_tokens["doctor"],
    )
    session_id = res_sess.json()["id"]

    # More than 100 events in a batch -> 422
    huge_batch = [
        {
            "event_id": str(uuid.uuid4()),
            "task_id": str(uuid.uuid4()),
            "image_id": c["img_l_id"],
            "seq": i + 1,
            "event_type": "PREDICTION_VIEWED",
            "client_utc": "2026-10-16T12:00:00Z",
            "elapsed_ms": float(i),
            "session_elapsed_ms": float(i),
        }
        for i in range(101)
    ]
    resp = client.post(f"/api/hitl/sessions/{session_id}/events", json={"events": huge_batch}, headers=auth_tokens["doctor"])
    assert resp.status_code == 422
