import os
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-chars-long-12345")

import uuid
from datetime import datetime, UTC
import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import create_access_token, hash_password
from backend.db.database import (
    FacilityModel,
    ImageModel,
    SessionLocal,
    StudyModel,
    UserModel,
)
from backend.services.inference_engine import InferenceEngine


@pytest.fixture
def overlay_test_env(tmp_path):
    prefix = uuid.uuid4().hex[:8]
    test_db = SessionLocal()

    fac = FacilityModel(
        id=f"FAC-OV-{prefix}",
        name=f"Facility Overlay {prefix}",
        facility_code=f"FOV-{prefix}",
        is_active=True,
    )
    test_db.add(fac)
    test_db.commit()

    pwd_hash = hash_password("SecurePass123!")
    doc = UserModel(
        id=f"doc-ov-{prefix}",
        username=f"doctor_ov_{prefix}",
        full_name="Dr. Overlay",
        role="DOCTOR",
        facility_id=fac.id,
        password_hash=pwd_hash,
        is_active=True,
    )
    test_db.add(doc)
    test_db.commit()

    from tests.test_vinmec_api_smoke import synthetic_fixture_image
    img_path = synthetic_fixture_image()

    study = StudyModel(
        id=f"study-ov-{prefix}",
        study_code=f"ST-OV-{prefix}",
        study_date="2026-11-01",
        facility_id=fac.id,
        status="PENDING",
    )
    test_db.add(study)
    test_db.commit()

    image = ImageModel(
        id=f"img-ov-{prefix}",
        study_id=study.id,
        filename=f"img_{prefix}.png",
        raw_path=str(img_path),
        laterality="R",
        file_hash=f"hash-{prefix}",
        source_content_sha256=f"dummy-sha-{prefix}",
    )
    test_db.add(image)
    test_db.commit()

    token = create_access_token({"sub": doc.username, "role": "DOCTOR", "facility_id": fac.id})
    client = TestClient(app)

    try:
        yield {
            "client": client,
            "token": token,
            "image": image,
            "study": study,
            "db": test_db,
        }
    finally:
        test_db.close()


def test_inference_engine_predict_default_no_overlay(monkeypatch):
    """InferenceEngine.run_inference defaults to generate_overlay=False."""
    from backend.app.config import model_registry
    engine = model_registry.get_primary_adapter().engine
    engine.forward_probabilities = lambda _tensor: np.zeros((512, 512), dtype=np.float32)
    dummy_tensor = torch.zeros((1, 1, 512, 512), dtype=torch.float32)
    dummy_gray = np.zeros((512, 512), dtype=np.uint8)

    # 1. Default call (no generate_overlay arg)
    result_default = engine.run_inference(dummy_tensor, dummy_gray)
    assert result_default["overlay_base64"] is None, "Default run_inference must NOT generate overlay"

    # 2. Explicit generate_overlay=True
    result_with_overlay = engine.run_inference(dummy_tensor, dummy_gray, generate_overlay=True)
    assert result_with_overlay["overlay_base64"] is not None
    assert result_with_overlay["overlay_base64"].startswith("data:image/png;base64,")


def test_api_predict_default_no_overlay(overlay_test_env, monkeypatch):
    """POST /api/predict/{image_id} returns overlay_base64=None by default, unless ?generate_overlay=true."""
    from backend.app.config import model_registry
    from tests.helpers.synthetic_inference import enable_synthetic_inference

    enable_synthetic_inference(monkeypatch, model_registry)
    client = overlay_test_env["client"]
    token = overlay_test_env["token"]
    image = overlay_test_env["image"]
    study = overlay_test_env["study"]

    page_inst_id = "test-page-inst-1"
    lease_resp = client.post(
        f"/api/workspace/cases/{study.id}/lease",
        headers={"Authorization": f"Bearer {token}"},
        json={"tab_id": "test-tab-id-12345678", "page_instance_id": page_inst_id},
    )
    assert lease_resp.status_code == 200, lease_resp.text
    lease_token = lease_resp.json()["lease_token"]

    lease_headers = {
        "Authorization": f"Bearer {token}",
        "X-Case-Lease-Token": lease_token,
        "X-Case-Page-Instance-Id": page_inst_id,
        "Idempotency-Key": str(uuid.uuid4()),
    }

    # 1. Default call -> overlay_base64 is None
    resp_default = client.post(f"/api/predict/{image.id}", headers=lease_headers)
    assert resp_default.status_code == 200, resp_default.text
    data_default = resp_default.json()
    assert data_default["overlay_base64"] is None, "API must not return overlay by default"
    assert data_default["rle_mask"] is not None

    # 2. Call with generate_overlay=true -> overlay_base64 is present
    headers_with_overlay = {**lease_headers, "Idempotency-Key": str(uuid.uuid4())}
    resp_with_overlay = client.post(f"/api/predict/{image.id}?generate_overlay=true", headers=headers_with_overlay)
    assert resp_with_overlay.status_code == 200, resp_with_overlay.text
    data_with_overlay = resp_with_overlay.json()
    assert data_with_overlay["overlay_base64"] is not None
    assert data_with_overlay["overlay_base64"].startswith("data:image/png;base64,")
