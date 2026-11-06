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
def auth_tokens(test_case_setup):
    from backend.app.routers.auth import create_access_token
    doc_token = create_access_token({"sub": "doctor"})
    other_token = create_access_token({"sub": "bacsi"})
    admin_token = create_access_token({"sub": "admin"})
    return {
        "doctor": {
            "Authorization": f"Bearer {doc_token}",
            "X-Case-Lease-Token": test_case_setup["lease_token"],
            "X-Case-Page-Instance-Id": test_case_setup["page_instance_id"],
        },
        "other_doctor": {"Authorization": f"Bearer {other_token}"},
        "admin": {"Authorization": f"Bearer {admin_token}"},
    }


@pytest.fixture
def test_case_setup():
    from backend.db import database
    db = next(database.get_db())
    try:
        facility = db.query(database.FacilityModel).filter_by(id="FAC-DEFAULT-TEST").first()
        if not facility:
            facility = database.FacilityModel(
                id="FAC-DEFAULT-TEST",
                facility_code="FAC-DEF-TEST",
                name="Default Test Facility",
                is_active=True,
            )
            db.add(facility)
            db.commit()

        doctor = db.query(database.UserModel).filter_by(username="doctor").first()
        if doctor and doctor.facility_id != "FAC-DEFAULT-TEST":
            doctor.facility_id = "FAC-DEFAULT-TEST"
            db.commit()

        other_doctor = db.query(database.UserModel).filter_by(username="bacsi").first()
        if other_doctor and other_doctor.facility_id != "FAC-DEFAULT-TEST":
            other_doctor.facility_id = "FAC-DEFAULT-TEST"
            db.commit()

        admin = db.query(database.UserModel).filter_by(username="admin").first()
        if admin:
            admin.is_global_admin = True
            admin.facility_id = "FAC-DEFAULT-TEST"
            db.commit()

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
            facility_id="FAC-DEFAULT-TEST",
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

        from backend.services.case_lease_service import acquire_case_lease

        doctor = db.query(database.UserModel).filter_by(username="doctor").one()
        page_instance_id = f"test-page-{uuid.uuid4().hex}"
        lease = acquire_case_lease(
            db,
            study.id,
            doctor,
            f"test-tab-{uuid.uuid4().hex}",
            page_instance_id,
            None,
        )

        return {
            "study_id": study.id,
            "img_l_id": img_l.id,
            "img_r_id": img_r.id,
            "pred_l_id": pred_l.id,
            "pred_r_id": pred_r.id,
            "lease_token": lease["lease_token"],
            "page_instance_id": page_instance_id,
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
    lease = {
        "lease_token": c["lease_token"],
        "page_instance_id": c["page_instance_id"],
    }

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
        **lease,
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
    assert res_batch.status_code == 200, res_batch.text

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
    ack_response = client.post(
        f"/api/hitl/sessions/{session_id}/events",
        json=ack_payload,
        headers=auth_tokens["doctor"],
    )
    assert ack_response.status_code == 200, ack_response.text

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


def test_session_event_limit_is_rechecked_after_append_lock(auth_tokens, test_case_setup, monkeypatch):
    from backend.app.main import app
    from backend.app.routers import hitl
    from backend.db.database import HITLEventModel, SessionLocal

    client = TestClient(app)
    case = test_case_setup
    created = client.post(
        "/api/hitl/sessions",
        json={"study_id": case["study_id"], "participant_code": "LIMIT_RACE"},
        headers=auth_tokens["doctor"],
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]

    with SessionLocal() as db:
        db.add_all(
            HITLEventModel(
                id=str(uuid.uuid4()),
                event_id=str(uuid.uuid4()),
                session_id=session_id,
                task_id=str(uuid.uuid4()),
                image_id=case["img_l_id"],
                seq=1,
                event_type="PREDICTION_VIEWED",
                client_utc="2026-10-29T12:00:00Z",
                elapsed_ms=1.0,
                session_elapsed_ms=1.0,
                payload_hash="0" * 64,
                payload={},
                actor_id="doctor",
            )
            for _ in range(9999)
        )
        db.commit()

    claim_lock = hitl._claim_hitl_session_for_append
    injected = False

    def append_one_concurrent_event_before_claim(db, session):
        nonlocal injected
        if not injected:
            injected = True
            db.rollback()
            with SessionLocal() as concurrent_db:
                concurrent_db.add(
                    HITLEventModel(
                        id=str(uuid.uuid4()),
                        event_id=str(uuid.uuid4()),
                        session_id=session_id,
                        task_id=str(uuid.uuid4()),
                        image_id=case["img_l_id"],
                        seq=1,
                        event_type="PREDICTION_VIEWED",
                        client_utc="2026-10-29T12:00:00Z",
                        elapsed_ms=1.0,
                        session_elapsed_ms=1.0,
                        payload_hash="1" * 64,
                        payload={},
                        actor_id="doctor",
                    )
                )
                concurrent_db.commit()
        return claim_lock(db, session)

    monkeypatch.setattr(hitl, "_claim_hitl_session_for_append", append_one_concurrent_event_before_claim)
    response = client.post(
        f"/api/hitl/sessions/{session_id}/events",
        json={
            "events": [
                {
                    "event_id": str(uuid.uuid4()),
                    "task_id": str(uuid.uuid4()),
                    "image_id": case["img_l_id"],
                    "seq": 1,
                    "event_type": "PREDICTION_VIEWED",
                    "client_utc": "2026-10-29T12:00:01Z",
                    "elapsed_ms": 2.0,
                    "session_elapsed_ms": 2.0,
                }
            ]
        },
        headers=auth_tokens["doctor"],
    )

    assert injected is True
    assert response.status_code == 422, response.text
    with SessionLocal() as db:
        assert db.query(HITLEventModel).filter_by(session_id=session_id).count() == 10000


@pytest.mark.parametrize("concurrent_winner_committed", [False, True])
def test_hitl_integrity_recovery_never_writes_outside_lock(
    auth_tokens, test_case_setup, monkeypatch, concurrent_winner_committed,
):
    import hashlib
    import json

    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    from backend.app.main import app
    from backend.db.database import HITLEventModel, SessionLocal

    client = TestClient(app)
    case = test_case_setup
    created = client.post(
        "/api/hitl/sessions",
        json={"study_id": case["study_id"], "participant_code": "INTEGRITY_RECOVERY"},
        headers=auth_tokens["doctor"],
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]
    event = {
        "event_id": str(uuid.uuid4()),
        "task_id": str(uuid.uuid4()),
        "image_id": case["img_l_id"],
        "seq": 1,
        "event_type": "PREDICTION_VIEWED",
        "client_utc": "2026-10-29T12:10:00Z",
        "elapsed_ms": 10.0,
        "session_elapsed_ms": 10.0,
        "payload": {},
    }
    identity_data = {
        "event_type": event["event_type"],
        "task_id": event["task_id"],
        "image_id": event["image_id"],
        "prediction_id": None,
        "seq": event["seq"],
        "client_utc": event["client_utc"],
        "elapsed_ms": event["elapsed_ms"],
        "session_elapsed_ms": event["session_elapsed_ms"],
        "payload": {},
    }
    identity_hash = hashlib.sha256(json.dumps(identity_data, sort_keys=True).encode("utf-8")).hexdigest()
    original_commit = Session.commit
    injected = False

    def commit_with_concurrent_integrity_failure(db):
        nonlocal injected
        event_row = db.query(HITLEventModel).filter_by(event_id=event["event_id"]).first()
        if not injected and event_row is not None:
            injected = True
            db.rollback()
            if concurrent_winner_committed:
                with SessionLocal() as winner_db:
                    winner_db.add(
                        HITLEventModel(
                            id=str(uuid.uuid4()),
                            event_id=event["event_id"],
                            session_id=session_id,
                            task_id=event["task_id"],
                            image_id=event["image_id"],
                            seq=event["seq"],
                            event_type=event["event_type"],
                            client_utc=event["client_utc"],
                            elapsed_ms=event["elapsed_ms"],
                            session_elapsed_ms=event["session_elapsed_ms"],
                            payload_hash=identity_hash,
                            payload={},
                            actor_id="doctor",
                        )
                    )
                    winner_db.commit()
            raise IntegrityError("simulated concurrent append", {}, RuntimeError("duplicate commit"))
        return original_commit(db)

    monkeypatch.setattr(Session, "commit", commit_with_concurrent_integrity_failure)
    response = client.post(
        f"/api/hitl/sessions/{session_id}/events",
        json={"events": [event]},
        headers=auth_tokens["doctor"],
    )

    assert injected is True
    if concurrent_winner_committed:
        assert response.status_code == 200, response.text
        assert response.json()["accepted_count"] == 0
        assert response.json()["duplicate_count"] == 1
        expected_count = 1
    else:
        assert response.status_code == 409, response.text
        expected_count = 0
    with SessionLocal() as db:
        assert db.query(HITLEventModel).filter_by(session_id=session_id).count() == expected_count


@pytest.mark.parametrize("terminal_status", ["COMPLETED", "ABORTED"])
def test_terminal_hitl_session_rejects_new_events(auth_tokens, test_case_setup, terminal_status):
    from backend.app.main import app
    from backend.db.database import HITLEventModel, HITLSessionModel, SessionLocal

    client = TestClient(app)
    case = test_case_setup
    created = client.post(
        "/api/hitl/sessions",
        json={"study_id": case["study_id"], "participant_code": "TERMINAL_TEST"},
        headers=auth_tokens["doctor"],
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "task_id": str(uuid.uuid4()),
                "image_id": case["img_l_id"],
                "seq": 1,
                "event_type": "PREDICTION_VIEWED",
                "client_utc": "2026-10-21T12:00:00Z",
                "elapsed_ms": 100.0,
                "session_elapsed_ms": 100.0,
            }
        ]
    }
    first_response = client.post(
        f"/api/hitl/sessions/{session_id}/events",
        json=payload,
        headers=auth_tokens["doctor"],
    )
    assert first_response.status_code == 200
    with SessionLocal() as db:
        session = db.get(HITLSessionModel, session_id)
        session.status = terminal_status
        db.commit()

    replay = client.post(
        f"/api/hitl/sessions/{session_id}/events",
        json=payload,
        headers=auth_tokens["doctor"],
    )
    assert replay.status_code == 200
    assert replay.json()["duplicate_count"] == 1
    payload["events"][0]["event_id"] = str(uuid.uuid4())
    payload["events"][0]["seq"] = 2
    response = client.post(
        f"/api/hitl/sessions/{session_id}/events",
        json=payload,
        headers=auth_tokens["doctor"],
    )
    assert response.status_code == 409
    with SessionLocal() as db:
        assert db.query(HITLEventModel).filter_by(session_id=session_id).count() == 1


