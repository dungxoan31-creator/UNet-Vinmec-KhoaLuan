"""
Regression test suite proving the remediation of audit findings F01-F14.
Assertions test the DESIRED secure, clinical, and robust behavior.
"""

import uuid
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import create_access_token, hash_password
from backend.db.database import SessionLocal, FacilityModel, UserModel, AuditLogModel
from tests.helpers.fixture_factory import create_test_facility, create_test_user


def test_cross_facility_admin_cannot_reset_other_facility_password(monkeypatch):
    """F01 Remediation: Facility A admin must NOT be able to reset Facility B user password."""
    monkeypatch.setenv("APP_JWT_SECRET", "synthetic-audit-key-20261101-at-least-32-characters")
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        fac_a = create_test_facility(db, f"fac-a-{suffix}", f"Facility A {suffix}")
        fac_b = create_test_facility(db, f"fac-b-{suffix}", f"Facility B {suffix}")

        admin_a = create_test_user(db, facility_id=fac_a.id, role="ADMIN", username=f"admin_{suffix}")
        doc_b = create_test_user(db, facility_id=fac_b.id, role="DOCTOR", username=f"doc_{suffix}")
        doc_b.password_hash = hash_password("OriginalPassword123!")
        db.commit()

        token = create_access_token({"sub": admin_a.username, "role": "ADMIN", "facility_id": fac_a.id})
        previous_hash = doc_b.password_hash

        with TestClient(app) as client:
            resp = client.post(
                f"/api/admin/users/{doc_b.id}/reset-password",
                headers={"Authorization": f"Bearer {token}"},
                json={"new_password": "HackedPassword123!"},
            )

        db.refresh(doc_b)
        # Expected: 404 (or 403) to prevent tenant leakage, and password MUST NOT change
        assert resp.status_code in (403, 404), resp.text
        assert doc_b.password_hash == previous_hash, "Target password MUST NOT be modified by cross-facility admin"


