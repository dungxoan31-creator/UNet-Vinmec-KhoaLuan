"""
Unit tests for metadata extraction and automatic calibration services (Phase 1).
"""

import numpy as np
import pytest

from backend.services.calibration_service import (
    detect_ruler_spacing_from_raster,
    get_automatic_calibration,
)
from backend.services.metadata_extractor import (
    extract_file_metadata,
    extract_filename_laterality,
)


def test_extract_filename_laterality():
    assert extract_filename_laterality("patient123_left_ovary.jpg")[0] == "L"
    assert extract_filename_laterality("patient123_right_trans.png")[0] == "R"
    assert extract_filename_laterality("PT45_LT.dcm")[0] == "L"
    assert extract_filename_laterality("CASE_RT_01.jpg")[0] == "R"
    assert extract_filename_laterality("TRAI_1.PNG")[0] == "L"
    assert extract_filename_laterality("PHAI_2.PNG")[0] == "R"
    assert extract_filename_laterality("ovary_scan.jpg")[0] is None
    assert extract_filename_laterality("left_and_right.jpg")[0] is None


def test_extract_file_metadata_raster_defaults():
    meta = extract_file_metadata("dummy/path/VNMC_99182_LEFT.png")
    assert meta["pid"]["value"] == "VNMC_99182"
    assert meta["pid"]["source"] == "filename"
    assert meta["pid"]["confidence"] == 0.85

    assert meta["laterality"]["value"] == "L"
    assert meta["laterality"]["source"] == "filename"

    assert "T" in meta["study_date"]["value"]  # YYYY-MM-DDTHH:MM format
    assert meta["reason"]["value"] == "Theo dõi hình thái"


def test_detect_ruler_spacing_synthetic_ticks():
    # Create an image with regular tick marks on the right margin every 20 pixels
    img = np.zeros((400, 300), dtype=np.uint8)
    for y in range(40, 360, 20):
        img[y : y + 2, 280:298] = 255  # bright tick mark on right strip

    spacing, conf = detect_ruler_spacing_from_raster(img)
    assert spacing is not None
    # 10mm / 20px = 0.5 mm/px
    assert spacing == pytest.approx(0.5, rel=0.1)
    assert conf >= 0.7


def test_get_automatic_calibration_fallback():
    # Blank image has no ruler ticks
    blank = np.zeros((200, 200), dtype=np.uint8)
    calib = get_automatic_calibration("unknown.png", blank)
    assert calib["calibrated"] is False
    assert calib["pixel_spacing_mm"] == 0.1
    assert calib["source"] == "default_uncalibrated"


def test_extract_intake_metadata_api(monkeypatch):
    import io
    from datetime import timedelta

    import cv2
    from fastapi.testclient import TestClient

    monkeypatch.setenv("APP_JWT_SECRET", "production-ready-jwt-secret-key-32-chars-minimum")
    from backend.app.main import app
    from backend.app.security import create_access_token, hash_password
    from backend.db.database import SessionLocal, UserModel, init_db

    init_db()
    with SessionLocal() as db:
        user = db.query(UserModel).filter(UserModel.username == "doctor_intake_test").first()
        if not user:
            user = UserModel(
                id="user-intake-test",
                username="doctor_intake_test",
                full_name="Dr. Test Intake",
                password_hash=hash_password("doctor123password"),
                role="DOCTOR",
                is_active=True,
            )
            db.add(user)
            db.commit()

    token = create_access_token(
        data={"sub": "doctor_intake_test", "role": "DOCTOR", "user_id": "user-intake-test"},
        expires_delta=timedelta(hours=1),
    )
    client = TestClient(app)

    # Synthetic image
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".png", img)

    resp = client.post(
        "/api/intake/extract-metadata",
        files={"file": ("VNMC_10293_LEFT.png", io.BytesIO(buf.tobytes()), "image/png")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "metadata" in data
    assert data["metadata"]["pid"]["value"] == "VNMC_10293"
    assert data["metadata"]["laterality"]["value"] == "L"
    assert "calibration" in data
    assert data["calibration"]["calibrated"] is False

