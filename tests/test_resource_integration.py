"""Regression evidence for resource consolidation; synthetic inputs only."""

import cv2
import numpy as np
import pytest
import torch

from backend.services.disease_classifier import DiseaseClassifierService
from backend.services.image_classifier import CHECKSUM, image_classifier


def test_facade_reuses_verified_bgr_training_pipeline_without_second_model():
    image = np.random.default_rng(73).integers(0, 256, (143, 287, 3), dtype=np.uint8)
    direct = image_classifier.predict(image)
    service = DiseaseClassifierService()
    result = service.predict_disease(image)
    assert service.classifier is image_classifier
    assert result["probabilities"] == direct["probabilities"]
    assert result["provenance"]["checkpoint_sha256"] == CHECKSUM
    assert result["research_use_only"] and result["requires_clinician_confirmation"]
    assert result["is_malignant_suspected"] is None


@pytest.mark.parametrize("bad_file", [None, b"invalid checkpoint"])
def test_facade_missing_or_invalid_weights_cannot_predict(tmp_path, bad_file):
    path = tmp_path / "not-verified.pth"
    if bad_file is not None:
        path.write_bytes(bad_file)
    service = DiseaseClassifierService(checkpoint_path=path)
    result = service.predict_disease(np.zeros((32, 32), np.uint8))
    assert result["status"] == "UNAVAILABLE"
    assert result["suggested_label_vi"] is None
    assert service.is_loaded is False
    assert not result.get("probabilities")


def test_mask_equivalent_diameter_is_not_maximum_diameter():
    image = np.full((120, 240), 80, np.uint8)
    mask = np.zeros(image.shape, np.uint8)
    mask[30:51, 40:141] = 1
    measurements = DiseaseClassifierService().predict_disease(image, mask, .1)["mask_measurements"]
    assert measurements["max_diameter_mm"] == 10.0
    assert measurements["equivalent_diameter_mm"] == pytest.approx(5.2, abs=.01)
    assert measurements["area_cm2"] == pytest.approx(.212, abs=.001)
    assert DiseaseClassifierService().predict_disease(image, mask)["mask_measurements"]["max_diameter_mm"] is None
    with pytest.raises(ValueError, match="dimensions"):
        DiseaseClassifierService().predict_disease(image, np.zeros((512, 512), np.uint8))


