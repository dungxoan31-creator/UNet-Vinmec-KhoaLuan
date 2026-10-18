"""
Comprehensive test suite verifying fixes for:
1. CDSS Reasoning Engine endpoint (/api/v1/cdss/evaluate)
2. Medical PDF Report generation endpoint (/api/generate-report)
3. Ultrasound Pixel Spacing calibration endpoint (/api/images/{image_id}/calibrate)
4. Spatial surface distance metrics (HD95 & ASD)
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ai_training.metrics_clinical import compute_hd95_and_asd
from backend.app.main import app
from backend.db.database import Base, ImageModel, PatientModel, PredictionModel, StudyModel, get_db
from backend.services.cdss_engine import CDSSReasoningEngine


def test_cdss_reasoning_engine_deterministic_rules():
    engine = CDSSReasoningEngine()

    # A binary mask and a few morphology fields do not establish O-RADS.
    normal_eval = engine.evaluate_case(
        vision_findings={"max_diameter_mm": 22.0, "has_solid_component": False, "fluid_echogenicity": "anechoic"},
        patient_context={"age": 28, "is_postmenopausal": False},
    )
    assert normal_eval["success"] is True
    assert normal_eval["orads_stratification"]["category"] is None
    assert normal_eval["status"] == "INSUFFICIENT_DATA"

    # Case 2: Simple serous cyst 45mm
    simple_eval = engine.evaluate_case(
        vision_findings={
            "max_diameter_mm": 45.0,
            "ortho_diameter_mm": 38.0,
            "locules_count": 1,
            "has_solid_component": False,
            "fluid_echogenicity": "anechoic",
            "color_score": 1,
        },
        patient_context={"age": 34, "is_postmenopausal": False},
    )
    assert simple_eval["orads_stratification"]["category"] is None
    assert simple_eval["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"

    # Case 3: Endometrioma (ground glass)
    endo_eval = engine.evaluate_case(
        vision_findings={
            "max_diameter_mm": 52.0,
            "ortho_diameter_mm": 44.0,
            "locules_count": 1,
            "has_solid_component": False,
            "fluid_echogenicity": "ground_glass",
            "color_score": 1,
        },
        patient_context={"age": 31, "is_postmenopausal": False},
    )
    assert endo_eval["orads_stratification"]["category"] is None

    # Case 4: Multilocular cyst without solid component < 100mm
    multi_eval = engine.evaluate_case(
        vision_findings={
            "max_diameter_mm": 65.0,
            "ortho_diameter_mm": 50.0,
            "locules_count": 3,
            "has_solid_component": False,
            "color_score": 2,
        },
        patient_context={"age": 42, "is_postmenopausal": False},
    )
    assert multi_eval["orads_stratification"]["category"] is None

    # Case 5: High risk lesion with ascites
    high_risk_eval = engine.evaluate_case(
        vision_findings={
            "max_diameter_mm": 85.0,
            "ortho_diameter_mm": 60.0,
            "locules_count": 2,
            "has_solid_component": True,
            "has_ascites": True,
            "color_score": 3,
        },
        patient_context={"age": 58, "is_postmenopausal": True},
    )
    assert high_risk_eval["orads_stratification"]["category"] is None
    assert high_risk_eval["iota_evaluation"]["rule_verdict"] == "NOT_EVALUATED"


def test_cdss_api_endpoint(doctor_access):
    with TestClient(app) as client:
        payload = {
            "vision_findings": {
                "max_diameter_mm": 38.0,
                "ortho_diameter_mm": 26.0,
                "has_solid_component": False,
                "locules_count": 1,
                "fluid_echogenicity": "anechoic",
                "color_score": 1,
            },
            "patient_context": {"age": 32, "is_postmenopausal": False},
        }
        res = client.post("/api/v1/cdss/evaluate", json=payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["success"] is True
        assert data["orads_stratification"]["category"] is None
        assert data["status"] == "INSUFFICIENT_DATA"
        assert len(data["citations"]) >= 1


def test_generate_report_pdf_requires_server_side_clinical_approval(doctor_access):
    with TestClient(app) as client:
        # 1. Unvalidated request still returns 501
        empty_res = client.post("/api/generate-report", json={})
        assert empty_res.status_code == 501

        # 2. A client-supplied is_verified flag is not clinical approval.
        valid_payload = {
            "patientId": "200044962",
            "patientName": "Nguyễn Thị Phượng",
            "patientGender": "Nữ (Female)",
            "patientDob": "16/05/1991",
            "clinicalDiagnosis": "U nang buồng trứng phải",
            "is_verified": True,
            "doctorName": "BS.CKII. Trương Thị Phượng",
            "measurements": {
                "max_diameter_mm": 35.0,
                "ortho_diameter_mm": 26.0,
                "total_area_cm2": 7.15,
            },
        }
        valid_res = client.post("/api/generate-report", json=valid_payload)
        assert valid_res.status_code == 501, valid_res.text


def test_calibrate_spacing_endpoint(tmp_path, doctor_access):
    db_engine = create_engine(f"sqlite:///{tmp_path / 'calib.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(db_engine)

    def temp_db():
        with Session(db_engine) as db:
            yield db

    app.dependency_overrides[get_db] = temp_db
    try:
        with Session(db_engine) as db:
            p = PatientModel(id="p-1", anonymized_pid="ANON-TEST")
            db.add(p)
            s = StudyModel(id="s-1", patient_id="p-1", study_code="STD-TEST", study_date="2026-10-08")
            db.add(s)
            img = ImageModel(id="img-calib", study_id="s-1", filename="test.png", raw_path="test.png")
            db.add(img)
            # Add a prediction with a simple 512x512 mask
            mask_rle = {"shape": [512, 512], "first_val": 0, "counts": [1000, 500, 512 * 512 - 1500]}
            pred = PredictionModel(id="pred-calib", image_id="img-calib", raw_mask_rle=mask_rle, measurements={})
            db.add(pred)
            db.commit()

        with TestClient(app) as client:
            # Calibrate using pixel_spacing_mm = 0.12
            res = client.post("/api/images/img-calib/calibrate?pixel_spacing_mm=0.12")
            assert res.status_code == 200, res.text
            data = res.json()
            assert data["success"] is True
            assert data["pixel_spacing_mm"] == 0.12
            assert data["measurements"] is not None
            assert data["measurements"]["calibrated"] is True
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_hd95_and_asd_metrics():
    # 1. Identical masks: distance should be 0.0
    mask_a = np.zeros((100, 100), dtype=np.uint8)
    mask_a[30:70, 30:70] = 1
    res_identical = compute_hd95_and_asd(mask_a, mask_a, voxelspacing=1.0)
    assert res_identical["is_valid"] is True
    assert res_identical["hd95"] == 0.0
    assert res_identical["asd"] == 0.0

    # 2. Both empty masks
    empty = np.zeros((100, 100), dtype=np.uint8)
    res_empty = compute_hd95_and_asd(empty, empty)
    assert res_empty["is_valid"] is True
    assert res_empty["hd95"] == 0.0

    # 3. Shifted mask by 10 pixels: HD95 should be positive and finite
    mask_b = np.zeros((100, 100), dtype=np.uint8)
    mask_b[40:80, 40:80] = 1
    res_shifted = compute_hd95_and_asd(mask_a, mask_b, voxelspacing=1.0)
    assert res_shifted["is_valid"] is True
    assert res_shifted["hd95"] > 0
    assert res_shifted["asd"] > 0
