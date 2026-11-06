import os
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-chars-long-12345")

import uuid
from datetime import datetime, UTC
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import create_access_token, hash_password
from backend.db.database import (
    AuditLogModel,
    CorrectionRequestModel,
    FacilityModel,
    ImageModel,
    NotificationModel,
    SessionLocal,
    StudyModel,
    UserModel,
)


@pytest.fixture
def correction_env():
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

    doc_a = UserModel(
        id=f"doc-a-{prefix}",
        username=f"doctor_a_{prefix}",
        full_name="Dr. Alpha",
        role="DOCTOR",
        facility_id=fac_a.id,
        password_hash=pwd_hash,
        is_active=True,
    )
    tech_a = UserModel(
        id=f"tech-a-{prefix}",
        username=f"tech_a_{prefix}",
        full_name="Technician Alpha",
        role="SENIOR",
        facility_id=fac_a.id,
        password_hash=pwd_hash,
        is_active=True,
    )
    tech_b = UserModel(
        id=f"tech-b-{prefix}",
        username=f"tech_b_{prefix}",
        full_name="Technician Beta",
        role="SENIOR",
        facility_id=fac_b.id,
        password_hash=pwd_hash,
        is_active=True,
    )
    other_tech_a = UserModel(
        id=f"other-tech-a-{prefix}",
        username=f"other_tech_a_{prefix}",
        full_name="Other Technician Alpha",
        role="SENIOR",
        facility_id=fac_a.id,
        password_hash=pwd_hash,
        is_active=True,
    )
    test_db.add_all([doc_a, tech_a, tech_b, other_tech_a])
    test_db.commit()

    token_doc_a = create_access_token({"sub": doc_a.username, "role": "DOCTOR", "facility_id": fac_a.id})
    token_tech_a = create_access_token({"sub": tech_a.username, "role": "TECHNICIAN", "facility_id": fac_a.id})
    token_tech_b = create_access_token({"sub": tech_b.username, "role": "TECHNICIAN", "facility_id": fac_b.id})
    token_other_tech_a = create_access_token({"sub": other_tech_a.username, "role": "TECHNICIAN", "facility_id": fac_a.id})

    client = TestClient(app)
    try:
        yield {
            "client": client,
            "fac_a": fac_a,
            "fac_b": fac_b,
            "doc_a": doc_a,
            "tech_a": tech_a,
            "tech_b": tech_b,
            "other_tech_a": other_tech_a,
            "token_doc_a": token_doc_a,
            "token_tech_a": token_tech_a,
            "token_tech_b": token_tech_b,
            "token_other_tech_a": token_other_tech_a,
            "db": test_db,
            "prefix": prefix,
        }
    finally:
        test_db.close()


