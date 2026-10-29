"""Clinical records and images require an authenticated account."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.database import Base, UserModel, get_db


def test_clinical_api_requires_token_and_doctor_can_read_cases(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-long-random-signing-secret-123456")
    monkeypatch.setenv("APP_DOCTOR_PASSWORD", "doctor-test-password")
    from backend.app.main import app

    engine = create_engine(f"sqlite:///{tmp_path / 'protected.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(UserModel(id="doctor-id", username="doctor", full_name="Doctor", role="DOCTOR"))
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            prompt_payload = {"image_id": "any-image-id", "box": [0, 0, 8, 8]}
            for method, path in [
                ("GET", "/api/cases"),
                ("GET", "/api/stats"),
                ("POST", "/api/upload"),
                ("POST", "/api/review"),
                ("POST", "/api/v1/cdss/evaluate"),
                ("GET", "/api/evaluation/metrics"),
                ("GET", "/api/images/missing/viewer-source"),
                ("GET", "/api/notifications"),
                ("POST", "/api/notifications/read"),
                ("GET", "/api/v1/clinical-templates"),
                ("POST", "/api/v1/clinical-templates/apply"),
            ]:
                assert client.request(method, path).status_code == 401, path
            assert client.post(
                "/api/v1/inference/interactive-prompt", json=prompt_payload
            ).status_code == 401

            from backend.app.security import create_access_token

            cookie_only_token = create_access_token({"sub": "doctor", "uid": "doctor-id"})
            client.cookies.set("access_token", cookie_only_token)
            cookie_only = client.get("/api/cases")
            client.cookies.delete("access_token")
            assert cookie_only.status_code == 401, "Authentication must not accept ambient cookies."

            login = client.post("/api/auth/login", json={"username": "doctor", "password": "doctor-test-password"})
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            assert client.get("/api/cases", headers=headers).status_code == 200
            assert client.get("/api/stats", headers=headers).status_code == 200
            assert client.get("/api/notifications", headers=headers).json() == []
            empty_read = client.post("/api/notifications/read", headers=headers, json={"ids": []})
            assert empty_read.json() == {"status": "NOOP", "updated": 0}
            unsupported_read = client.post(
                "/api/notifications/read", headers=headers, json={"ids": ["notification-id"]}
            )
            assert unsupported_read.status_code == 501
            assert client.get("/api/health").status_code == 200
            assert client.get("/data/anything.png").status_code == 404
            foreign = client.get("/api/health", headers={"Origin": "https://untrusted.example"})
            assert "access-control-allow-origin" not in foreign.headers

            # UAT-04: Admin token must be forbidden (403) from accessing clinical details and images
            with Session(engine) as db:
                db.add(UserModel(id="admin-id", username="admin", full_name="Admin", role="ADMIN"))
                db.commit()
            monkeypatch.setenv("APP_ADMIN_PASSWORD", "admin-test-password")
            admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin-test-password"})
            assert admin_login.status_code == 200
            admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
            assert client.post(
                "/api/v1/inference/interactive-prompt",
                headers=admin_headers,
                json=prompt_payload,
            ).status_code == 403

            import cv2
            import numpy as np

            from backend.app.routers import inference as inference_router

            upload_dir = tmp_path / "admin-upload-attempts"
            upload_dir.mkdir()
            monkeypatch.setattr(inference_router, "UPLOAD_DIR", str(upload_dir))
            encoded, image_bytes = cv2.imencode(
                ".png", np.full((128, 128), 127, dtype=np.uint8)
            )
            assert encoded
            upload_response = client.post(
                "/api/upload",
                headers=admin_headers,
                data={"anonymized_pid": "ADMIN-MUST-NOT-CREATE-PATIENT"},
                files={"file": ("standalone.png", image_bytes.tobytes(), "image/png")},
            )
            assert upload_response.status_code == 403, upload_response.text
            assert list(upload_dir.iterdir()) == []
            with Session(engine) as db:
                from backend.db.database import ImageModel, PatientModel, StudyModel

                assert db.query(PatientModel).count() == 0
                assert db.query(StudyModel).count() == 0
                assert db.query(ImageModel).count() == 0

            for method, path in [
                ("GET", "/api/cases"),
                ("GET", "/api/workspace/cases"),
                ("POST", "/api/workspace/cases/search"),
                ("GET", "/api/workspace/dashboard/summary?date=2026-10-26"),
                ("POST", "/api/v1/cdss/evaluate"),
                ("GET", "/api/v1/clinical-templates"),
                ("POST", "/api/v1/clinical-templates/apply"),
                ("GET", "/api/evaluation/samples/43/workstation-bundle"),
                ("GET", "/api/evaluation/samples/43/download/image"),
            ]:
                assert client.request(method, path, headers=admin_headers, json={}).status_code == 403, path

            assert client.get("/api/cases/any-study-id", headers=admin_headers).status_code == 403
            assert client.get("/api/images/any-image-id/source.png", headers=admin_headers).status_code == 403
            assert client.get("/api/images/any-image-id/viewer-source", headers=admin_headers).status_code == 403
            assert client.get("/api/images/any-image-id/mask.png", headers=admin_headers).status_code == 403
            valid_mask_rle = {"shape": [512, 512], "counts": [512 * 512], "first_val": 0}
            assert (
                client.post(
                    "/api/images/any-image-id/measurements",
                    headers=admin_headers,
                    json={"rle_mask": valid_mask_rle},
                ).status_code
                == 403
            )
            assert (
                client.post(
                    "/api/images/any-image-id/calibrate?distance_mm=10&distance_pixels=20",
                    headers=admin_headers,
                ).status_code
                == 403
            )
            admin_lease_request = {
                "tab_id": "admin-tab-lease-1234",
                "page_instance_id": "admin-page-instance-1234",
            }
            assert (
                client.post(
                    "/api/workspace/cases/any-study-id/lease",
                    headers=admin_headers,
                    json=admin_lease_request,
                ).status_code
                == 403
            )
            assert (
                client.request(
                    "DELETE",
                    "/api/workspace/cases/any-study-id/lease",
                    headers=admin_headers,
                    json={"lease_token": "a" * 32, "page_instance_id": admin_lease_request["page_instance_id"]},
                ).status_code
                == 403
            )
            for method, path in [
                ("POST", "/api/upload"),
                ("POST", "/api/validate-image?image_id=any-image-id"),
                ("POST", "/api/predict/any-image-id"),
            ]:
                response = client.request(method, path, headers=admin_headers)
                assert response.status_code == 403, (path, response.status_code, response.text)

            valid_mask = {"shape": [512, 512], "counts": [512 * 512], "first_val": 0}
            valid_review = {
                "image_id": "image-id",
                "study_id": "study-id",
                "prediction_id": "prediction-id",
                "verified_mask_rle": valid_mask,
                "expected_revision": 0,
                "request_id": "admin-review-request",
            }
            for method, path, body in [
                (
                    "POST",
                    "/api/reviews/batch",
                    {
                        "study_id": "study-id",
                        "expected_revision": 0,
                        "request_id": "admin-batch-request",
                        "reviews": [valid_review],
                    },
                ),
                ("POST", "/api/review", valid_review),
                (
                    "POST",
                    "/api/hitl/sessions",
                    {"study_id": "study-id", "participant_code": "admin-test"},
                ),
                ("GET", "/api/hitl/sessions/other-user-session", None),
                ("GET", "/api/evaluation/samples", None),
            ]:
                response = client.request(method, path, headers=admin_headers, json=body)
                assert response.status_code == 403, (path, response.status_code, response.text)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
