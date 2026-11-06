from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.db.database import SessionLocal, StudyModel
from tests.helpers.fixture_factory import create_test_image


def reserve(client):
    response = client.post("/api/cases", json={"study_date": "2026-11-03T10:15"},
                           headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 200, response.text
    return response.json()


def lease_headers(client, study_id, active_case_lease):
    lease = active_case_lease(client, study_id)
    return {"X-Case-Lease-Token": lease["lease_token"],
            "X-Case-Page-Instance-Id": lease["page_instance_id"]}


def test_reserved_visit_is_reused_when_completing_sides(doctor_access, active_case_lease):
    with TestClient(app) as client:
        visit = reserve(client)
        path = f"/api/cases/{visit['study_id']}/intake-sides"
        payload = {"active_ovary_side": "LEFT", "contralateral_status": "NOT_VISUALIZED"}
        assert client.put(path, json=payload).status_code == 423
        headers = lease_headers(client, visit["study_id"], active_case_lease)
        for _ in range(2):
            response = client.put(path, json=payload, headers=headers)
            assert response.status_code == 200, response.text
            assert response.json()["study_id"] == visit["study_id"]
            assert response.json()["visit_no"] == visit["visit_no"]
            assert response.json()["ovary_side"] == "LEFT"
        assert client.put(path, json={"active_ovary_side": "RIGHT"}, headers=headers).status_code == 422
        assert client.put(path, json={**payload, "patient_id": "123456789"}, headers=headers).status_code == 422


def test_reserved_visit_cannot_change_finalized_context(doctor_access, active_case_lease):
    with TestClient(app) as client:
        visit = reserve(client)
        headers = lease_headers(client, visit["study_id"], active_case_lease)
        with SessionLocal() as db:
            study = db.get(StudyModel, visit["study_id"])
            study.status = "REVIEWED"
            db.commit()
        response = client.put(f"/api/cases/{visit['study_id']}/intake-sides",
                              json={"active_ovary_side": "BOTH"}, headers=headers)
        assert response.status_code == 409, response.text


def test_reserved_visit_cannot_reassign_sides_after_images(doctor_access, active_case_lease):
    with TestClient(app) as client:
        visit = reserve(client)
        headers = lease_headers(client, visit["study_id"], active_case_lease)
        with SessionLocal() as db:
            create_test_image(db, visit["study_id"])
        response = client.put(f"/api/cases/{visit['study_id']}/intake-sides",
                              json={"active_ovary_side": "BOTH"}, headers=headers)
        assert response.status_code == 409, response.text