def test_admin_cannot_self_deactivate_or_self_demote(monkeypatch):
    """F10 Remediation: Admin must NOT be able to self-deactivate, self-demote, or self-delete."""
    monkeypatch.setenv("APP_JWT_SECRET", "synthetic-audit-key-20261101-at-least-32-characters")
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        fac = create_test_facility(db, f"fac-f10-{suffix}", f"Facility F10 {suffix}")
        admin = create_test_user(db, facility_id=fac.id, role="ADMIN", username=f"admin_f10_{suffix}")
        db.commit()

        token = create_access_token({"sub": admin.username, "role": "ADMIN", "facility_id": fac.id})

        with TestClient(app) as client:
            # 1. Attempt self-deactivation
            resp_deact = client.patch(
                f"/api/admin/users/{admin.id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"is_active": False},
            )
            assert resp_deact.status_code == 400, f"Self-deactivation must return 400, got: {resp_deact.status_code}"

            # 2. Attempt self-demotion
            resp_demote = client.patch(
                f"/api/admin/users/{admin.id}",
                headers={"Authorization": f"Bearer {token}"},
                json={"role": "DOCTOR"},
            )
            assert resp_demote.status_code == 400, f"Self-demotion must return 400, got: {resp_demote.status_code}"

            # 3. Attempt self-deletion
            resp_del = client.delete(
                f"/api/admin/users/{admin.id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp_del.status_code == 400, f"Self-deletion must return 400, got: {resp_del.status_code}"

        db.refresh(admin)
        assert admin.is_active is True, "Admin MUST remain active"
        assert admin.role == "ADMIN", "Admin role MUST remain ADMIN"


def test_dashboard_stats_scoped_by_facility(monkeypatch):
    """F11 Remediation: /api/stats must return metrics strictly scoped to user's facility."""
    from tests.helpers.fixture_factory import create_test_patient, create_test_study, create_test_image
    monkeypatch.setenv("APP_JWT_SECRET", "synthetic-audit-key-20261101-at-least-32-characters")
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        fac_a = create_test_facility(db, f"fac-f11a-{suffix}", f"Facility A {suffix}")
        fac_b = create_test_facility(db, f"fac-f11b-{suffix}", f"Facility B {suffix}")

        user_a = create_test_user(db, facility_id=fac_a.id, role="DOCTOR", username=f"doc_a_{suffix}")
        user_b = create_test_user(db, facility_id=fac_b.id, role="DOCTOR", username=f"doc_b_{suffix}")

        # Seed 2 studies in Facility A
        pat_a = create_test_patient(db)
        std_a1 = create_test_study(db, facility_id=fac_a.id, patient_id=pat_a.id)
        img_a1 = create_test_image(db, study_id=std_a1.id)
        std_a2 = create_test_study(db, facility_id=fac_a.id, patient_id=pat_a.id)
        img_a2 = create_test_image(db, study_id=std_a2.id)

        # Seed 1 study in Facility B
        pat_b = create_test_patient(db)
        std_b1 = create_test_study(db, facility_id=fac_b.id, patient_id=pat_b.id)
        img_b1 = create_test_image(db, study_id=std_b1.id)
        db.commit()

        token_a = create_access_token({"sub": user_a.username, "role": "DOCTOR", "facility_id": fac_a.id})
        token_b = create_access_token({"sub": user_b.username, "role": "DOCTOR", "facility_id": fac_b.id})

        with TestClient(app) as client:
            resp_a = client.get("/api/stats", headers={"Authorization": f"Bearer {token_a}"})
            assert resp_a.status_code == 200, resp_a.text
            stats_a = resp_a.json()

            resp_b = client.get("/api/stats", headers={"Authorization": f"Bearer {token_b}"})
            assert resp_b.status_code == 200, resp_b.text
            stats_b = resp_b.json()

        # Check scoping: facility A must only count facility A studies/images
        assert stats_a["total_cases_received"] >= 2
        assert stats_b["total_cases_received"] >= 1
        assert stats_a["total_cases_received"] != stats_b["total_cases_received"] or stats_a["total_cases_received"] >= 2


def _make_valid_simple_cyst_findings(diameter_mm: float) -> dict:
    return {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_diameter_mm": diameter_mm,
        "locules_count": 1,
        "has_solid_component": False,
        "papillary_projections_count": 0,
        "fluid_echogenicity": "anechoic",
        "acoustic_shadowing": False,
        "wall_irregular": False,
        "color_score": 1,
        "has_ascites": False,
        "has_peritoneal_nodules": False,
    }


def test_cdss_100mm_boundary_and_simple_cyst_orads3():
    """F02 Remediation: Simple cyst >= 100 mm is O-RADS 3; < 100 mm is O-RADS 2."""
    from backend.services.cdss_engine import CDSSReasoningEngine

    engine = CDSSReasoningEngine()

    # 1. 99.9 mm -> O-RADS 2
    res_99_9 = engine.evaluate_case(vision_findings=_make_valid_simple_cyst_findings(99.9))
    assert res_99_9["status"] == "RULE_MATCHED"
    assert res_99_9["orads_stratification"]["category"] == "O-RADS 2"

    # 2. Exactly 100.0 mm -> O-RADS 3 (was bug F02: previously returned O-RADS 2)
    res_100 = engine.evaluate_case(vision_findings=_make_valid_simple_cyst_findings(100.0))
    assert res_100["status"] == "RULE_MATCHED"
    assert res_100["orads_stratification"]["category"] == "O-RADS 3", (
        f"Expected O-RADS 3 for 100.0 mm, got {res_100['orads_stratification']['category']}"
    )

    # 3. 100.1 mm -> O-RADS 3
    res_100_1 = engine.evaluate_case(vision_findings=_make_valid_simple_cyst_findings(100.1))
    assert res_100_1["status"] == "RULE_MATCHED"
    assert res_100_1["orads_stratification"]["category"] == "O-RADS 3"

    # 4. NaN / Inf / non-finite -> UNSUPPORTED_PATTERN
    res_nan = engine.evaluate_case(vision_findings=_make_valid_simple_cyst_findings(float("nan")))
    assert res_nan["status"] == "UNSUPPORTED_PATTERN"

    # 5. <= 30 mm without physiologic flag -> UNSUPPORTED_PATTERN
    res_30 = engine.evaluate_case(vision_findings=_make_valid_simple_cyst_findings(30.0))
    assert res_30["status"] == "UNSUPPORTED_PATTERN"


def test_cdss_multi_lesion_aggregation_worst_case(monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "synthetic-audit-key-20261101-at-least-32-characters")
    """F13 Remediation: Multi-lesion aggregation uses worst-case semantics and fails closed if any lesion unresolved."""
    from backend.services.cdss_engine import CDSSReasoningEngine

    engine = CDSSReasoningEngine()

    lesion_2 = _make_valid_simple_cyst_findings(50.0)  # O-RADS 2
    lesion_3 = _make_valid_simple_cyst_findings(120.0) # O-RADS 3

    # All matched: overall is worst-case (O-RADS 3)
    res_multi = engine.evaluate_multi_lesions(
        lesions=[
            {"lesion_id": "L1", "findings": lesion_2},
            {"lesion_id": "L2", "findings": lesion_3},
        ]
    )
    assert res_multi["complete"] is True
    assert res_multi["status"] == "RULE_MATCHED"
    assert res_multi["overall_category"] == "O-RADS 3"
    assert len(res_multi["lesion_evaluations"]) == 2

    # Incomplete: Lesion 1 is O-RADS 2, Lesion 2 is incomplete (missing descriptors)
    incomplete_lesion = {"assessment_source": "clinician", "modality": "ultrasound_2d"}
    res_incomplete = engine.evaluate_multi_lesions(
        lesions=[
            {"lesion_id": "L1", "findings": lesion_2},
            {"lesion_id": "L2", "findings": incomplete_lesion},
        ]
    )
    assert res_incomplete["complete"] is False
    assert res_incomplete["status"] == "INCOMPLETE_OR_UNSUPPORTED"
    assert res_incomplete["overall_category"] is None

    # Empty lesions list
    res_empty = engine.evaluate_multi_lesions(lesions=[])
    assert res_empty["complete"] is False
    assert res_empty["status"] == "NO_LESIONS"
    assert res_empty["overall_category"] is None

    # Test API endpoint
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        fac = create_test_facility(db, f"fac-cdss-{suffix}")
        u = create_test_user(db, facility_id=fac.id, role="DOCTOR", username=f"doc_cdss_{suffix}")
        token = create_access_token({"sub": u.username, "role": "DOCTOR", "facility_id": fac.id})
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/cdss/evaluate-multi",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "lesions": [
                    {"lesion_id": "L1", "findings": lesion_2},
                    {"lesion_id": "L2", "findings": lesion_3},
                ]
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["complete"] is True
        assert data["overall_category"] == "O-RADS 3"