@pytest.mark.parametrize("terminal_status", ["COMPLETED", "ABORTED"])
def test_review_batch_cannot_reopen_terminal_hitl_session(
    auth_tokens, test_case_setup, terminal_status
):
    from backend.app.main import app
    from backend.db.database import HITLSessionModel, ReviewModel, SessionLocal, StudyModel

    client = TestClient(app)
    case = test_case_setup
    lease = {
        "lease_token": case["lease_token"],
        "page_instance_id": case["page_instance_id"],
    }
    created = client.post(
        "/api/hitl/sessions",
        json={"study_id": case["study_id"], "participant_code": "TERMINAL_REVIEW_TEST"},
        headers=auth_tokens["doctor"],
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]
    with SessionLocal() as db:
        session = db.get(HITLSessionModel, session_id)
        session.status = terminal_status
        db.commit()

    request_id = str(uuid.uuid4())
    empty_mask = {"shape": [512, 512], "first_val": 0, "counts": [262144]}
    response = client.post(
        "/api/reviews/batch",
        json={
            "study_id": case["study_id"],
            "expected_revision": 0,
            "request_id": request_id,
            **lease,
            "hitl_session_id": session_id,
            "reviews": [
                {
                    "image_id": case["img_l_id"],
                    "prediction_id": case["pred_l_id"],
                    "doctor_action": "ACCEPTED_RAW",
                    "verified_mask_rle": empty_mask,
                },
                {
                    "image_id": case["img_r_id"],
                    "prediction_id": case["pred_r_id"],
                    "doctor_action": "ACCEPTED_RAW",
                    "verified_mask_rle": empty_mask,
                },
            ],
        },
        headers=auth_tokens["doctor"],
    )
    assert response.status_code == 409
    with SessionLocal() as db:
        session = db.get(HITLSessionModel, session_id)
        study = db.get(StudyModel, case["study_id"])
        assert session.status == terminal_status
        assert study.review_revision == 0
        assert db.query(ReviewModel).filter_by(image_id=case["img_l_id"]).count() == 0


