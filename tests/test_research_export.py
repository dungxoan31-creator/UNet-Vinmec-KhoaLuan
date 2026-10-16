"""
Unit and integration tests for research ZIP export bundle (Task 11).
"""

import io
import json
import os
import uuid
import zipfile
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


def test_export_pins_review_prediction(auth_tokens, case_with_multiple_predictions):
    from backend.app.main import app
    client = TestClient(app)
    c = case_with_multiple_predictions
    payload = {
        "review_ids": [c["review_id"]],
        "expected_revision": 1,
    }
    resp = client.post(f"/api/cases/{c['study_id']}/research-export", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"

    # Inspect zip contents
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        namelist = zf.namelist()
        assert "metadata.json" in namelist
        ai_mask_path = f"{c['image_id']}/ai_mask.png"
        rev_mask_path = f"{c['image_id']}/reviewed_mask.png"
        overlay_path = f"{c['image_id']}/overlay.png"
        assert ai_mask_path in namelist
        assert rev_mask_path in namelist
        assert overlay_path in namelist

        # Decode ai_mask.png from zip: it MUST match P1, NOT P2!
        ai_mask_bytes = zf.read(ai_mask_path)
        ai_mask_np = cv2.imdecode(np.frombuffer(ai_mask_bytes, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        ai_binary = (ai_mask_np > 0).astype(np.uint8)

        # Compare with P1 and P2 source
        assert ai_mask_np.shape == (300, 400)
        assert ai_mask_np[90, 90] == 255 and ai_mask_np[185, 185] == 0, "Exported AI mask must strictly match reviewed prediction P1"


def test_bundle_requires_persisted_review(auth_tokens, case_with_multiple_predictions):
    from backend.app.main import app
    client = TestClient(app)
    c = case_with_multiple_predictions
    payload = {
        "review_ids": [str(uuid.uuid4())],  # non-existent review
        "expected_revision": 1,
    }
    resp = client.post(f"/api/cases/{c['study_id']}/research-export", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code in (404, 422)


def test_export_rejects_cross_case_ids(auth_tokens, case_with_multiple_predictions):
    from backend.db import database
    from backend.app.main import app
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

    # Pass review_id of study 1 to other_study -> 422
    payload = {
        "review_ids": [c["review_id"]],
        "expected_revision": 1,
    }
    resp = client.post(f"/api/cases/{other_study_id}/research-export", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code in (404, 422)


def test_export_auth_and_no_phi(auth_tokens, case_with_multiple_predictions):
    from backend.app.main import app
    client = TestClient(app)
    c = case_with_multiple_predictions
    payload = {
        "review_ids": [c["review_id"]],
        "expected_revision": 1,
    }
    # Unauthenticated -> 401
    resp_unauth = client.post(f"/api/cases/{c['study_id']}/research-export", json=payload)
    assert resp_unauth.status_code == 401

    # Authenticated doctor -> 200
    resp = client.post(f"/api/cases/{c['study_id']}/research-export", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 200

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        metadata = json.loads(zf.read("metadata.json").decode("utf-8"))
        raw_text = json.dumps(metadata)

        # PHI & Secret checks:
        assert "TEST_PATIENT_SECRET_PHI" not in raw_text, "Patient identity or confidential info must not be in export"
        assert "Bearer" not in raw_text
        assert "password" not in raw_text.lower()
        assert "Users" not in raw_text and "AppData" not in raw_text, "Server local filesystem paths must not leak"
        assert metadata["disclaimer"]


def test_native_shapes_and_mask_hashes(auth_tokens, case_with_multiple_predictions):
    import hashlib
    from backend.app.main import app
    client = TestClient(app)
    c = case_with_multiple_predictions
    payload = {
        "review_ids": [c["review_id"]],
        "expected_revision": 1,
    }
    resp = client.post(f"/api/cases/{c['study_id']}/research-export", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 200

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        metadata = json.loads(zf.read("metadata.json").decode("utf-8"))
        img_meta = metadata["images"][0]
        assert img_meta["geometry"]["native_shape"] == [300, 400]
        assert img_meta["physical_units"] is None

        for key, file_info in img_meta["files"].items():
            path_in_zip = file_info["path"]
            assert path_in_zip in zf.namelist()
            content = zf.read(path_in_zip)
            actual_sha = hashlib.sha256(content).hexdigest()
            assert actual_sha == file_info["sha256"], f"Hash mismatch for {key}: expected {file_info['sha256']}, got {actual_sha}"


def test_stale_export_revision(auth_tokens, case_with_multiple_predictions):
    from backend.app.main import app
    client = TestClient(app)
    c = case_with_multiple_predictions
    # Stale revision (expected 5, study is 1) -> 409
    payload = {
        "review_ids": [c["review_id"]],
        "expected_revision": 5,
    }
    resp = client.post(f"/api/cases/{c['study_id']}/research-export", json=payload, headers=auth_tokens["doctor"])
    assert resp.status_code == 409


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

