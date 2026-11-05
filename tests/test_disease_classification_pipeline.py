"""
Tests for the integrated Image, Mask, and Disease Classification pipeline.
Verifies ResNet-34 8-class MMOTU pathology inference, mask integration, and DiagnosticReasoningEngine.
"""

import sys
import numpy as np
import pytest

from ai_training.mmotu_label_schema import MMOTU_8_CLASSES


def test_disease_classifier_service_initialization():
    """Verify DiseaseClassifierService discovers checkpoint and initializes properly."""
    from backend.services.disease_classifier import DiseaseClassifierService

    service = DiseaseClassifierService()
    service.predict_disease(np.full((32, 32), 80, dtype=np.uint8))
    assert service.is_loaded is True
    assert service.device is not None
    assert len(service.class_names) == 8
    assert service.class_names == list(MMOTU_8_CLASSES)


def test_predict_disease_with_dummy_image():
    """Verify disease prediction on a synthetic 3-channel ultrasound image."""
    from backend.services.disease_classifier import DiseaseClassifierService

    service = DiseaseClassifierService()
    dummy_img = np.random.randint(0, 256, (256, 256, 3), dtype=np.uint8)

    result = service.predict_disease(dummy_img)

    assert isinstance(result, dict)
    assert "status" in result
    assert result["status"] in ("PREDICTED", "ABSTAIN")
    assert "suggested_label" in result
    assert result["suggested_label"] in MMOTU_8_CLASSES if result["status"] == "PREDICTED" else result["suggested_label"] is None
    assert "probabilities" in result
    assert len(result["probabilities"]) == 8

    # Sum of probabilities should be approximately 1.0
    total_p = sum(result["probabilities"].values())
    assert pytest.approx(total_p, abs=1e-3) == 1.0

    # Top 3 rankings
    assert "top3" in result
    assert len(result["top3"]) == 3
    assert result["top3"][0][0] in MMOTU_8_CLASSES
    if result["status"] == "PREDICTED":
        assert result["top3"][0][0] == result["suggested_label"]

    # Provenance
    assert "provenance" in result
    assert result["provenance"]["model"] == "MMOTU ResNet34 8-class"
    assert result["provenance"]["checkpoint_sha256"] is not None


def test_predict_disease_with_mask():
    """Verify prediction when a binary segmentation mask is provided."""
    from backend.services.disease_classifier import DiseaseClassifierService

    service = DiseaseClassifierService()
    dummy_img = np.full((300, 400, 3), 40, dtype=np.uint8)
    dummy_mask = np.zeros((300, 400), dtype=np.uint8)

    # Draw a synthetic lesion in the center
    dummy_mask[100:200, 150:250] = 1
    dummy_img[100:200, 150:250] = 180

    result = service.predict_disease(dummy_img, mask=dummy_mask, pixel_spacing_mm=0.1)

    assert result["status"] in ("PREDICTED", "ABSTAIN")
    assert result["suggested_label"] in MMOTU_8_CLASSES if result["status"] == "PREDICTED" else result["suggested_label"] is None
    assert "mask_measurements" in result
    assert result["mask_measurements"] is not None
    assert result["mask_measurements"]["lesion_detected"] is True
    assert result["mask_measurements"]["area_px"] > 0


def test_predict_disease_empty_mask_fallback():
    """Verify prediction gracefully falls back to full image if mask has 0 pixels."""
    from backend.services.disease_classifier import DiseaseClassifierService

    service = DiseaseClassifierService()
    dummy_img = np.random.randint(20, 200, (256, 256, 3), dtype=np.uint8)
    empty_mask = np.zeros((256, 256), dtype=np.uint8)

    result = service.predict_disease(dummy_img, mask=empty_mask)
    assert result["status"] in ("PREDICTED", "ABSTAIN")
    assert result["mask_measurements"]["lesion_detected"] is False


def test_predict_disease_grayscale_input():
    """Verify 2D grayscale image (H, W) is automatically expanded to 3 channels."""
    from backend.services.disease_classifier import DiseaseClassifierService

    service = DiseaseClassifierService()
    gray_img = np.random.randint(0, 256, (200, 200), dtype=np.uint8)

    result = service.predict_disease(gray_img)
    assert result["status"] in ("PREDICTED", "ABSTAIN")
    assert result["suggested_label"] in MMOTU_8_CLASSES if result["status"] == "PREDICTED" else result["suggested_label"] is None


