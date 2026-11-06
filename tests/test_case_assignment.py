import os
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-chars-long-12345")

import uuid
from datetime import datetime, UTC, timedelta
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import create_access_token, hash_password
from backend.db.database import (
    CaseLeaseModel,
    FacilityModel,
    NotificationModel,
    SessionLocal,
    StudyModel,
    UserModel,
)


@pytest.fixture
def assignment_env():
    prefix = uuid.uuid4().hex[:8]
    test_db = SessionLocal()

    fac_a = FacilityModel(
        id=f"FAC-A-{prefix}",
        name=f"Facility Alpha {prefix}",
        facility_code=f"FA-{prefix}",
        is_active=True,
    )
    fac_b = FacilityModel(
        id=f"FAC-B-{prefix}",
        name=f"Facility Beta {prefix}",
        facility_code=f"FB-{prefix}",
        is_active=True,
    )
    test_db.add_all([fac_a, fac_b])
    test_db.commit()

    pwd_hash = hash_password("SecurePass123!")

    doc_a1 = UserModel(
        id=f"doc-a1-{prefix}",
        username=f"doctor_a1_{prefix}",
        full_name="Dr. Alpha One",
        role="DOCTOR",
        facility_id=fac_a.id,
        password_hash=pwd_hash,
        is_active=True,
    )
    doc_a2 = UserModel(
        id=f"doc-a2-{prefix}",
        username=f"doctor_a2_{prefix}",
        full_name="Dr. Alpha Two",
        role="DOCTOR",
        facility_id=fac_a.id,
        password_hash=pwd_hash,
        is_active=True,
    )
    doc_b = UserModel(
        id=f"doc-b-{prefix}",
        username=f"doctor_b_{prefix}",
        full_name="Dr. Beta",
        role="DOCTOR",
        facility_id=fac_b.id,
        password_hash=pwd_hash,
        is_active=True,
    )
    admin_fac_a = UserModel(
        id=f"admin-a-{prefix}",
        username=f"admin_a_{prefix}",
        full_name="Admin Alpha",
        role="ADMIN",
        facility_id=fac_a.id,
        password_hash=pwd_hash,
        is_active=True,
    )
    admin_global = UserModel(
        id=f"admin-global-{prefix}",
        username=f"admin_global_{prefix}",
        full_name="Global Administrator",
        role="ADMIN",
        facility_id=None,
        password_hash=pwd_hash,
        is_active=True,
    )
    test_db.add_all([doc_a1, doc_a2, doc_b, admin_fac_a, admin_global])
    test_db.commit()

    token_doc_a1 = create_access_token({"sub": doc_a1.username, "role": "DOCTOR", "facility_id": fac_a.id})
    token_doc_a2 = create_access_token({"sub": doc_a2.username, "role": "DOCTOR", "facility_id": fac_a.id})
    token_doc_b = create_access_token({"sub": doc_b.username, "role": "DOCTOR", "facility_id": fac_b.id})
    token_admin_a = create_access_token({"sub": admin_fac_a.username, "role": "ADMIN", "facility_id": fac_a.id})
    token_admin_global = create_access_token({"sub": admin_global.username, "role": "ADMIN", "facility_id": None})

    client = TestClient(app)
    try:
        yield {
            "client": client,
            "fac_a": fac_a,
            "fac_b": fac_b,
            "doc_a1": doc_a1,
            "doc_a2": doc_a2,
            "doc_b": doc_b,
            "admin_fac_a": admin_fac_a,
            "admin_global": admin_global,
            "token_doc_a1": token_doc_a1,
            "token_doc_a2": token_doc_a2,
            "token_doc_b": token_doc_b,
            "token_admin_a": token_admin_a,
            "token_admin_global": token_admin_global,
            "db": test_db,
            "prefix": prefix,
        }
    finally:
        test_db.close()