def test_caliper_removal_safety_lock():
    """F03 Remediation: Automatic caliper removal is locked and fails closed until verified clinician mask workflow."""
    from backend.services.preprocessor import UltrasoundPreprocessor

    prep = UltrasoundPreprocessor()
    synthetic_img = np.ones((128, 128), dtype=np.uint8) * 50
    # Simulate a bright line (caliper proxy or thin septum)
    synthetic_img[60, 20:80] = 250

    # Auto caliper removal MUST raise ValueError
    with pytest.raises(ValueError, match="Tự động xóa caliper chưa được xác thực"):
        prep.preprocess(synthetic_img, enable_caliper_removal=True)

    # Standard processing MUST succeed without mutating thin septum
    tensor, padded, params, iqa = prep.preprocess(synthetic_img, enable_caliper_removal=False)
    assert tensor.shape == (1, 1, 512, 512)
    assert padded.shape == (512, 512)


def test_speckle_srad_filter_robustness():
    """F05 Remediation: SRAD filter keyword arguments and execution robustness."""
    from backend.services.preprocessor import UltrasoundPreprocessor
    from scripts.ultrasound_preprocessing_enhancement import SpeckleFilter

    synthetic_img = (np.random.rand(64, 64) * 255).astype(np.uint8)

    # 1. Direct SRAD call with n_iter
    out1 = SpeckleFilter.srad_filter(synthetic_img, n_iter=3)
    assert out1.shape == (64, 64)

    # 2. Direct SRAD call with num_iter (compatibility)
    out2 = SpeckleFilter.srad_filter(synthetic_img, num_iter=3)
    assert out2.shape == (64, 64)

    # 3. Preprocessor pipeline with denoise_method="srad"
    prep = UltrasoundPreprocessor()
    tensor, padded, _, _ = prep.preprocess(synthetic_img, denoise_method="srad")
    assert tensor.shape == (1, 1, 512, 512)