def test_hitl_session_cannot_be_linked_to_multiple_review_batches(
    auth_tokens, test_case_setup
):
    from backend.app.main import app
    from backend.db.database import HITLSessionModel, ReviewBatchModel, SessionLocal, StudyModel

    client = TestClient(app)
    case = test_case_setup
    lease = {
        "lease_token": case["lease_token"],
        "page_instance_id": case["page_instance_id"],
    }
    created = client.post(
        "/api/hitl/sessions",
        json={"study_id": case["study_id"], "participant_code": "SINGLE_BATCH_TEST"},
        headers=auth_tokens["doctor"],
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]
    empty_mask = {"shape": [512, 512], "first_val": 0, "counts": [262144]}

    def batch_payload(expected_revision, request_id):
        return {
            "study_id": case["study_id"],
            "expected_revision": expected_revision,
            "request_id": request_id,
            **lease,
            "hitl_session_id": session_id,
            "reviews": [
                {
                    "image_id": case["img_l_id"],
                    "prediction_id": case["pred_l_id"],
                    "doctor_action": "ACCEPTED_RAW",
                    "verified_mask_rle": empty_mask,
                },
                {
                    "image_id": case["img_r_id"],
                    "prediction_id": case["pred_r_id"],
                    "doctor_action": "ACCEPTED_RAW",
                    "verified_mask_rle": empty_mask,
                },
            ],
        }

    first_request_id = str(uuid.uuid4())
    first_response = client.post(
        "/api/reviews/batch",
        json=batch_payload(0, first_request_id),
        headers=auth_tokens["doctor"],
    )
    assert first_response.status_code == 200, first_response.text
    with SessionLocal() as db:
        session = db.get(HITLSessionModel, session_id)
        first_batch_id = session.review_batch_id
        assert session.status == "INCOMPLETE"
        assert first_batch_id is not None

    second_response = client.post(
        "/api/reviews/batch",
        json=batch_payload(1, str(uuid.uuid4())),
        headers=auth_tokens["doctor"],
    )
    assert second_response.status_code == 409
    with SessionLocal() as db:
        session = db.get(HITLSessionModel, session_id)
        study = db.get(StudyModel, case["study_id"])
        assert session.review_batch_id == first_batch_id
        assert session.status == "INCOMPLETE"
        assert study.review_revision == 1
        assert db.query(ReviewBatchModel).filter_by(study_id=case["study_id"]).count() == 1


