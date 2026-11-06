"""Regression checks for synthetic cases discovered by the independent audit."""
import cv2
import numpy as np
import pytest
from fastapi import HTTPException

from backend.services.inference_engine import InferenceEngine
from backend.services.morphology_extractor import separate_and_count_follicles
from backend.services.preprocessor import UltrasoundPreprocessor
from backend.services.review_validation import validate_review_mask
from backend.services.source_measurements import measure_source_mask


def test_modified_empty_mask_is_rejected():
    with pytest.raises(HTTPException) as error:
        validate_review_mask("MODIFIED", np.zeros((4, 4), np.uint8), np.ones((4, 4), np.uint8))
    assert error.value.status_code == 422


def test_watershed_failure_is_not_zero(monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("synthetic failure")
    monkeypatch.setattr("backend.services.morphology_extractor.separate_and_count_follicles", fail)
    mask = np.zeros((64, 64), np.uint8)
    cv2.circle(mask, (30, 30), 10, 1, -1)
    result = InferenceEngine.__new__(InferenceEngine).extract_calipers_and_measurements(mask, 0.1)["follicles"]
    assert result["analysis_status"] == "FAILED"
    assert result["count"] is None
    assert result["count_in_range"] is None


@pytest.mark.parametrize("diameter,expected", [(1.999, 0), (2.0, 1), (2.001, 1), (8.999, 1), (9.0, 1), (9.001, 0)])
def test_source_count_uses_unrounded_diameter(diameter, expected):
    mask = np.zeros((512, 512), np.uint8)
    cv2.circle(mask, (200, 200), 20, 1, -1)
    pixels = separate_and_count_follicles(mask)["diameters_px"][0]
    engine = InferenceEngine.__new__(InferenceEngine)
    result = measure_source_mask(mask, engine.mask_to_rle(mask), UltrasoundPreprocessor(), engine,
        {"pixel_spacing_mm": diameter / pixels, "calibrated": True, "calibration_source": "MANUAL"})
    assert result["follicles"]["count_in_range"] == expected


def test_uncalibrated_size_count_is_unknown():
    mask = np.zeros((64, 64), np.uint8)
    cv2.circle(mask, (30, 30), 10, 1, -1)
    result = separate_and_count_follicles(mask)
    assert result["count_in_range"] is None


def test_failed_region_analysis_is_not_reported_as_zero_or_follicles():
    from backend.services.report_generator import build_structured_findings_report
    report = build_structured_findings_report({"measurements": {"follicles": {
        "analysis_status": "FAILED", "count": None, "count_in_range": None,
    }}})
    assert "Không thể phân tích" in report
    assert "Số nang" not in report


@pytest.mark.usefixtures("doctor_access")
def test_identical_dicom_upload_rejected(tmp_path, monkeypatch, active_case_lease):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from test_dicom_scope_guard import make_dicom

    from backend.app.main import app
    from backend.app.routers import inference
    from backend.db.database import Base, ImageModel, PatientModel, StudyModel, UserModel, get_db

    engine = create_engine(f"sqlite:///{tmp_path / 'audit.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(UserModel(id="test-doctor", username="doctor", full_name="Test Doctor", role="DOCTOR"))
        db.add(PatientModel(id="p", anonymized_pid="SYNTHETIC-DUPLICATE"))
        db.add(StudyModel(id="s", patient_id="p", study_date="2026-10-28", ovary_side="BOTH"))
        db.commit()
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(tmp_path))
    def temporary_db():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            lease = active_case_lease(client, "s")
            headers = {"X-Case-Lease-Token": lease["lease_token"], "X-Case-Page-Instance-Id": lease["page_instance_id"]}
            content = make_dicom("US")
            first = client.post("/api/upload", headers=headers, data={"study_id": "s", "laterality": "R"}, files={"file": ("first.dcm", content, "application/dicom")})
            second = client.post("/api/upload", headers=headers, data={"study_id": "s", "laterality": "L"}, files={"file": ("second.dcm", content, "application/dicom")})
            assert first.status_code == 200, first.text
            assert second.status_code == 409, second.text
        with Session(engine) as db:
            assert db.query(ImageModel).filter_by(study_id="s").count() == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_source_hash_uniqueness_is_enforced_by_database(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    from backend.db.database import Base, ImageModel, PatientModel, StudyModel

    engine = create_engine(f"sqlite:///{tmp_path / 'source-hash.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(PatientModel(id="p", anonymized_pid="SYNTHETIC-HASH"))
        db.add(StudyModel(id="s", patient_id="p", study_date="2026-10-28"))
        db.commit()
        db.add(ImageModel(id="a", study_id="s", filename="a.dcm", raw_path="a.dcm",
                          file_hash="a" * 64, source_content_sha256="c" * 64))
        db.commit()
        db.add(ImageModel(id="b", study_id="s", filename="b.dcm", raw_path="b.dcm",
                          file_hash="b" * 64, source_content_sha256="c" * 64))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    engine.dispose()


@pytest.mark.usefixtures("doctor_access")
def test_simultaneous_duplicate_dicom_uploads_leave_one_image(tmp_path, monkeypatch, active_case_lease):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from test_dicom_scope_guard import make_dicom

    from backend.app.main import app
    from backend.app.routers import inference
    from backend.db.database import Base, ImageModel, PatientModel, StudyModel, UserModel, get_db

    engine = create_engine(f"sqlite:///{tmp_path / 'concurrent.db'}", connect_args={"check_same_thread": False, "timeout": 30})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(UserModel(id="test-doctor", username="doctor", full_name="Test Doctor", role="DOCTOR"))
        db.add(PatientModel(id="p", anonymized_pid="SYNTHETIC-RACE"))
        db.add(StudyModel(id="s", patient_id="p", study_date="2026-10-28", ovary_side="BOTH"))
        db.commit()
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(tmp_path))
    def temporary_db():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = temporary_db
    barrier = Barrier(2)
    decode = inference.decode_ultrasound_image
    def synchronized_decode(path):
        image = decode(path)
        barrier.wait(timeout=10)
        return image
    monkeypatch.setattr(inference, "decode_ultrasound_image", synchronized_decode)
    content = make_dicom("US")
    try:
        with TestClient(app) as client:
            lease = active_case_lease(client, "s")
        headers = {"X-Case-Lease-Token": lease["lease_token"], "X-Case-Page-Instance-Id": lease["page_instance_id"]}
        def upload(side):
            with TestClient(app) as client:
                return client.post("/api/upload", headers=headers, data={"study_id": "s", "laterality": side},
                                   files={"file": ("synthetic.dcm", content, "application/dicom")})
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(upload, ("L", "R")))
        assert sorted(response.status_code for response in responses) == [200, 409]
        with Session(engine) as db:
            assert db.query(ImageModel).filter_by(study_id="s").count() == 1
        assert len(list(tmp_path.glob("*.dcm"))) == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
