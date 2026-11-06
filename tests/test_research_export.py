"""
Unit and integration tests for research ZIP export bundle (Task 11).
"""

import os
import uuid

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")


@pytest.fixture
def auth_tokens():
    from backend.app.routers.auth import create_access_token
    doc_token = create_access_token({"sub": "doctor"})
    admin_token = create_access_token({"sub": "admin"})
    return {
        "doctor": {"Authorization": f"Bearer {doc_token}"},
        "admin": {"Authorization": f"Bearer {admin_token}"},
    }


@pytest.fixture
def case_with_multiple_predictions(tmp_path):
    from backend.db import database
    from backend.services.inference_engine import InferenceEngine
    from backend.services.preprocessor import UltrasoundPreprocessor

    # Create dummy source images on disk
    src_img = np.zeros((300, 400, 3), dtype=np.uint8)
    src_img[50:250, 50:350] = 120
    img_path = tmp_path / "img_source.png"
    cv2.imwrite(str(img_path), src_img)

    prep = UltrasoundPreprocessor(target_size=(512, 512))

    # Mask 1 (P1 - reviewed)
    mask1_source = np.zeros((300, 400), dtype=np.uint8)
    mask1_source[60:120, 60:120] = 1
    m1_512, _ = prep.letterbox_resize(mask1_source, is_mask=True)
    rle1 = InferenceEngine.mask_to_rle(m1_512)

    # Mask 2 (P2 - newer prediction generated later)
    mask2_source = np.zeros((300, 400), dtype=np.uint8)
    mask2_source[150:220, 150:220] = 1
    m2_512, _ = prep.letterbox_resize(mask2_source, is_mask=True)
    rle2 = InferenceEngine.mask_to_rle(m2_512)

    # Reviewed mask (modified P1)
    mask_rev_source = np.zeros((300, 400), dtype=np.uint8)
    mask_rev_source[60:130, 60:130] = 1
    mrev_512, _ = prep.letterbox_resize(mask_rev_source, is_mask=True)
    rle_rev = InferenceEngine.mask_to_rle(mrev_512)

    db = next(database.get_db())
    try:
        patient = database.PatientModel(
            id=str(uuid.uuid4()),
            anonymized_pid=f"TEST_PATIENT_SECRET_PHI_{uuid.uuid4().hex[:8]}",
        )
        db.add(patient)
        study = database.StudyModel(
            id=str(uuid.uuid4()),
            patient_id=patient.id,
            study_code="STUDY_EXP_001",
            study_date="2026-10-16",
            status="REVIEWED",
            ovary_side="RIGHT",
            review_revision=1,
        )
        db.add(study)

        img = database.ImageModel(
            id=str(uuid.uuid4()),
            study_id=study.id,
            filename="img_source.png",
            laterality="R",
            raw_path=str(img_path),
            width=400,
            height=300,
            pixel_spacing_mm=None,  # uncalibrated
        )
        db.add(img)

        # P1
        pred1 = database.PredictionModel(
            id=str(uuid.uuid4()),
            image_id=img.id,
            model_version="AttentionUNet-v1.2",
            raw_mask_rle=rle1,
            measurements={},
            provenance_json={
                "checkpoint_sha256": "aaaa1111" * 8,
                "architecture": "Attention U-Net",
                "threshold": 0.5,
            },
        )
        db.add(pred1)

        # Review linked strictly to P1
        review = database.ReviewModel(
            id=str(uuid.uuid4()),
            image_id=img.id,
            prediction_id=pred1.id,
            doctor_id="doctor",
            doctor_action="MODIFIED",
            verified_mask_rle=rle_rev,
            max_diameter_mm=None,
            ortho_diameter_mm=None,
            total_area_cm2=None,
            lesion_type="U nang đơn thùy",
            clinical_notes="Ghi chú nghiên cứu",
            is_official_ground_truth=False,
        )
        db.add(review)

        # P2 added after review (latest in DB)
        pred2 = database.PredictionModel(
            id=str(uuid.uuid4()),
            image_id=img.id,
            model_version="AttentionUNet-v1.3",
            raw_mask_rle=rle2,
            measurements={},
            provenance_json={
                "checkpoint_sha256": "bbbb2222" * 8,
                "architecture": "Attention U-Net v2",
                "threshold": 0.5,
            },
        )
        db.add(pred2)
        db.commit()

        return {
            "study_id": study.id,
            "image_id": img.id,
            "pred1_id": pred1.id,
            "pred2_id": pred2.id,
            "review_id": review.id,
            "source_shape": (300, 400),
            "m1_source": mask1_source,
            "m2_source": mask2_source,
            "mrev_source": mask_rev_source,
        }
    finally:
        db.close()