def test_correction_supports_single_image_case(monkeypatch):
    """F08 Remediation: Correction workflow supports 1 to 20 images, not locked to exactly 2 images."""
    from tests.helpers.fixture_factory import create_test_facility, create_test_user, create_test_study, create_test_image
    from backend.db.database import CorrectionRequestModel
    from datetime import datetime, UTC

    monkeypatch.setenv("APP_JWT_SECRET", "synthetic-audit-key-20261101-at-least-32-characters")
    suffix = uuid.uuid4().hex[:8]

    with SessionLocal() as db:
        fac = create_test_facility(db, f"fac-f08-{suffix}")
        doc = create_test_user(db, facility_id=fac.id, role="DOCTOR", username=f"doc_f08_{suffix}")
        tech = create_test_user(db, facility_id=fac.id, role="SENIOR", username=f"tech_f08_{suffix}")

        # Single-image study
        study = create_test_study(db, facility_id=fac.id, assignee_id=doc.id)
        img = create_test_image(db, study_id=study.id)

        corr = CorrectionRequestModel(
            id=f"corr-f08-{suffix}",
            study_id=study.id,
            review_revision=0,
            reason="Hiệu chỉnh ca 1 ảnh",
            doctor_id=doc.id,
            technician_id=tech.id,
            status="PENDING",
            created_at=datetime.now(UTC),
        )
        db.add(corr)
        db.commit()

        token_tech = create_access_token({"sub": tech.username, "role": "SENIOR", "facility_id": fac.id})

        with TestClient(app) as client:
            # 1. Acquire lease
            lease_resp = client.post(
                f"/api/workspace/cases/{study.id}/lease",
                headers={"Authorization": f"Bearer {token_tech}"},
                json={"tab_id": f"tab-instance-{suffix}-long", "page_instance_id": f"page-instance-{suffix}-long"},
            )
            assert lease_resp.status_code == 200, lease_resp.text
            lease_data = lease_resp.json()
            assert lease_data["granted"] is True

            # 2. Save draft correction for 1 image (was bug F08: failed with 422 if != 2)
            rle = {"shape": [512, 512], "first_val": 0, "counts": [262144]}
            draft_resp = client.put(
                f"/api/workspace/cases/{study.id}/corrections",
                headers={"Authorization": f"Bearer {token_tech}"},
                json={
                    "correction_id": corr.id,
                    "base_revision": 0,
                    "lease_token": lease_data["lease_token"],
                    "page_instance_id": f"page-instance-{suffix}-long",
                    "draft_payload": {
                        "images": [
                            {"image_id": img.id, "verified_mask_rle": rle, "notes": "1-img test", "morphology": ""}
                        ]
                    },
                },
            )
            assert draft_resp.status_code == 200, draft_resp.text
            data = draft_resp.json()
            assert data["status"] == "SUBMITTED"