def test_prediction_classifies_source_exactly_once(doctor_access, active_case_lease, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.app.main import app
    from backend.app.config import model_registry
    from backend.db.database import SessionLocal
    from tests.helpers.fixture_factory import create_test_image, create_test_study
    from tests.helpers.synthetic_inference import enable_synthetic_inference

    enable_synthetic_inference(monkeypatch, model_registry)

    image = np.random.default_rng(79).integers(30, 190, (180, 360, 3), dtype=np.uint8)
    path = tmp_path / "synthetic.png"
    cv2.imwrite(str(path), image)
    with SessionLocal() as db:
        study = create_test_study(db, facility_id="FAC-DEFAULT-TEST")
        record = create_test_image(db, study.id, raw_path=str(path))
        study_id, image_id = study.id, record.id
    calls = []
    original = image_classifier.predict

    def observed(pixels):
        calls.append(pixels.copy())
        return original(pixels)

    monkeypatch.setattr(image_classifier, "predict", observed)
    with TestClient(app) as client:
        lease = active_case_lease(client, study_id)
        response = client.post(f"/api/predict/{image_id}", headers={
            "X-Case-Lease-Token": lease["lease_token"],
            "X-Case-Page-Instance-Id": lease["page_instance_id"],
        })
        assert response.status_code == 200, response.text
        assert len(calls) == 1
        assert np.array_equal(calls[0], image)
        assert response.json()["timings"]["server_pipeline_ms"] >= response.json()["timings"]["classification_ms"]
        lease_headers = {
            "X-Case-Lease-Token": lease["lease_token"],
            "X-Case-Page-Instance-Id": lease["page_instance_id"],
        }
        assert client.post(f"/api/predict/{image_id}?model_key=tinyusfm", headers=lease_headers).status_code == 503
        assert client.post(f"/api/predict/{image_id}?model_key=unknown-model", headers=lease_headers).status_code == 422
        assert len(calls) == 1, "Unavailable adapters must not rerun the primary or classifier"

        # Rectangular source geometry must be recovered from the viewer mask.
        from backend.services.inference_engine import InferenceEngine
        mask = np.zeros((512, 512), np.uint8)
        mask[200:300, 100:400] = 1
        result = client.post(f"/api/images/{image_id}/classify", json={
            "mask_rle": InferenceEngine.mask_to_rle(mask), "pixel_spacing_mm": .1,
        })
        assert result.status_code == 200, result.text
        assert result.json()["mask_measurements"]["lesion_detected"] is True
        assert result.json()["mask_measurements"]["coordinate_space"] == "decoded-source-image"
        for spacing in (-1, 0, "NaN", True, 1e200):
            assert client.post(f"/api/images/{image_id}/classify", json={"pixel_spacing_mm": spacing}).status_code == 422
        assert client.post(f"/api/images/{image_id}/classify", json={
            "mask_rle": {"shape": [1, 1], "counts": [1]},
        }).status_code == 422
        assert client.post(f"/api/images/{image_id}/classify", json={"mask_rle": {}}).status_code == 422
        assert client.post(f"/api/images/{image_id}/classify", json={"unknown_field": True}).status_code == 422


def test_unimplemented_registered_models_do_not_become_loaded_from_file_presence(monkeypatch):
    from types import SimpleNamespace

    from backend.services import model_service

    monkeypatch.setattr(model_service, "InferenceEngine", lambda **_: SimpleNamespace(
        device="cpu", model_name="test", architecture_name="test", is_model_ready=True,
    ))
    monkeypatch.setattr(model_service.ModelRegistry, "load_persisted_candidates", lambda _: None)
    monkeypatch.setattr(model_service.os.path, "isfile", lambda _: True)
    registry = model_service.ModelRegistry()
    assert registry.get_primary_adapter().is_loaded
    for key, adapter in registry.adapters.items():
        if key == "attention_unet":
            continue
        assert adapter.is_loaded is False
        assert adapter.get_info()["checksum"] is None
        assert adapter.get_info()["threshold"] is None
        with pytest.raises(ValueError, match="no native loaded"):
            registry.predict(None, None, model_key=key)


def test_latency_benchmark_does_not_invent_accuracy():
    from types import SimpleNamespace

    from scripts.evaluate_model_zoo_benchmark import benchmark_loaded_adapter

    with pytest.raises(RuntimeError, match="not loaded"):
        benchmark_loaded_adapter(SimpleNamespace(is_loaded=False))
    adapter = SimpleNamespace(
        is_loaded=True, get_info=lambda: {"name": "synthetic test double"},
        engine=SimpleNamespace(device="cpu", forward_probabilities=lambda _: None, model=torch.nn.Identity()),
    )
    result = benchmark_loaded_adapter(adapter, iterations=2)
    assert result["accuracy_evaluated"] is False
    assert result["dataset"] is None
    assert len(result["latency_ms"]["samples"]) == 2
    assert not any(key in result for key in ("dice_dsc", "iou_jaccard", "hd95_mm"))


def test_cli_reuses_bounded_dicom_decoder_and_source_mask_geometry(tmp_path):
    from backend.services.inference_engine import InferenceEngine
    from backend.services.preprocessor import UltrasoundPreprocessor
    from scripts.predict_image_mask_disease import load_image, load_or_generate_mask
    from tests.test_dicom_scope_guard import make_dicom

    dicom_path = tmp_path / "synthetic.dcm"
    dicom_path.write_bytes(make_dicom("US", rows=128, columns=256))
    decoded = load_image(dicom_path)
    assert decoded.shape[:2] == (128, 256)
    mask = np.zeros((128, 256), np.uint8)
    mask[40:80, 50:150] = 1
    mask_path = tmp_path / "synthetic-mask.png"
    cv2.imwrite(str(mask_path), mask)
    prepared, measurements = load_or_generate_mask(
        decoded, mask_path, UltrasoundPreprocessor(), InferenceEngine.__new__(InferenceEngine), None,
    )
    assert prepared.shape == (512, 512)
    assert not prepared[:128].any() and not prepared[384:].any()
    assert measurements["calibrated"] is False
    assert measurements["max_diameter_mm"] is None
    assert measurements["max_diameter_px"] == pytest.approx(99, abs=.1)