def test_predict_disease_invalid_input_raises_value_error():
    """Verify non-image input or empty dimensions raises ValueError."""
    from backend.services.disease_classifier import DiseaseClassifierService

    service = DiseaseClassifierService()

    with pytest.raises(ValueError, match="Hợp lệ"):
        service.predict_disease(np.zeros((0, 0), dtype=np.uint8))

    with pytest.raises(ValueError, match="Hợp lệ"):
        service.predict_disease("not_an_image")


def test_segmentation_does_not_classify_enhanced_letterboxed_input(monkeypatch):
    """Only the API boundary has the source pixels required by the classifier."""
    from backend.app.config import model_registry
    from backend.services.preprocessor import UltrasoundPreprocessor
    from backend.services.image_classifier import image_classifier

    def forbidden(_image):
        pytest.fail("Segmentation must not run classification on transformed pixels")

    monkeypatch.setattr(image_classifier, "predict", forbidden)

    adapter = model_registry.get_primary_adapter()
    engine = adapter.engine
    engine.forward_probabilities = lambda _tensor: np.zeros((512, 512), dtype=np.float32)
    prep = UltrasoundPreprocessor()
    dummy_img = np.full((512, 512), 60, dtype=np.uint8)
    dummy_img[200:300, 200:300] = 200

    tensor_512, padded_gray, _, _ = prep.preprocess(dummy_img)
    result = engine.predict(tensor_512, padded_gray, generate_overlay=False)

    assert "ai_diagnosis" in result
    assert result["ai_diagnosis"] is None


