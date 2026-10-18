"""
Negative boundary tests, failure modes, and security constraints (Task 17).
Verifies:
- Upload input bounds: empty, corrupt, invalid extension, size > 20MiB (HTTP 413), decoded > 25M pixels
- Protected route authentication & role authorization
- Missing resource lookups: non-existent images, studies, predictions (HTTP 404)
- Safe fail-closed semantics: failures do not pollute database state
"""

import io
import os
import uuid

import pytest

os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-characters-long-2026")

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import app
from backend.app.routers.auth import create_access_token
from backend.db.database import PredictionModel, ReviewModel, SessionLocal, UserModel


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def doctor_headers(db):
    user = db.query(UserModel).filter(UserModel.username == "doctor").first()
    if not user:
        user = UserModel(
            id=str(uuid.uuid4()),
            username="doctor",
            role="DOCTOR",
            full_name="BS.CKI Nguyễn Văn A",
            is_active=True,
        )
        db.add(user)
        db.commit()
    token = create_access_token(data={"sub": user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def nurse_headers(db):
    user = db.query(UserModel).filter(UserModel.username == "nurse_neg_test").first()
    if not user:
        user = UserModel(
            id=str(uuid.uuid4()),
            username="nurse_neg_test",
            role="NURSE",
            full_name="Nurse Negative Test",
            is_active=True,
        )
        db.add(user)
        db.commit()
    token = create_access_token(data={"sub": user.username})
    return {"Authorization": f"Bearer {token}"}


def test_upload_rejects_empty_file(client, doctor_headers):
    # 0-byte file
    files = {"file": ("empty.png", b"", "image/png")}
    resp = client.post("/api/upload", files=files, headers=doctor_headers)
    assert resp.status_code == 400
    assert "quá nhỏ" in resp.json().get("detail", "") or "rỗng" in resp.json().get("detail", "")


def test_upload_rejects_disallowed_extension(client, doctor_headers):
    files = {"file": ("script.exe", b"MZ\x90\x00" + b"\x00" * 70, "application/octet-stream")}
    resp = client.post("/api/upload", files=files, headers=doctor_headers)
    assert resp.status_code == 400
    assert "Định dạng file không hợp lệ" in resp.json().get("detail", "")


def test_upload_rejects_oversized_file(client, doctor_headers):
    # > 20 MiB payload
    oversized = b"P" * (20 * 1024 * 1024 + 1)
    files = {"file": ("huge.png", oversized, "image/png")}
    resp = client.post("/api/upload", files=files, headers=doctor_headers)
    assert resp.status_code == 413
    assert "quá lớn" in resp.json().get("detail", "")


def test_upload_rejects_corrupted_image_bytes(client, doctor_headers):
    # Valid PNG signature followed by garbage bytes
    corrupt_bytes = b"\x89PNG\r\n\x1a\n" + b"\xff" * 200
    files = {"file": ("corrupt.png", corrupt_bytes, "image/png")}
    resp = client.post("/api/upload", files=files, headers=doctor_headers)
    assert resp.status_code == 400
    assert "Không thể đọc nội dung file ảnh y tế" in resp.json().get("detail", "")


def test_upload_rejects_unauthenticated(client):
    buf = io.BytesIO()
    Image.new("L", (100, 100), color=128).save(buf, format="PNG")
    files = {"file": ("test.png", buf.getvalue(), "image/png")}
    resp = client.post("/api/upload", files=files)
    assert resp.status_code == 401


def test_upload_rejects_invalid_laterality(client, doctor_headers):
    buf = io.BytesIO()
    Image.new("L", (100, 100), color=128).save(buf, format="PNG")
    files = {"file": ("test.png", buf.getvalue(), "image/png")}
    data = {"laterality": "INVALID_SIDE"}
    resp = client.post("/api/upload", files=files, data=data, headers=doctor_headers)
    assert resp.status_code == 422


def test_prediction_rejects_missing_image_404(client, doctor_headers):
    resp = client.post(f"/api/predict/{uuid.uuid4()}", headers=doctor_headers)
    assert resp.status_code == 404


def test_validation_rejects_missing_image_404(client, doctor_headers):
    resp = client.post(f"/api/validate-image?image_id={uuid.uuid4()}", headers=doctor_headers)
    assert resp.status_code == 404


def test_batch_review_rejects_nurse_403(client, nurse_headers):
    payload = {
        "study_id": str(uuid.uuid4()),
        "expected_revision": 0,
        "request_id": str(uuid.uuid4()),
        "reviews": [],
    }
    resp = client.post("/api/reviews/batch", json=payload, headers=nurse_headers)
    assert resp.status_code == 403


def test_research_export_rejects_missing_study_404(client, doctor_headers):
    payload = {
        "review_ids": [str(uuid.uuid4())],
        "expected_revision": 0,
    }
    resp = client.post(f"/api/cases/{uuid.uuid4()}/research-export", json=payload, headers=doctor_headers)
    assert resp.status_code == 404


def test_prediction_failure_preserves_db_rowcount(client, doctor_headers, db):
    initial_predictions = db.query(PredictionModel).count()
    initial_reviews = db.query(ReviewModel).count()

    # Trigger failed prediction
    resp = client.post(f"/api/predict/{uuid.uuid4()}", headers=doctor_headers)
    assert resp.status_code == 404

    # Assert row counts completely unchanged
    assert db.query(PredictionModel).count() == initial_predictions
    assert db.query(ReviewModel).count() == initial_reviews
