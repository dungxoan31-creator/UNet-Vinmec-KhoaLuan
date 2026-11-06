from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.security import hash_password
from backend.db.database import (
    Base,
    ImageModel,
    PredictionModel,
    ReviewModel,
    StudyModel,
    UserModel,
    get_db,
)


def test_admin_analytics_summary_and_doctor_stats(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-secret-for-admin-reports-123456")
    monkeypatch.setenv("APP_ADMIN_PASSWORD", "admin-test-pass")
    monkeypatch.setenv("APP_DOCTOR_PASSWORD", "doctor-test-pass")

    from backend.app.main import app

    engine = create_engine(
        f"sqlite:///{tmp_path / 'admin-reports.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        admin_user = UserModel(
            id="admin-1",
            username="admin",
            full_name="Quản trị viên",
            role="ADMIN",
            password_hash=hash_password("admin-test-pass"),
        )
        doctor_user = UserModel(
            id="doc-1",
            username="doctor",
            full_name="BS.CKI Nguyễn Văn A",
            role="DOCTOR",
            department="Khoa Chẩn đoán Hình ảnh",
            password_hash=hash_password("doctor-test-pass"),
        )
        inactive_doctor = UserModel(
            id="doc-2",
            username="doctor-no-reviews",
            full_name="BS chưa có lượt rà soát",
            role="DOCTOR",
            password_hash=hash_password("doctor-test-pass"),
        )
        study = StudyModel(
            id="study-1",
            study_code="CA-2026-001",
            study_date="2026-11-01",
            status="REVIEWED",
        )
        img1 = ImageModel(
            id="img-1",
            study_id="study-1",
            filename="us_01.png",
            raw_path="uploads/us_01.png",
            file_hash="hash123",
            laterality="L",
        )
        pred1 = PredictionModel(
            id="pred-1",
            image_id="img-1",
            iqa_score=0.85,
            confidence_score=0.92,
            raw_mask_rle={"counts": [10, 20]},
            measurements={"has_lesion": True},
        )
        review1 = ReviewModel(
            id="rev-1",
            image_id="img-1",
            prediction_id="pred-1",
            doctor_id="doctor",
            doctor_action="ACCEPTED_RAW",
            verified_mask_rle={"counts": [10, 20]},
            lesion_type="U quái (Dermoid cyst)",
            max_diameter_mm=25.4,
            ortho_diameter_mm=18.2,
            time_spent_seconds=65,
            hitl_feedback={"orads": "O-RADS 2", "orads_score": "O-RADS 2", "lesion_type": "teratoma"},
        )
        db.add_all([admin_user, doctor_user, inactive_doctor, study, img1, pred1, review1])
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db

    try:
        with TestClient(app) as client:
            # 1. Login as Admin
            admin_login = client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin-test-pass"},
            )
            assert admin_login.status_code == 200
            admin_token = admin_login.json()["access_token"]
            admin_headers = {"Authorization": f"Bearer {admin_token}"}

            # 2. Test GET /api/admin/analytics/summary
            summary_res = client.get("/api/admin/analytics/summary", headers=admin_headers)
            assert summary_res.status_code == 200
            summary = summary_res.json()
            assert summary["total_cases"] == 1
            assert summary["completed_cases"] == 1
            assert summary["total_images"] == 1
            assert summary["total_predictions"] == 1
            assert summary["total_reviews"] == 1
            assert summary["overall_consensus_rate_pct"] == 100.0
            assert summary["avg_iqa_score"] == 0.85
            assert summary["iqa_pass_rate_pct"] == 100.0
            assert summary["iqa_scored_count"] == 1
            assert summary["active_doctors_count"] == 1
            assert summary["orads_distribution"]["O-RADS 2"] == 1
            assert summary["lesion_distribution"]["U quái (Dermoid cyst)"] == 1
            assert summary["action_distribution"]["ACCEPTED_RAW"] == 1
            assert summary["iqa_tiers"]["Xuất sắc (≥ 0.8)"] == 1
            assert isinstance(summary["timeline_trend"], list)
            assert len(summary["timeline_trend"]) > 0
            assert "Tiền mãn kinh (Pre-menopausal)" in summary["demographics"]
            assert summary["avg_review_seconds"] == 65.0
            assert summary["review_duration_count"] == 1
            assert "generated_at" in summary

            # Test summary with filters
            filtered_summary = client.get("/api/admin/analytics/summary?days=30&status=REVIEWED&doctor_id=doctor", headers=admin_headers)
            assert filtered_summary.status_code == 200
            assert filtered_summary.json()["total_cases"] == 1

            empty_summary = client.get("/api/admin/analytics/summary?days=30&status=PENDING", headers=admin_headers)
            assert empty_summary.status_code == 200
            empty_metrics = empty_summary.json()
            assert empty_metrics["total_cases"] == 0
            assert empty_metrics["overall_consensus_rate_pct"] is None
            assert empty_metrics["avg_iqa_score"] is None
            assert empty_metrics["iqa_pass_rate_pct"] is None
            assert empty_metrics["avg_review_seconds"] is None
            assert empty_metrics["iqa_scored_count"] == 0
            assert empty_metrics["review_duration_count"] == 0

            # 3. Test Drill-Down cases list
            drilldown_all = client.get("/api/admin/reports/cases", headers=admin_headers)
            assert drilldown_all.status_code == 200
            cases_all = drilldown_all.json()
            assert len(cases_all) == 1
            assert cases_all[0]["study_code"] == "CA-2026-001"
            assert cases_all[0]["orads"] == "O-RADS 2"
            assert cases_all[0]["lesion_type"] == "U quái (Dermoid cyst)"
            assert cases_all[0]["measurements_summary"] == "25.4 × 18.2 mm"
            assert cases_all[0]["doctor_name"] == "BS.CKI Nguyễn Văn A"

            # Filter by ORADS matching
            drilldown_orads = client.get("/api/admin/reports/cases?orads=O-RADS 2", headers=admin_headers)
            assert drilldown_orads.status_code == 200
            assert len(drilldown_orads.json()) == 1

            # Filter by ORADS not matching
            drilldown_none = client.get("/api/admin/reports/cases?orads=O-RADS 5", headers=admin_headers)
            assert drilldown_none.status_code == 200
            assert len(drilldown_none.json()) == 0

            # Filter by Lesion Type
            drilldown_lesion = client.get("/api/admin/reports/cases?lesion_type=Dermoid", headers=admin_headers)
            assert drilldown_lesion.status_code == 200
            assert len(drilldown_lesion.json()) == 1

            # Filter by Days and Status
            drilldown_filtered = client.get("/api/admin/reports/cases?days=30&status=REVIEWED&doctor_id=doctor", headers=admin_headers)
            assert drilldown_filtered.status_code == 200
            assert len(drilldown_filtered.json()) == 1

            drilldown_empty = client.get("/api/admin/reports/cases?days=30&status=PENDING", headers=admin_headers)
            assert drilldown_empty.status_code == 200
            assert len(drilldown_empty.json()) == 0

            # Export drilldown cases to CSV
            drilldown_csv = client.get("/api/admin/reports/cases/export-csv?orads=O-RADS 2", headers=admin_headers)
            assert drilldown_csv.status_code == 200
            assert "text/csv" in drilldown_csv.headers["content-type"]
            csv_content = drilldown_csv.content.decode("utf-8")
            assert "CA-2026-001" in csv_content
            assert "O-RADS 2" in csv_content
            assert "U quái (Dermoid cyst)" in csv_content

            # 4. Test GET /api/admin/doctor-stats
            doc_stats_res = client.get("/api/admin/doctor-stats", headers=admin_headers)
            assert doc_stats_res.status_code == 200
            doc_stats = doc_stats_res.json()
            assert len(doc_stats) >= 1
            doc_item = next((d for d in doc_stats if d["doctor_id"] == "doc-1"), None)
            assert doc_item is not None
            assert doc_item["doctor_name"] == "BS.CKI Nguyễn Văn A"
            assert doc_item["signed_count"] == 1
            assert doc_item["raw_accepted_count"] == 1
            assert doc_item["modified_count"] == 0
            assert doc_item["consensus_rate_pct"] == 100.0
            assert doc_item["avg_review_seconds"] == 65.0
            assert doc_item["review_duration_count"] == 1
            no_review_item = next((d for d in doc_stats if d["doctor_id"] == "doc-2"), None)
            assert no_review_item is not None
            assert no_review_item["consensus_rate_pct"] is None
            assert no_review_item["avg_review_seconds"] is None
            assert no_review_item["review_duration_count"] == 0

            with Session(engine) as db:
                db.query(PredictionModel).filter_by(id="pred-1").update({"iqa_score": 0.0})
                db.query(ReviewModel).filter_by(id="rev-1").update({
                    "doctor_action": "MODIFIED",
                    "time_spent_seconds": 0,
                })
                db.commit()
            measured_zero = client.get("/api/admin/analytics/summary", headers=admin_headers)
            assert measured_zero.status_code == 200
            zero_metrics = measured_zero.json()
            assert zero_metrics["iqa_scored_count"] == 1
            assert zero_metrics["avg_iqa_score"] == 0.0
            assert zero_metrics["iqa_pass_rate_pct"] == 0.0
            assert zero_metrics["overall_consensus_rate_pct"] == 0.0
            assert zero_metrics["review_duration_count"] == 1
            assert zero_metrics["avg_review_seconds"] == 0.0

            # 5. Test Doctor isolation: Doctor cannot access admin reports
            doc_login = client.post(
                "/api/auth/login",
                json={"username": "doctor", "password": "doctor-test-pass"},
            )
            assert doc_login.status_code == 200
            doc_token = doc_login.json()["access_token"]
            doc_headers = {"Authorization": f"Bearer {doc_token}"}

            forbidden_summary = client.get("/api/admin/analytics/summary", headers=doc_headers)
            assert forbidden_summary.status_code == 403

            forbidden_cases = client.get("/api/admin/reports/cases", headers=doc_headers)
            assert forbidden_cases.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
