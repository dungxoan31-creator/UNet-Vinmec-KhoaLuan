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
import struct
import uuid
import zlib

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


def test_upload_rejects_oversized_decoded_raster_before_decode(
    tmp_path, monkeypatch, client, doctor_headers, db
):
    from backend.app.routers import inference
    from backend.db.database import ImageModel

    source = io.BytesIO()
    Image.new("L", (1, 1), color=128).save(source, format="PNG")
    contents = bytearray(source.getvalue())
    struct.pack_into(">II", contents, 16, 10_000, 10_000)
    struct.pack_into(">I", contents, 29, zlib.crc32(contents[12:29]) & 0xFFFFFFFF)
    decode_calls = []
    original_decode = inference.decode_ultrasound_image

    def track_decode(path):
        decode_calls.append(path)
        return original_decode(path)

    monkeypatch.setattr(inference, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(inference, "decode_ultrasound_image", track_decode)
    before_images = db.query(ImageModel).count()

    response = client.post(
        "/api/upload",
        files={"file": ("oversized-dimensions.png", bytes(contents), "image/png")},
        headers=doctor_headers,
    )

    assert response.status_code == 413, response.text
    assert "25 triệu pixels" in response.json()["detail"]
    assert decode_calls == [], "Header dimensions must be checked before raster decode."
    assert db.query(ImageModel).count() == before_images
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(("extension", "image_format", "media_type"), [
    ("png", "PNG", "image/png"),
    ("jpg", "JPEG", "image/jpeg"),
])
def test_upload_accepts_supported_png_and_jpeg(
    tmp_path, monkeypatch, doctor_access, extension, image_format, media_type
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.main import app
    from backend.app.routers import inference
    from backend.db.database import Base, ImageModel, get_db

    engine = create_engine(
        f"sqlite:///{tmp_path / 'valid-raster.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(tmp_path / "uploads"))
    image_dir = tmp_path / "uploads"
    image_dir.mkdir()

    def temporary_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = temporary_db
    try:
        source = io.BytesIO()
        Image.new("L", (128, 96), color=112).save(source, format=image_format)
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/upload",
                files={"file": (f"valid.{extension}", source.getvalue(), media_type)},
            )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["dimensions"] == [128, 96]
        with Session(engine) as session:
            stored = session.get(ImageModel, payload["image_id"])
            assert stored is not None
            assert stored.raw_path.endswith(f".{extension}")
            assert os.path.isfile(stored.raw_path)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_intake_metadata_rejects_oversized_decoded_raster_before_decode(
    client, doctor_headers, monkeypatch
):
    from backend.app.routers import inference

    source = io.BytesIO()
    Image.new("L", (1, 1), color=128).save(source, format="PNG")
    contents = bytearray(source.getvalue())
    struct.pack_into(">II", contents, 16, 6_000, 5_000)
    struct.pack_into(">I", contents, 29, zlib.crc32(contents[12:29]) & 0xFFFFFFFF)
    decode_calls = []

    def track_decode(path):
        decode_calls.append(path)
        return None

    monkeypatch.setattr(inference, "decode_ultrasound_image", track_decode)
    response = client.post(
        "/api/intake/extract-metadata",
        files={"file": ("oversized-intake.png", bytes(contents), "image/png")},
        headers=doctor_headers,
    )

    assert response.status_code == 413, response.text
    assert "25 triệu pixels" in response.json()["detail"]
    assert decode_calls == [], "Intake metadata must not decode or propose metadata for oversized rasters."


@pytest.mark.parametrize(
    "untrusted_filename",
    ["../../outside.png", r"..\..\outside.png", r"C:\outside.png"],
)
def test_upload_stores_uuid_filename_inside_upload_root(
    tmp_path, monkeypatch, doctor_access, untrusted_filename
):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.app.main import app
    from backend.app.routers import inference
    from backend.db.database import Base, ImageModel, get_db

    engine = create_engine(
        f"sqlite:///{tmp_path / 'filename-boundary.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(upload_root))

    def temporary_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = temporary_db
    source = io.BytesIO()
    Image.new("L", (64, 48), color=112).save(source, format="PNG")
    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/upload",
                files={"file": (untrusted_filename, source.getvalue(), "image/png")},
            )

        assert response.status_code == 200, response.text
        payload = response.json()
        with Session(engine) as session:
            stored = session.get(ImageModel, payload["image_id"])
            assert stored is not None
            assert stored.raw_path == str(upload_root / stored.filename)
            assert stored.filename == os.path.basename(stored.raw_path)
            assert stored.filename.endswith(".png")
        assert payload["filename"] == stored.filename
        assert len(list(upload_root.iterdir())) == 1
        assert not (tmp_path / "outside.png").exists()
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


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


def test_research_export_stays_disabled_without_disclosing_study_state(client, doctor_headers):
    payload = {
        "review_ids": [str(uuid.uuid4())],
        "expected_revision": 0,
        "ethics_approval_code": "UNVERIFIED-USER-INPUT",
        "patient_consent_confirmed": True,
    }
    resp = client.post(f"/api/cases/{uuid.uuid4()}/research-export", json=payload, headers=doctor_headers)
    assert resp.status_code == 501


def test_prediction_failure_preserves_db_rowcount(client, doctor_headers, db):
    initial_predictions = db.query(PredictionModel).count()
    initial_reviews = db.query(ReviewModel).count()

    # Trigger failed prediction
    resp = client.post(f"/api/predict/{uuid.uuid4()}", headers=doctor_headers)
    assert resp.status_code == 404

    # Assert row counts completely unchanged
    assert db.query(PredictionModel).count() == initial_predictions
    assert db.query(ReviewModel).count() == initial_reviews