def test_research_export_is_disabled_even_for_self_attested_request(auth_tokens, case_with_multiple_predictions):
    from backend.app.main import app
    client = TestClient(app)
    c = case_with_multiple_predictions
    payload = {
        "review_ids": [c["review_id"]],
        "expected_revision": 1,
        "ethics_approval_code": "UNVERIFIED-USER-INPUT",
        "patient_consent_confirmed": True,
    }
    resp = client.post(f"/api/cases/{c['study_id']}/research-export", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 501
    assert "disabled" in resp.json()["detail"]


def test_disabled_export_does_not_query_review_ids(auth_tokens, case_with_multiple_predictions):
    from backend.app.main import app
    client = TestClient(app)
    c = case_with_multiple_predictions
    payload = {
        "review_ids": [str(uuid.uuid4())],  # non-existent review
        "expected_revision": 1,
        "ethics_approval_code": "UNVERIFIED-USER-INPUT",
        "patient_consent_confirmed": True,
    }
    resp = client.post(f"/api/cases/{c['study_id']}/research-export", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 501


def test_disabled_export_ignores_caller_supplied_case_ids(auth_tokens, case_with_multiple_predictions):
    from backend.app.main import app
    from backend.db import database
    client = TestClient(app)
    c = case_with_multiple_predictions

    # Create another study
    db = next(database.get_db())
    try:
        other_patient = database.PatientModel(id=str(uuid.uuid4()), anonymized_pid=f"OTHER_PID_{uuid.uuid4().hex[:8]}")
        db.add(other_patient)
        other_study = database.StudyModel(
            id=str(uuid.uuid4()), patient_id=other_patient.id, study_date="2026-10-16", review_revision=1
        )
        db.add(other_study)
        db.commit()
        other_study_id = other_study.id
    finally:
        db.close()

    # Export remains unavailable regardless of caller-supplied study and review identifiers.
    payload = {
        "review_ids": [c["review_id"]],
        "expected_revision": 1,
        "ethics_approval_code": "UNVERIFIED-USER-INPUT",
        "patient_consent_confirmed": True,
    }
    resp = client.post(f"/api/cases/{other_study_id}/research-export", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 501


def test_export_requires_authentication_and_remains_disabled(auth_tokens, case_with_multiple_predictions):
    from backend.app.main import app
    client = TestClient(app)
    c = case_with_multiple_predictions
    payload = {
        "review_ids": [c["review_id"]],
        "expected_revision": 1,
        "ethics_approval_code": "UNVERIFIED-USER-INPUT",
        "patient_consent_confirmed": True,
    }
    # Unauthenticated -> 401
    resp_unauth = client.post(f"/api/cases/{c['study_id']}/research-export", json=payload)
    assert resp_unauth.status_code == 401

    # An authenticated doctor still cannot export without trusted authorization records.
    resp = client.post(f"/api/cases/{c['study_id']}/research-export", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 501
    assert resp.headers["content-type"].startswith("application/json")


def test_disabled_export_returns_no_bundle(auth_tokens, case_with_multiple_predictions):
    from backend.app.main import app
    client = TestClient(app)
    c = case_with_multiple_predictions
    payload = {
        "review_ids": [c["review_id"]],
        "expected_revision": 1,
        "ethics_approval_code": "UNVERIFIED-USER-INPUT",
        "patient_consent_confirmed": True,
    }
    resp = client.post(f"/api/cases/{c['study_id']}/research-export", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 501
    assert not resp.content.startswith(b"PK")


def test_disabled_export_does_not_disclose_revision_state(auth_tokens, case_with_multiple_predictions):
    from backend.app.main import app
    client = TestClient(app)
    c = case_with_multiple_predictions
    # The disabled service responds before looking up study or review state.
    payload = {
        "review_ids": [c["review_id"]],
        "expected_revision": 5,
        "ethics_approval_code": "UNVERIFIED-USER-INPUT",
        "patient_consent_confirmed": True,
    }
    resp = client.post(f"/api/cases/{c['study_id']}/research-export", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 501


def test_export_mask_explicit_pinned_ids(auth_tokens, case_with_multiple_predictions):
    from backend.app.main import app
    client = TestClient(app)
    c = case_with_multiple_predictions

    # 1. Export AI mask pinning P1
    resp_p1 = client.get(f"/api/images/{c['image_id']}/mask.png?kind=ai&prediction_id={c['pred1_id']}", headers=auth_tokens["doctor"])
    assert resp_p1.status_code == 200
    p1_mask = cv2.imdecode(np.frombuffer(resp_p1.content, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    assert p1_mask[90, 90] == 255 and p1_mask[185, 185] == 0

    # 2. Export AI mask pinning P2
    resp_p2 = client.get(f"/api/images/{c['image_id']}/mask.png?kind=ai&prediction_id={c['pred2_id']}", headers=auth_tokens["doctor"])
    assert resp_p2.status_code == 200
    p2_mask = cv2.imdecode(np.frombuffer(resp_p2.content, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    assert p2_mask[185, 185] == 255 and p2_mask[90, 90] == 0

    # 3. Export reviewed mask pinning review_id
    resp_rev = client.get(f"/api/images/{c['image_id']}/mask.png?kind=reviewed&review_id={c['review_id']}", headers=auth_tokens["doctor"])
    assert resp_rev.status_code == 200
    rev_mask = cv2.imdecode(np.frombuffer(resp_rev.content, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    assert rev_mask[90, 90] == 255 and rev_mask[185, 185] == 0


def test_export_mask_mismatched_kind_or_id_422(auth_tokens, case_with_multiple_predictions):
    from backend.app.main import app
    client = TestClient(app)
    c = case_with_multiple_predictions

    # passing review_id when kind=ai -> 422
    resp1 = client.get(f"/api/images/{c['image_id']}/mask.png?kind=ai&review_id={c['review_id']}", headers=auth_tokens["doctor"])
    assert resp1.status_code == 422

    # passing prediction_id when kind=reviewed -> 422
    resp2 = client.get(f"/api/images/{c['image_id']}/mask.png?kind=reviewed&prediction_id={c['pred1_id']}", headers=auth_tokens["doctor"])
    assert resp2.status_code == 422