def test_doctor_creates_correction_request_same_facility(correction_env):
    """Doctor creates correction request for technician in same facility -> 200 OK & notification created."""
    client = correction_env["client"]
    db = correction_env["db"]
    token_doc_a = correction_env["token_doc_a"]
    doc_a = correction_env["doc_a"]
    tech_a = correction_env["tech_a"]
    fac_a = correction_env["fac_a"]
    prefix = correction_env["prefix"]

    study = StudyModel(
        id=f"study-cr-1-{prefix}",
        study_code=f"ST-CR-1-{prefix}",
        study_date="2026-11-01",
        facility_id=fac_a.id,
        status="PENDING",
        assignee_id=doc_a.id,
    )
    db.add(study)
    db.commit()

    resp = client.post(
        f"/api/workspace/cases/{study.id}/corrections",
        headers={"Authorization": f"Bearer {token_doc_a}"},
        json={"technician_id": tech_a.id, "reason": "Cần vẽ lại viền buồng trứng phải do chồng lấn mô mỡ"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["technician_id"] == tech_a.id

    # Verify CorrectionRequestModel record
    corr = db.query(CorrectionRequestModel).filter(CorrectionRequestModel.study_id == study.id).first()
    assert corr is not None
    assert corr.technician_id == tech_a.id
    assert corr.status == "PENDING"

    # Verify NotificationModel created
    notif = db.query(NotificationModel).filter(
        NotificationModel.recipient_id == tech_a.id,
        NotificationModel.study_id == study.id,
        NotificationModel.event_type == "CORRECTION_REQUESTED",
    ).first()
    assert notif is not None
    assert notif.facility_id == fac_a.id
    assert "Cần vẽ lại" in notif.message

    audit = db.query(AuditLogModel).filter(
        AuditLogModel.entity_name == "correction_request",
        AuditLogModel.entity_id == corr.id,
        AuditLogModel.action_type == "CORRECTION_REQUESTED",
    ).first()
    assert audit is not None
    assert audit.actor_id == doc_a.id
    assert audit.details["technician_id"] == tech_a.id

    repeated = client.post(
        f"/api/workspace/cases/{study.id}/corrections",
        headers={"Authorization": f"Bearer {token_doc_a}"},
        json={"technician_id": tech_a.id, "reason": "Lặp yêu cầu"},
    )
    assert repeated.status_code == 409, repeated.text
    assert db.query(NotificationModel).filter(
        NotificationModel.recipient_id == tech_a.id,
        NotificationModel.study_id == study.id,
        NotificationModel.event_type == "CORRECTION_REQUESTED",
    ).count() == 1


def test_doctor_creates_correction_different_facility_forbidden(correction_env):
    """Doctor cannot assign correction to a technician from another facility."""
    client = correction_env["client"]
    db = correction_env["db"]
    token_doc_a = correction_env["token_doc_a"]
    doc_a = correction_env["doc_a"]
    tech_b = correction_env["tech_b"]
    fac_a = correction_env["fac_a"]
    prefix = correction_env["prefix"]

    study = StudyModel(
        id=f"study-cr-2-{prefix}",
        study_code=f"ST-CR-2-{prefix}",
        study_date="2026-11-01",
        facility_id=fac_a.id,
        status="PENDING",
        assignee_id=doc_a.id,
    )
    db.add(study)
    db.commit()

    resp = client.post(
        f"/api/workspace/cases/{study.id}/corrections",
        headers={"Authorization": f"Bearer {token_doc_a}"},
        json={"technician_id": tech_b.id, "reason": "Cross-facility assignment"},
    )
    assert resp.status_code == 403, resp.text


def test_technician_saves_draft_correction(correction_env):
    """Assigned technician saves draft correction -> 200 OK, draft saved, status SUBMITTED."""
    client = correction_env["client"]
    db = correction_env["db"]
    token_tech_a = correction_env["token_tech_a"]
    token_other_tech_a = correction_env["token_other_tech_a"]
    doc_a = correction_env["doc_a"]
    tech_a = correction_env["tech_a"]
    fac_a = correction_env["fac_a"]
    prefix = correction_env["prefix"]

    study = StudyModel(
        id=f"study-cr-3-{prefix}",
        study_code=f"ST-CR-3-{prefix}",
        study_date="2026-11-01",
        facility_id=fac_a.id,
        status="PENDING",
        review_revision=0,
    )
    images = [
        ImageModel(
            id=f"image-cr-{index}-{prefix}",
            study_id=study.id,
            filename=f"case-{index}.png",
            raw_path=f"/tmp/case-{index}.png",
            laterality=side,
        )
        for index, side in enumerate(("L", "R"), start=1)
    ]
    db.add(study)
    db.commit()
    corr = CorrectionRequestModel(
        id=f"corr-3-{prefix}",
        study_id=study.id,
        review_revision=0,
        reason="Chỉnh sửa viền",
        doctor_id=doc_a.id,
        technician_id=tech_a.id,
        status="PENDING",
        created_at=datetime.now(UTC),
    )
    db.add_all([corr, *images])
    db.commit()

    # 1. Other technician tries to save -> 403 Forbidden
    rle = {"shape": [512, 512], "first_val": 0, "counts": [262144]}
    draft_images = [
        {"image_id": image.id, "verified_mask_rle": rle, "notes": "Unauthorized edit", "morphology": ""}
        for image in images
    ]
    resp_other = client.put(
        f"/api/workspace/cases/{study.id}/corrections",
        headers={"Authorization": f"Bearer {token_other_tech_a}"},
        json={
            "correction_id": corr.id,
            "base_revision": 0,
            "lease_token": "x" * 40,
            "page_instance_id": "correction-page-0001",
            "draft_payload": {"images": draft_images},
        },
    )
    assert resp_other.status_code == 403, resp_other.text

    lease_response = client.post(
        f"/api/workspace/cases/{study.id}/lease",
        headers={"Authorization": f"Bearer {token_tech_a}"},
        json={"tab_id": "correction-tab-0001", "page_instance_id": "correction-page-0001"},
    )
    assert lease_response.status_code == 200, lease_response.text
    lease = lease_response.json()
    assert lease["granted"] is True

    detail = client.get(
        f"/api/cases/{study.id}",
        headers={"Authorization": f"Bearer {token_tech_a}"},
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["correction_by"] == tech_a.id

    denied_detail = client.get(
        f"/api/cases/{study.id}",
        headers={"Authorization": f"Bearer {token_other_tech_a}"},
    )
    assert denied_detail.status_code == 403, denied_detail.text

    draft_images = [
        {"image_id": image.id, "verified_mask_rle": rle, "notes": "Updated note", "morphology": ""}
        for image in images
    ]

    invalid_lease = client.put(
        f"/api/workspace/cases/{study.id}/corrections",
        headers={"Authorization": f"Bearer {token_tech_a}"},
        json={
            "correction_id": corr.id,
            "base_revision": 0,
            "lease_token": "z" * 40,
            "page_instance_id": "correction-page-0001",
            "draft_payload": {"images": draft_images},
        },
    )
    assert invalid_lease.status_code == 423, invalid_lease.text

    stale_revision = client.put(
        f"/api/workspace/cases/{study.id}/corrections",
        headers={"Authorization": f"Bearer {token_tech_a}"},
        json={
            "correction_id": corr.id,
            "base_revision": 1,
            "lease_token": lease["lease_token"],
            "page_instance_id": "correction-page-0001",
            "draft_payload": {"images": draft_images},
        },
    )
    assert stale_revision.status_code == 409, stale_revision.text

    # 2. Assigned technician saves draft -> 200 OK
    resp = client.put(
        f"/api/workspace/cases/{study.id}/corrections",
        headers={"Authorization": f"Bearer {token_tech_a}"},
        json={
            "correction_id": corr.id,
            "base_revision": 0,
            "lease_token": lease["lease_token"],
            "page_instance_id": "correction-page-0001",
            "draft_payload": {"images": draft_images},
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "SUBMITTED"

    db.refresh(corr)
    assert corr.status == "SUBMITTED"
    assert corr.draft_payload["images"][0]["image_id"] in {image.id for image in images}

    db.refresh(study)
    assert study.review_revision == 1, "Review revision must be incremented"
    assert study.status == "PENDING", "Technician correction submission must not finalize physician review"
    assert study.status not in {"REVIEWED", "SIGNED_PRELIM", "APPROVED", "LOCKED"}

    audit_sub = db.query(AuditLogModel).filter(
        AuditLogModel.entity_name == "correction_request",
        AuditLogModel.entity_id == corr.id,
        AuditLogModel.action_type == "CORRECTION_SUBMITTED",
    ).first()
    assert audit_sub is not None
    assert audit_sub.actor_id == tech_a.id
    assert audit_sub.details["study_id"] == study.id

    submitted_detail = client.get(
        f"/api/cases/{study.id}",
        headers={"Authorization": f"Bearer {correction_env['token_doc_a']}"},
    )
    assert submitted_detail.status_code == 200, submitted_detail.text
    assert submitted_detail.json()["correction_status"] == "SUBMITTED"
    assert len(submitted_detail.json()["correction_draft"]["images"]) == 2

    technician_after_submit = client.get(
        f"/api/cases/{study.id}",
        headers={"Authorization": f"Bearer {token_tech_a}"},
    )
    assert technician_after_submit.status_code == 403

    duplicate_open_request = client.post(
        f"/api/workspace/cases/{study.id}/corrections",
        headers={"Authorization": f"Bearer {correction_env['token_doc_a']}"},
        json={"technician_id": tech_a.id, "reason": "Chưa bác sĩ rà soát yêu cầu trước"},
    )
    assert duplicate_open_request.status_code == 409


def test_technician_blocked_from_clinical_actions(correction_env):
    """Technician cannot access clinical-only endpoints (e.g. creating cases, leases)."""
    client = correction_env["client"]
    token_tech_a = correction_env["token_tech_a"]

    # Technician attempts to create a clinical case
    resp = client.post(
        "/api/cases",
        headers={"Authorization": f"Bearer {token_tech_a}", "Idempotency-Key": str(uuid.uuid4())},
        json={"study_date": "2026-11-01", "active_ovary_side": "RIGHT"},
    )
    assert resp.status_code == 403, "Technician must not be allowed to perform clinical case creation"