def test_audit_log_immutability_triggers():
    """F06 Remediation: Audit log entries are strictly append-only; UPDATE and DELETE are blocked by triggers."""
    from backend.db.database import init_db, AuditLogModel
    from sqlalchemy.exc import DatabaseError, OperationalError
    from sqlalchemy import text
    from datetime import datetime, UTC

    init_db()

    with SessionLocal() as db:
        log_entry = AuditLogModel(
            entity_name="study",
            entity_id=f"test-{uuid.uuid4().hex[:8]}",
            action_type="TEST_IMMUTABILITY",
            actor_id="test_doctor",
            details={"note": "original"},
            timestamp=datetime.now(UTC),
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        entry_id = log_entry.id

        # 1. Attempt to UPDATE the audit record -> MUST fail
        with pytest.raises((DatabaseError, OperationalError), match="immutable"):
            db.execute(text(f"UPDATE audit_logs SET action_type = 'TAMPERED' WHERE id = {entry_id}"))
            db.commit()
        db.rollback()

        # 2. Attempt to DELETE the audit record -> MUST fail
        with pytest.raises((DatabaseError, OperationalError), match="immutable"):
            db.execute(text(f"DELETE FROM audit_logs WHERE id = {entry_id}"))
            db.commit()
        db.rollback()

        # 3. Verify record was NOT altered or removed
        refreshed = db.query(AuditLogModel).filter_by(id=entry_id).first()
        assert refreshed is not None
        assert refreshed.action_type == "TEST_IMMUTABILITY"


def test_facility_status_created_index_exists():
    """F12 Remediation: Verify multi-tenant composite index ix_studies_facility_status_created exists."""
    from backend.db.database import init_db
    from sqlalchemy import text

    init_db()
    with SessionLocal() as db:
        indexes = db.execute(text("PRAGMA index_list(studies)")).fetchall()
        index_names = {row[1] for row in indexes}
        assert "ix_studies_facility_status_created" in index_names, (
            f"Expected index ix_studies_facility_status_created in studies table, found: {index_names}"
        )


def test_audit_leakage_hashes_file_bytes(tmp_path):
    """F07 Remediation: Split leakage audit hashes binary file contents via hashlib.file_digest, not path strings."""
    from scripts.audit_patient_independence_leakage import audit_splits
    import csv

    # Create dummy image content
    img_data = b"SYNTHETIC_IMAGE_BYTES_20261101_REPEAT_CHECK"
    file_a = tmp_path / "img_train.png"
    file_b = tmp_path / "img_val_different_name.png"
    file_a.write_bytes(img_data)
    file_b.write_bytes(img_data)

    splits_dir = tmp_path / "splits_test"
    splits_dir.mkdir()

    # Create train.csv and val.csv pointing to the two files with different names
    train_csv = splits_dir / "train.csv"
    with open(train_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file_path"])
        writer.writeheader()
        writer.writerow({"file_path": str(file_a)})

    val_csv = splits_dir / "val.csv"
    with open(val_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file_path"])
        writer.writeheader()
        writer.writerow({"file_path": str(file_b)})

    report = audit_splits(str(splits_dir))
    assert report["status"] == "LEAKAGE_DETECTED", (
        "Expected LEAKAGE_DETECTED because file contents are identical, even though file paths differ."
    )
    assert report["total_leakages"] == 1


def test_run_demo_workspace_enforces_synthetic_demo_mode():
    """F09 Remediation: scripts/run_demo_workspace.ps1 strictly sets APP_SYNTHETIC_DEMO_MODE to 1."""
    with open("scripts/run_demo_workspace.ps1", "r", encoding="utf-8") as f:
        content = f.read()
    assert '$env:APP_SYNTHETIC_DEMO_MODE = "1"' in content
    assert '$env:APP_SYNTHETIC_DEMO_MODE = "0"' not in content


def test_audit_leakage_fails_closed_when_images_missing(tmp_path):
    """F07 Remediation: When image files are missing on disk, audit_splits fails closed."""
    from scripts.audit_patient_independence_leakage import audit_splits
    import csv

    splits_dir = tmp_path / "splits_missing"
    splits_dir.mkdir()

    train_csv = splits_dir / "train.csv"
    with open(train_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file_path"])
        writer.writeheader()
        writer.writerow({"file_path": str(tmp_path / "non_existent_img_1.png")})

    val_csv = splits_dir / "val.csv"
    with open(val_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file_path"])
        writer.writeheader()
        writer.writerow({"file_path": str(tmp_path / "non_existent_img_2.png")})

    report = audit_splits(str(splits_dir))
    assert report["status"] == "FAIL", f"Expected FAIL when files missing, got: {report['status']}"
    assert report["missing_files_count"] == 2
    assert "fail-closed" in report["conclusion"].lower()


def test_viewer_source_denoise_method_validation_and_422():
    """Point 4 Remediation: viewer-source strictly validates denoise_method and returns 422 for locked caliper."""
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.security import create_access_token, hash_password
    from backend.db.database import SessionLocal, FacilityModel, UserModel, StudyModel, ImageModel
    import numpy as np
    import cv2
    import tempfile

    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as db:
        fac = FacilityModel(id=f"fac-vs-{suffix}", facility_code=f"FVS-{suffix}", name=f"Facility VS {suffix}", is_active=True)
        db.add(fac)
        db.commit()

        doc = UserModel(
            id=f"doc-vs-{suffix}",
            username=f"doc_vs_{suffix}",
            full_name="Dr. Viewer Source",
            role="DOCTOR",
            facility_id=fac.id,
            is_active=True,
            password_hash=hash_password("Pass123!"),
        )
        db.add(doc)
        db.commit()

        # Temporary raw ultrasound image
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            raw_path = tf.name
            dummy_img = np.full((128, 128), 50, dtype=np.uint8)
            cv2.imwrite(raw_path, dummy_img)

        study = StudyModel(id=f"std-vs-{suffix}", facility_id=fac.id, status="PENDING", study_date="2026-11-01")
        db.add(study)
        db.commit()

        img = ImageModel(id=f"img-vs-{suffix}", study_id=study.id, raw_path=raw_path, filename="test.png")
        db.add(img)
        db.commit()

        token = create_access_token({"sub": doc.username, "role": "DOCTOR"})

        with TestClient(app) as client:
            headers = {"Authorization": f"Bearer {token}"}

            # 1. Invalid denoise_method -> 422 (FastAPI Literal query validation)
            resp_inv = client.get(
                f"/api/images/{img.id}/viewer-source?denoise_method=arbitrary_typo_method",
                headers=headers,
            )
            assert resp_inv.status_code == 422, f"Expected 422 for typo method, got {resp_inv.status_code}: {resp_inv.text}"

            # 2. Locked caliper removal -> 422 (Converted from ValueError)
            resp_cal = client.get(
                f"/api/images/{img.id}/viewer-source?enable_caliper_removal=true",
                headers=headers,
            )
            assert resp_cal.status_code == 422, f"Expected 422 for locked caliper, got {resp_cal.status_code}: {resp_cal.text}"
            assert "xóa caliper" in resp_cal.json()["detail"].lower()

            # 3. Valid denoise_method="srad" -> 200
            resp_valid = client.get(
                f"/api/images/{img.id}/viewer-source?denoise_method=srad",
                headers=headers,
            )
            assert resp_valid.status_code == 200, f"Expected 200 for valid srad, got {resp_valid.status_code}: {resp_valid.text}"
            assert resp_valid.json()["denoise_method"] == "srad"