def test_stale_hitl_session_snapshot_cannot_claim_new_events(auth_tokens, test_case_setup):
    from fastapi import HTTPException

    from backend.app.main import app
    from backend.app.routers.hitl import _claim_hitl_session_for_append
    from backend.db.database import HITLSessionModel, SessionLocal

    client = TestClient(app)
    created = client.post(
        "/api/hitl/sessions",
        json={"study_id": test_case_setup["study_id"], "participant_code": "STALE_SESSION_TEST"},
        headers=auth_tokens["doctor"],
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]

    stale_db = SessionLocal()
    state_db = SessionLocal()
    try:
        stale_session = stale_db.get(HITLSessionModel, session_id)
        assert stale_session.status == "IN_PROGRESS"
        current_session = state_db.get(HITLSessionModel, session_id)
        current_session.status = "ABORTED"
        state_db.commit()

        with pytest.raises(HTTPException) as error:
            _claim_hitl_session_for_append(stale_db, stale_session)
        assert error.value.status_code == 409
        assert stale_db.get(HITLSessionModel, session_id).status == "ABORTED"
    finally:
        stale_db.close()
        state_db.close()


def test_stale_hitl_session_snapshot_cannot_link_review_batch(auth_tokens, test_case_setup):
    from fastapi import HTTPException

    from backend.app.main import app
    from backend.db.database import HITLSessionModel, SessionLocal
    from backend.services.review_service import _claim_hitl_session_for_review

    client = TestClient(app)
    created = client.post(
        "/api/hitl/sessions",
        json={"study_id": test_case_setup["study_id"], "participant_code": "STALE_REVIEW_LINK_TEST"},
        headers=auth_tokens["doctor"],
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]

    stale_db = SessionLocal()
    state_db = SessionLocal()
    try:
        stale_session = stale_db.get(HITLSessionModel, session_id)
        assert stale_session.status == "IN_PROGRESS"
        current_session = state_db.get(HITLSessionModel, session_id)
        current_session.status = "ABORTED"
        state_db.commit()

        with pytest.raises(HTTPException) as error:
            _claim_hitl_session_for_review(stale_db, stale_session, str(uuid.uuid4()))
        assert error.value.status_code == 409
        state_db.refresh(current_session)
        assert current_session.status == "ABORTED"
        assert current_session.review_batch_id is None
    finally:
        stale_db.close()
        state_db.close()


