"""Regression tests for audit fixes - MAJOR issues."""
import io
import json

import numpy as np
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.core.image_utils import cv2_imwrite_unicode


def test_fe_03_research_export_metadata_includes_orads_and_morphology(tmp_path, monkeypatch):
    """FE-03: Exported research bundle metadata.json must explicitly include orads and morphology_description from saved review."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.routers.auth import create_access_token
    from backend.db.database import (
        Base,
        ImageModel,
        PatientModel,
        PredictionModel,
        ReviewModel,
        StudyModel,
        UserModel,
        get_db,
    )
    from backend.services.inference_engine import InferenceEngine

    engine = create_engine(f"sqlite:///{tmp_path / 'fe03.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    img_path = tmp_path / "img1.png"
    cv2_imwrite_unicode(str(img_path), np.zeros((100, 100, 3), dtype=np.uint8))

    rle_512 = InferenceEngine.mask_to_rle(np.zeros((512, 512), dtype=np.uint8))

    from datetime import UTC, datetime
    with Session(engine) as db:
        db.add(UserModel(id="u_doc", username="doctor1", full_name="BS. One", role="DOCTOR", is_active=True))
        p = PatientModel(id="p1", anonymized_pid="PID-001")
        s = StudyModel(id="s1", patient_id="p1", study_code="ST-001", study_date=datetime.now(UTC), review_revision=1)
        im = ImageModel(
            id="im1",
            study_id="s1",
            filename="img1.png",
            raw_path=str(img_path),
            laterality="R",
            width=100,
            height=100,
        )
        pred = PredictionModel(
            id="pr1",
            image_id="im1",
            raw_mask_rle=rle_512,
            measurements={},
            provenance_json={"model_name": "U-Net"},
        )
        rev = ReviewModel(
            id="rev1",
            image_id="im1",
            prediction_id="pr1",
            doctor_id="doctor1",
            doctor_action="MODIFIED",
            verified_mask_rle=rle_512,
            max_diameter_mm=25.0,
            ortho_diameter_mm=18.0,
            total_area_cm2=3.5,
            lesion_type="CYST",
            clinical_notes="Nang buồng trứng phải",
            hitl_feedback={
                "orads": "O-RADS 3",
                "orads_score": "O-RADS 3",
                "morphology_description": "U nang đơn thùy, thành mỏng",
            },
        )
        db.add_all([p, s, im, pred, rev])
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        import zipfile
        with TestClient(app) as client:
            token = create_access_token({"sub": "doctor1", "uid": "u_doc"})
            headers = {"Authorization": f"Bearer {token}"}

            resp = client.post(
                "/api/cases/s1/research-export",
                headers=headers,
                json={"review_ids": ["rev1"], "expected_revision": 1},
            )
            assert resp.status_code == 200

            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                assert "metadata.json" in zf.namelist()
                metadata = json.loads(zf.read("metadata.json").decode("utf-8"))
                images = metadata.get("images", [])
                assert len(images) == 1
                img_meta = images[0]

                # FE-03: Assert orads and morphology_description are present in exported metadata
                assert "orads" in img_meta, "FE-03 VULNERABILITY: 'orads' missing from exported image metadata!"
                assert img_meta["orads"] == "O-RADS 3"
                assert "morphology_description" in img_meta, "FE-03 VULNERABILITY: 'morphology_description' missing from exported image metadata!"
                assert img_meta["morphology_description"] == "U nang đơn thùy, thành mỏng"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_ai_04_erased_hole_reduces_mask_area():
    """AI-04: Mask area calculation must account for erased internal holes instead of returning filled outer envelope."""
    from backend.services.inference_engine import InferenceEngine

    engine = InferenceEngine.__new__(InferenceEngine)
    engine.default_pixel_spacing_mm = 1.0

    # Create a 200x200 mask with a 101x101 outer square and an erased 61x61 inner square
    mask = np.zeros((200, 200), dtype=np.uint8)
    mask[50:151, 50:151] = 1  # 101x101 outer square = 10,000 px contour area
    mask[70:131, 70:131] = 0  # 61x61 inner hole erased = ~3,600-3,800 px erased

    res = engine.extract_calipers_and_measurements(mask, pixel_spacing_mm=1.0)
    assert res["has_lesion"] is True
    lesion = res["lesions"][0]

    # Without fix, area_px is 10000.0 (ignoring the erased hole). With fix, hole is subtracted.
    assert lesion["area_px"] < 8000.0, (
        f"AI-04 VULNERABILITY: Internal hole ignored in lesion area calculation! Reported area_px: {lesion['area_px']}"
    )
    assert res["total_area_cm2"] < 80.0, (
        f"AI-04 VULNERABILITY: Internal hole ignored in total_area_cm2! Reported: {res['total_area_cm2']}"
    )


def test_ai_06_summary_diameters_belong_to_same_dominant_lesion():
    """AI-06: Summary max_diameter and ortho_diameter must belong to the same dominant lesion, not mixed across disjoint lesions."""
    from backend.services.inference_engine import InferenceEngine

    engine = InferenceEngine.__new__(InferenceEngine)
    engine.default_pixel_spacing_mm = 1.0

    # Create mask with two separate components:
    # Component 1 (dominant, area = 2000px): 100 wide x 20 high -> Dmax ~ 100, Dorth ~ 20
    # Component 2 (area = 1600px): 40 wide x 40 high -> Dmax ~ 40, Dorth ~ 40
    mask = np.zeros((300, 300), dtype=np.uint8)
    mask[20:40, 50:150] = 1   # 20x100
    mask[100:140, 50:90] = 1  # 40x40

    res = engine.extract_calipers_and_measurements(mask, pixel_spacing_mm=1.0)
    assert res["total_lesions"] == 2

    # The dominant lesion (index 0) is the 20x100 rectangle
    dominant = res["lesions"][0]
    assert np.isclose(dominant["max_diameter_mm"], 100.0, atol=2.0)
    assert np.isclose(dominant["ortho_diameter_mm"], 20.0, atol=2.0)

    # In AI-06 vulnerability: res["ortho_diameter_mm"] was taken from Component 2 (40mm),
    # resulting in a phantom lesion of 100mm x 40mm!
    assert res["ortho_diameter_mm"] < 30.0, (
        f"AI-06 VULNERABILITY: Summary dimensions mixed axes across different lesions! Reported Dmax={res['max_diameter_mm']}, Dorth={res['ortho_diameter_mm']}"
    )
    assert res["max_diameter_mm"] == dominant["max_diameter_mm"]
    assert res["ortho_diameter_mm"] == dominant["ortho_diameter_mm"]


def test_ai_08_cannot_overwrite_serving_model_key(tmp_path, monkeypatch):
    """AI-08: Registering a model candidate with an existing or reserved key must be rejected to prevent overwriting active serving models."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.config import model_registry
    from backend.app.routers.auth import create_access_token, hash_password
    from backend.db.database import Base, UserModel, get_db

    engine = create_engine(f"sqlite:///{tmp_path / 'ai08.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            UserModel(
                id="u_adm",
                username="admin1",
                full_name="Admin",
                role="ADMIN",
                is_active=True,
                password_hash=hash_password("adminpass123"),
            )
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            admin_token = create_access_token({"sub": "admin1", "uid": "u_adm"})
            ah = {"Authorization": f"Bearer {admin_token}"}

            original_adapter = model_registry.get_adapter("attention_unet")
            original_is_loaded = original_adapter.is_loaded if original_adapter else False

            # Attempt to register candidate model using active serving key "attention_unet"
            resp = client.post(
                "/api/admin/models/register",
                headers=ah,
                json={"model_id": "attention_unet", "name": "Fake Model", "checkpoint": "dummy.pt"},
            )
            # Must be rejected with 409 Conflict (or 400), NEVER 200 SUCCESS
            assert resp.status_code == 409, (
                f"AI-08 VULNERABILITY: Registered candidate overwritten serving model! Status={resp.status_code}, Body={resp.text}"
            )

            # Active serving model must remain intact
            current_adapter = model_registry.get_adapter("attention_unet")
            assert current_adapter is original_adapter
            assert current_adapter.is_loaded == original_is_loaded
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()