def test_admin_assign_doctor_in_same_facility(assignment_env):
    """Facility admin assigns a doctor within the same facility -> 200 OK & notification created."""
    client = assignment_env["client"]
    db = assignment_env["db"]
    token_admin_a = assignment_env["token_admin_a"]
    doc_a1 = assignment_env["doc_a1"]
    fac_a = assignment_env["fac_a"]
    prefix = assignment_env["prefix"]

    study = StudyModel(
        id=f"study-as-1-{prefix}",
        study_code=f"ST-AS-1-{prefix}",
        study_date="2026-11-01",
        facility_id=fac_a.id,
        status="PENDING",
    )
    db.add(study)
    db.commit()

    resp = client.post(
        f"/api/workspace/cases/{study.id}/assign",
        headers={"Authorization": f"Bearer {token_admin_a}"},
        json={"assignee_id": doc_a1.id},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["assignee_id"] == doc_a1.id

    # Verify DB update
    db.refresh(study)
    assert study.assignee_id == doc_a1.id

    # Verify notification created
    notif = db.query(NotificationModel).filter(
        NotificationModel.recipient_id == doc_a1.id,
        NotificationModel.study_id == study.id,
        NotificationModel.event_type == "CASE_ASSIGNED",
    ).first()
    assert notif is not None
    assert notif.facility_id == fac_a.id
    assert notif.is_read is False


def test_assignment_rejects_inactive_or_non_doctor_and_deduplicates_noop(assignment_env):
    client = assignment_env["client"]
    db = assignment_env["db"]
    token_admin = assignment_env["token_admin_a"]
    fac = assignment_env["fac_a"]
    doctor = assignment_env["doc_a1"]
    prefix = assignment_env["prefix"]
    study = StudyModel(
        id=f"study-as-hardening-{prefix}",
        study_code=f"ST-AS-H-{prefix}",
        study_date="2026-11-01",
        facility_id=fac.id,
        status="PENDING",
    )
    inactive = UserModel(
        id=f"inactive-doctor-{prefix}",
        username=f"inactive_doctor_{prefix}",
        full_name="Inactive Doctor",
        role="DOCTOR",
        facility_id=fac.id,
        is_active=False,
    )
    technician = UserModel(
        id=f"technician-{prefix}",
        username=f"technician_{prefix}",
        full_name="Technician",
        role="SENIOR",
        facility_id=fac.id,
        is_active=True,
    )
    db.add_all([study, inactive, technician])
    db.commit()

    for target in (inactive, technician):
        response = client.post(
            f"/api/workspace/cases/{study.id}/assign",
            headers={"Authorization": f"Bearer {token_admin}"},
            json={"assignee_id": target.id},
        )
        assert response.status_code == 422, response.text

    for _ in range(2):
        response = client.post(
            f"/api/workspace/cases/{study.id}/assign",
            headers={"Authorization": f"Bearer {token_admin}"},
            json={"assignee_id": doctor.id},
        )
        assert response.status_code == 200, response.text
    assert db.query(NotificationModel).filter(
        NotificationModel.study_id == study.id,
        NotificationModel.event_type == "CASE_ASSIGNED",
    ).count() == 1


def test_admin_assign_doctor_different_facility_forbidden(assignment_env):
    """Facility admin A cannot assign a doctor from facility B."""
    client = assignment_env["client"]
    db = assignment_env["db"]
    token_admin_a = assignment_env["token_admin_a"]
    doc_b = assignment_env["doc_b"]
    fac_a = assignment_env["fac_a"]
    prefix = assignment_env["prefix"]

    study = StudyModel(
        id=f"study-as-2-{prefix}",
        study_code=f"ST-AS-2-{prefix}",
        study_date="2026-11-01",
        facility_id=fac_a.id,
        status="PENDING",
    )
    db.add(study)
    db.commit()

    resp = client.post(
        f"/api/workspace/cases/{study.id}/assign",
        headers={"Authorization": f"Bearer {token_admin_a}"},
        json={"assignee_id": doc_b.id},
    )
    assert resp.status_code == 403, resp.text


def test_admin_assign_active_lease_conflict_409(assignment_env):
    """Reassigning while an active lease is held returns 409 Conflict without revoking the lease."""
    client = assignment_env["client"]
    db = assignment_env["db"]
    token_admin_a = assignment_env["token_admin_a"]
    doc_a1 = assignment_env["doc_a1"]
    doc_a2 = assignment_env["doc_a2"]
    fac_a = assignment_env["fac_a"]
    prefix = assignment_env["prefix"]

    study = StudyModel(
        id=f"study-as-3-{prefix}",
        study_code=f"ST-AS-3-{prefix}",
        study_date="2026-11-01",
        facility_id=fac_a.id,
        status="PENDING",
        assignee_id=doc_a1.id,
    )
    db.add(study)
    db.commit()

    active_lease = CaseLeaseModel(
        study_id=study.id,
        owner_user_id=doc_a1.id,
        tab_id="tab-1",
        page_instance_id="page-inst-1",
        token_hash="token-hash-12345",
        acquired_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    db.add(active_lease)
    db.commit()

    resp = client.post(
        f"/api/workspace/cases/{study.id}/assign",
        headers={"Authorization": f"Bearer {token_admin_a}"},
        json={"assignee_id": doc_a2.id},
    )
    assert resp.status_code == 409, resp.text

    # Lease must still be intact
    lease_in_db = db.query(CaseLeaseModel).filter(CaseLeaseModel.study_id == study.id).first()
    assert lease_in_db is not None
    assert lease_in_db.token_hash == "token-hash-12345"


def test_doctor_self_claim_unassigned_case(assignment_env):
    """Doctor self-claims an unassigned case -> 200 OK, no notification to self."""
    client = assignment_env["client"]
    db = assignment_env["db"]
    token_doc_a1 = assignment_env["token_doc_a1"]
    doc_a1 = assignment_env["doc_a1"]
    fac_a = assignment_env["fac_a"]
    prefix = assignment_env["prefix"]

    study = StudyModel(
        id=f"study-cl-1-{prefix}",
        study_code=f"ST-CL-1-{prefix}",
        study_date="2026-11-01",
        facility_id=fac_a.id,
        status="PENDING",
        assignee_id=None,
    )
    db.add(study)
    db.commit()

    resp = client.post(
        f"/api/workspace/cases/{study.id}/claim",
        headers={"Authorization": f"Bearer {token_doc_a1}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "CLAIMED"
    assert data["assignee_id"] == doc_a1.id

    db.refresh(study)
    assert study.assignee_id == doc_a1.id

    # Self-claim must NOT produce a notification for self
    notif = db.query(NotificationModel).filter(
        NotificationModel.recipient_id == doc_a1.id,
        NotificationModel.study_id == study.id,
    ).first()
    assert notif is None, "Self-claim must not generate a notification to oneself"


def test_doctor_claim_already_assigned_case_conflict(assignment_env):
    """Doctor attempting to claim a case that already has an assignee gets 409 Conflict."""
    client = assignment_env["client"]
    db = assignment_env["db"]
    token_doc_a2 = assignment_env["token_doc_a2"]
    doc_a1 = assignment_env["doc_a1"]
    fac_a = assignment_env["fac_a"]
    prefix = assignment_env["prefix"]

    study = StudyModel(
        id=f"study-cl-2-{prefix}",
        study_code=f"ST-CL-2-{prefix}",
        study_date="2026-11-01",
        facility_id=fac_a.id,
        status="PENDING",
        assignee_id=doc_a1.id,
    )
    db.add(study)
    db.commit()

    resp = client.post(
        f"/api/workspace/cases/{study.id}/claim",
        headers={"Authorization": f"Bearer {token_doc_a2}"},
    )
    assert resp.status_code == 409, resp.text