def test_session_abort_must_be_last_event_in_batch(auth_tokens, test_case_setup):
    from backend.app.main import app
    from backend.db.database import HITLEventModel, HITLSessionModel, SessionLocal

    client = TestClient(app)
    case = test_case_setup
    created = client.post(
        "/api/hitl/sessions",
        json={"study_id": case["study_id"], "participant_code": "ABORT_ORDER_TEST"},
        headers=auth_tokens["doctor"],
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]
    task_id = str(uuid.uuid4())
    payload = {
        "events": [
            {
                "event_id": str(uuid.uuid4()),
                "task_id": task_id,
                "image_id": case["img_l_id"],
                "seq": 1,
                "event_type": "SESSION_ABORTED",
                "client_utc": "2026-10-21T12:00:00Z",
                "elapsed_ms": 100.0,
                "session_elapsed_ms": 100.0,
            },
            {
                "event_id": str(uuid.uuid4()),
                "task_id": task_id,
                "image_id": case["img_l_id"],
                "seq": 2,
                "event_type": "PREDICTION_VIEWED",
                "client_utc": "2026-10-21T12:00:01Z",
                "elapsed_ms": 200.0,
                "session_elapsed_ms": 200.0,
            },
        ]
    }
    response = client.post(
        f"/api/hitl/sessions/{session_id}/events",
        json=payload,
        headers=auth_tokens["doctor"],
    )
    assert response.status_code == 409
    with SessionLocal() as db:
        session = db.get(HITLSessionModel, session_id)
        assert session.status == "IN_PROGRESS"
        assert db.query(HITLEventModel).filter_by(session_id=session_id).count() == 0


@pytest.mark.parametrize(
    "event_overrides",
    [
        {"payload": {"error": "x" * 4097}},
        {"payload": {"details": {"nested": "value"}}},
        {"event_id": "x" * 37},
        {"event_id": "x" * 65},
        {"task_id": "x" * 37},
        {"image_id": "x" * 37},
        {"prediction_id": "x" * 37},
        {"client_utc": "not-a-timestamp"},
        {"client_utc": "2026-10-21T12:00:00"},
        {"client_utc": "2026-10-21T12:00:00+05:00"},
        {"unexpected": "ignored data must be rejected"},
    ],
)
def test_hitl_event_request_schema_bounds_and_rejects_unrecognized_data(event_overrides):
    from pydantic import ValidationError

    from backend.schemas.schemas import HITLEventItem

    event = {
        "event_id": str(uuid.uuid4()),
        "task_id": str(uuid.uuid4()),
        "image_id": str(uuid.uuid4()),
        "seq": 1,
        "event_type": "EDIT_COMMITTED",
        "client_utc": "2026-10-21T12:00:00Z",
        "elapsed_ms": 10.0,
        "session_elapsed_ms": 10.0,
        "payload": {"tool": "brush", "changed_pixels": 4},
    }
    event.update(event_overrides)

    with pytest.raises(ValidationError):
        HITLEventItem(**event)


def test_hitl_event_accepts_utc_iso8601_timestamp():
    from backend.schemas.schemas import HITLEventItem

    event = {
        "event_id": str(uuid.uuid4()),
        "task_id": str(uuid.uuid4()),
        "image_id": str(uuid.uuid4()),
        "seq": 1,
        "event_type": "EDIT_COMMITTED",
        "client_utc": "2026-10-21T12:00:00+00:00",
        "elapsed_ms": 10.0,
        "session_elapsed_ms": 10.0,
    }

    assert HITLEventItem(**event).client_utc == event["client_utc"]