def test_api_predict_returns_ai_diagnosis(monkeypatch):
    """Verify POST /api/predict/{image_id} returns populated ai_diagnosis in response."""
    import uuid
    import tempfile
    import cv2
    from fastapi.testclient import TestClient
    from backend.app.config import model_registry
    from backend.app.main import app
    from backend.app.security import create_access_token
    from backend.db.database import SessionLocal, FacilityModel, UserModel, StudyModel, ImageModel
    from tests.helpers.synthetic_inference import enable_synthetic_inference

    enable_synthetic_inference(monkeypatch, model_registry)

    monkeypatch.setenv("APP_JWT_SECRET", "synthetic-audit-key-20261101-at-least-32-characters")
    suffix = uuid.uuid4().hex[:8]

    with SessionLocal() as db:
        fac = FacilityModel(id=f"fac-diag-{suffix}", facility_code=f"FD-{suffix}", name="Facility Diag", is_active=True)
        db.add(fac)
        doc = UserModel(
            id=f"doc-diag-{suffix}",
            username=f"doc_diag_{suffix}",
            full_name="Dr. Diag",
            role="DOCTOR",
            facility_id=fac.id,
            is_active=True,
        )
        db.add(doc)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            raw_path = tf.name
            dummy_img = np.random.randint(30, 220, (256, 256), dtype=np.uint8)
            cv2.circle(dummy_img, (128, 128), 50, 180, -1)
            cv2.imwrite(raw_path, dummy_img)

        study = StudyModel(id=f"std-diag-{suffix}", facility_id=fac.id, status="PENDING", study_date="2026-11-02")
        db.add(study)
        img = ImageModel(id=f"img-diag-{suffix}", study_id=study.id, raw_path=raw_path, filename="diag_test.png")
        db.add(img)
        db.commit()

        study_id = study.id
        image_id = img.id
        token = create_access_token({"sub": doc.username, "role": "DOCTOR", "facility_id": fac.id})

    with TestClient(app) as client:
        # Acquire lease first
        lease_resp = client.post(
            f"/api/workspace/cases/{study_id}/lease",
            headers={"Authorization": f"Bearer {token}"},
            json={"tab_id": f"tab-diag-{suffix}-long", "page_instance_id": f"page-diag-{suffix}-long"},
        )
        assert lease_resp.status_code == 200
        lease_data = lease_resp.json()

        # Call predict
        resp = client.post(
            f"/api/predict/{image_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Case-Lease-Token": lease_data["lease_token"],
                "X-Case-Page-Instance-Id": f"page-diag-{suffix}-long",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "ai_diagnosis" in data
        assert data["ai_diagnosis"] is not None
        classification = data["ai_diagnosis"]
        assert classification["suggested_label"] in MMOTU_8_CLASSES if classification["status"] == "PREDICTED" else classification["suggested_label"] is None
        assert data["ai_diagnosis"]["status"] in ("PREDICTED", "ABSTAIN")


def test_api_classify_image_endpoint(monkeypatch):
    """Verify dedicated POST /api/images/{image_id}/classify endpoint."""
    import uuid
    import tempfile
    import cv2
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.security import create_access_token
    from backend.db.database import SessionLocal, FacilityModel, UserModel, StudyModel, ImageModel

    monkeypatch.setenv("APP_JWT_SECRET", "synthetic-audit-key-20261101-at-least-32-characters")
    suffix = uuid.uuid4().hex[:8]

    with SessionLocal() as db:
        fac = FacilityModel(id=f"fac-cls-{suffix}", facility_code=f"FC-{suffix}", name="Facility Cls", is_active=True)
        db.add(fac)
        doc = UserModel(
            id=f"doc-cls-{suffix}",
            username=f"doc_cls_{suffix}",
            full_name="Dr. Cls",
            role="DOCTOR",
            facility_id=fac.id,
            is_active=True,
        )
        db.add(doc)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            raw_path = tf.name
            dummy_img = np.full((128, 128), 70, dtype=np.uint8)
            cv2.imwrite(raw_path, dummy_img)

        study = StudyModel(id=f"std-cls-{suffix}", facility_id=fac.id, status="PENDING", study_date="2026-11-02")
        db.add(study)
        img = ImageModel(id=f"img-cls-{suffix}", study_id=study.id, raw_path=raw_path, filename="cls_test.png")
        db.add(img)
        db.commit()

        study_id = study.id
        image_id = img.id
        token = create_access_token({"sub": doc.username, "role": "DOCTOR", "facility_id": fac.id})

    with TestClient(app) as client:
        # 1. Classify without mask
        resp = client.post(
            f"/api/images/{image_id}/classify",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] in ("PREDICTED", "ABSTAIN")
        assert data["suggested_label"] in MMOTU_8_CLASSES if data["status"] == "PREDICTED" else data["suggested_label"] is None

        # 2. Classify with custom RLE mask
        custom_rle = {"shape": [512, 512], "first_val": 0, "counts": [1000, 500, 260644]}
        resp2 = client.post(
            f"/api/images/{image_id}/classify",
            headers={"Authorization": f"Bearer {token}"},
            json={"mask_rle": custom_rle, "pixel_spacing_mm": 0.15},
        )
        assert resp2.status_code == 200, resp2.text
        data2 = resp2.json()
        assert data2["status"] in ("PREDICTED", "ABSTAIN")
        assert "mask_measurements" in data2


def test_cli_predict_image_mask_disease_execution(tmp_path):
    """Verify scripts/predict_image_mask_disease.py runs end-to-end via subprocess."""
    import subprocess
    import cv2

    img_path = tmp_path / "sample_us.png"
    mask_path = tmp_path / "sample_mask.png"
    json_path = tmp_path / "out_report.json"
    vis_path = tmp_path / "out_vis.png"

    dummy_img = np.random.randint(40, 200, (256, 256, 3), dtype=np.uint8)
    cv2.circle(dummy_img, (128, 128), 40, (220, 220, 220), -1)
    cv2.imwrite(str(img_path), dummy_img)

    dummy_mask = np.zeros((256, 256), dtype=np.uint8)
    cv2.circle(dummy_mask, (128, 128), 40, 255, -1)
    cv2.imwrite(str(mask_path), dummy_mask)

    cmd = [
        sys.executable,
        "scripts/predict_image_mask_disease.py",
        "--image", str(img_path),
        "--mask", str(mask_path),
        "--output-json", str(json_path),
        "--output-vis", str(vis_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert result.returncode == 0, f"CLI execution failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    assert json_path.is_file()
    assert vis_path.is_file()
    assert "KẾT QUẢ PHÂN LOẠI BỆNH HỌC" in result.stdout
