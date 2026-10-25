"""The same bytes must not be assigned to both views of one study."""

import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.db.database import (
    AuditLogModel,
    Base,
    ImageModel,
    PatientModel,
    PendingFileDeletionModel,
    StudyModel,
    UserModel,
    get_db,
)

pytestmark = pytest.mark.usefixtures("doctor_access")


@pytest.mark.parametrize("remove_first_file", [False, True])
@pytest.mark.parametrize(
    "upload_filename",
    ["../../outside.png", r"..\..\outside.png", "PRIVATE_IDENTIFIER_SENTINEL.png"],
)
def test_identical_image_rejected_within_study(
    tmp_path, monkeypatch, remove_first_file, upload_filename, active_case_lease
):
    from backend.app.main import app
    from backend.app.routers import inference

    engine = create_engine(f"sqlite:///{tmp_path / 'upload.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(UserModel(id="test-doctor", username="doctor", full_name="Test Doctor", role="DOCTOR"))
        db.add(PatientModel(id="patient", anonymized_pid="TEST-DUPLICATE"))
        db.add(StudyModel(id="study", patient_id="patient", study_date="2026-10-08", ovary_side="BOTH"))
        db.commit()
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(tmp_path))
    image = np.full((300, 500), 90, dtype=np.uint8)
    image[60:240, 100:400] = 140
    encoded, buffer = cv2.imencode(".png", image)
    assert encoded
    contents = buffer.tobytes()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            lease = active_case_lease(client, "study")
            headers = {
                "X-Case-Lease-Token": lease["lease_token"],
                "X-Case-Page-Instance-Id": lease["page_instance_id"],
            }
            first = client.post("/api/upload", headers=headers, data={"study_id": "study", "laterality": "R"}, files={"file": (upload_filename, contents, "image/png")})
            assert first.status_code == 200, first.text
            assert "PRIVATE_IDENTIFIER_SENTINEL" not in first.text
            with Session(engine) as db:
                stored = db.get(ImageModel, first.json()["image_id"])
                assert Path(stored.raw_path).resolve().parent == tmp_path.resolve()
                assert "/" not in stored.filename and "\\" not in stored.filename
                assert stored.filename == f"{stored.id}.png"
                assert first.json()["filename"] == stored.filename
                audit = db.query(AuditLogModel).filter_by(
                    entity_name="image", entity_id=stored.id, action_type="UPLOAD_IMAGE"
                ).one()
                assert "filename" not in audit.details
                assert "PRIVATE_IDENTIFIER_SENTINEL" not in json.dumps(audit.details)
            if remove_first_file:
                with Session(engine) as db:
                    Path(db.get(ImageModel, first.json()["image_id"]).raw_path).unlink()
            second = client.post("/api/upload", headers=headers, data={"study_id": "study", "laterality": "L"}, files={"file": ("same.png", contents, "image/png")})
        assert second.status_code == 409
        if remove_first_file:
            assert second.json()["detail"] == "Ảnh này đã tồn tại trong ca khảo sát."
            with Session(engine) as db:
                assert db.query(ImageModel).filter_by(study_id="study").count() == 1
            assert not list(tmp_path.glob("*.png")), "Rejected upload must remove its new file"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_hash_constraint_blocks_two_sessions_after_both_see_no_image(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'race.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(PatientModel(id="patient", anonymized_pid="PID-RACE"))
        db.add(StudyModel(id="study", patient_id="patient", study_date="2026-10-11"))
        db.commit()
    with Session(engine) as first, Session(engine) as second:
        assert first.query(ImageModel).filter_by(study_id="study").count() == 0
        assert second.query(ImageModel).filter_by(study_id="study").count() == 0
        first.add(ImageModel(id="first", study_id="study", filename="a.png", raw_path="a.png", file_hash="a" * 64))
        second.add(ImageModel(id="second", study_id="study", filename="b.png", raw_path="b.png", file_hash="a" * 64))
        first.commit()
        with pytest.raises(IntegrityError):
            second.commit()
        second.rollback()
    engine.dispose()


@pytest.mark.parametrize(
    ("sides", "expected_statuses"),
    [
        (("L", "R"), [200, 200]),
        (("R", "R"), [200, 409]),
    ],
)
def test_laterality_race_commits_expected_bilateral_or_conflict_state(
    tmp_path, monkeypatch, sides, expected_statuses, active_case_lease
):
    from backend.app.main import app
    from backend.app.routers import inference

    engine = create_engine(
        f"sqlite:///{tmp_path / 'laterality-race.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(UserModel(id="test-doctor", username="doctor", full_name="Test Doctor", role="DOCTOR"))
        db.add(PatientModel(id="patient", anonymized_pid="PID-LATERALITY-RACE"))
        db.add(StudyModel(id="study", patient_id="patient", study_date="2026-10-21", ovary_side="BOTH"))
        db.commit()

    monkeypatch.setattr(inference, "UPLOAD_DIR", str(tmp_path))

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    decode_barrier = Barrier(2)
    original_decode = inference.decode_ultrasound_image

    def synchronized_decode(path):
        image = original_decode(path)
        decode_barrier.wait(timeout=10)
        return image

    monkeypatch.setattr(inference, "decode_ultrasound_image", synchronized_decode)

    left = np.full((300, 500), 90, dtype=np.uint8)
    left[60:240, 100:400] = 140
    right = left.copy()
    right[40:210, 130:370] = 170
    left_ok, left_buffer = cv2.imencode(".png", left)
    right_ok, right_buffer = cv2.imencode(".png", right)
    assert left_ok and right_ok

    with TestClient(app) as lease_client:
        lease = active_case_lease(lease_client, "study")
    lease_headers = {
        "X-Case-Lease-Token": lease["lease_token"],
        "X-Case-Page-Instance-Id": lease["page_instance_id"],
    }

    def upload(side, contents):
        with TestClient(app) as client:
            return client.post(
                "/api/upload",
                headers=lease_headers,
                data={"study_id": "study", "laterality": side},
                files={"file": (f"{side}.png", contents, "image/png")},
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            responses = list(workers.map(upload, sides, (left_buffer.tobytes(), right_buffer.tobytes())))
        assert sorted(response.status_code for response in responses) == sorted(expected_statuses), [
            (response.status_code, response.text) for response in responses
        ]
        with Session(engine) as db:
            images = db.query(ImageModel).filter_by(study_id="study").all()
            assert len(images) == expected_statuses.count(200)
            assert {image.laterality for image in images} == {
                side for side, response in zip(sides, responses) if response.status_code == 200
            }
        assert len(list(tmp_path.glob("*.png"))) == expected_statuses.count(200)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_partial_upload_write_failure_removes_file_and_keeps_database_empty(tmp_path, monkeypatch):
    from backend.app.main import app
    from backend.app.routers import inference

    engine = create_engine(f"sqlite:///{tmp_path / 'upload-write-failure.db'}")
    Base.metadata.create_all(engine)

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(tmp_path))
    real_open = open

    class PartialWriter:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *_exc_info):
            self.stream.close()
            return False

        def write(self, contents):
            self.stream.write(contents[:16])
            self.stream.flush()
            raise OSError("simulated disk-full after partial upload write")

    def fail_after_partial_write(path, mode="r", *args, **kwargs):
        if Path(path).resolve().parent == tmp_path.resolve() and mode == "wb":
            return PartialWriter(real_open(path, mode, *args, **kwargs))
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(inference, "open", fail_after_partial_write, raising=False)
    image = np.full((300, 500), 90, dtype=np.uint8)
    encoded, buffer = cv2.imencode(".png", image)
    assert encoded

    try:
        with TestClient(app) as client:
            with pytest.raises(OSError, match="simulated disk-full"):
                client.post(
                    "/api/upload",
                    files={"file": ("partial.png", buffer.tobytes(), "image/png")},
                )

        with Session(engine) as db:
            assert db.query(ImageModel).count() == 0
            assert db.query(AuditLogModel).filter_by(action_type="UPLOAD_IMAGE").count() == 0
        assert not list(tmp_path.glob("*.png")), "A failed partial write must not leave an orphan upload"
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_upload_rollback_failure_still_removes_uncommitted_file(tmp_path, monkeypatch):
    from backend.app.main import app
    from backend.app.routers import inference

    engine = create_engine(f"sqlite:///{tmp_path / 'upload-rollback-failure.db'}")
    Base.metadata.create_all(engine)

    def temporary_db():
        with Session(engine) as db:
            def fail_rollback():
                raise RuntimeError("simulated rollback failure")

            db.rollback = fail_rollback
            yield db

    app.dependency_overrides[get_db] = temporary_db
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(inference, "decode_ultrasound_image", lambda _path: None)
    encoded, buffer = cv2.imencode(".png", np.full((300, 500), 90, dtype=np.uint8))
    assert encoded

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/upload",
                files={"file": ("decode-failure.png", buffer.tobytes(), "image/png")},
            )

        assert response.status_code == 400, response.text
        with Session(engine) as db:
            assert db.query(ImageModel).count() == 0
        assert not list(tmp_path.glob("*.png"))
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_upload_commit_acknowledgement_failure_preserves_committed_file(tmp_path, monkeypatch):
    from backend.app.main import app
    from backend.app.routers import inference

    engine = create_engine(f"sqlite:///{tmp_path / 'upload-commit-ack-failure.db'}")
    Base.metadata.create_all(engine)

    def temporary_db():
        with Session(engine) as db:
            original_commit = db.commit

            def commit_then_lose_acknowledgement():
                original_commit()
                raise RuntimeError("simulated lost commit acknowledgement")

            def fail_rollback():
                raise RuntimeError("simulated rollback failure")

            db.commit = commit_then_lose_acknowledgement
            db.rollback = fail_rollback
            yield db

    app.dependency_overrides[get_db] = temporary_db
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(tmp_path))
    image = np.full((300, 500), 90, dtype=np.uint8)
    image[60:240, 100:400] = 140
    encoded, buffer = cv2.imencode(".png", image)
    assert encoded

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/upload",
                files={"file": ("commit-ack.png", buffer.tobytes(), "image/png")},
            )

        assert response.status_code == 200, response.text
        with Session(engine) as db:
            record = db.query(ImageModel).one()
            assert Path(record.raw_path).exists()
            assert record.file_hash == hashlib.sha256(buffer.tobytes()).hexdigest()
        assert len(list(tmp_path.glob("*.png"))) == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_upload_file_cleanup_failure_is_queued_for_retry(tmp_path, monkeypatch):
    from backend.app.main import app
    from backend.app.routers import inference
    from backend.services import file_deletion_service

    engine = create_engine(f"sqlite:///{tmp_path / 'upload-cleanup-outbox.db'}")
    Base.metadata.create_all(engine)

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(inference, "decode_ultrasound_image", lambda _path: None)
    real_remove = inference.os.remove

    def fail_upload_remove(path):
        if Path(path).resolve().parent == tmp_path.resolve():
            raise PermissionError("simulated upload file lock")
        real_remove(path)

    monkeypatch.setattr(inference.os, "remove", fail_upload_remove)
    real_unlink = Path.unlink

    def fail_upload_unlink(path, *args, **kwargs):
        if path.resolve().parent == tmp_path.resolve() and path.suffix == ".png":
            raise PermissionError("simulated persistent upload file lock")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(file_deletion_service.Path, "unlink", fail_upload_unlink)
    image = np.full((300, 500), 90, dtype=np.uint8)
    encoded, buffer = cv2.imencode(".png", image)
    assert encoded

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/upload",
                files={"file": ("locked.png", buffer.tobytes(), "image/png")},
            )

        assert response.status_code == 400
        with Session(engine) as db:
            assert db.query(ImageModel).count() == 0
            pending = db.query(PendingFileDeletionModel).one()
            deletion_id = pending.id
            relative_path = pending.relative_path
        staged_path = tmp_path / relative_path
        assert staged_path.exists()

        monkeypatch.setattr(file_deletion_service.Path, "unlink", real_unlink)
        with Session(engine) as db:
            assert file_deletion_service.retry_pending_file_deletions(
                db, tmp_path, [deletion_id]
            ) is False
            assert db.query(PendingFileDeletionModel).count() == 0
        assert not staged_path.exists()
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_double_upload_cleanup_failure_emits_critical_log_without_file_path(
    tmp_path, monkeypatch, caplog
):
    import logging

    from backend.app.main import app
    from backend.app.routers import inference

    engine = create_engine(f"sqlite:///{tmp_path / 'upload-double-cleanup-failure.db'}")
    Base.metadata.create_all(engine)

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    monkeypatch.setattr(inference, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(inference, "decode_ultrasound_image", lambda _path: None)
    real_remove = inference.os.remove

    def fail_remove(path):
        if Path(path).resolve().parent == tmp_path.resolve() and Path(path).suffix == ".png":
            raise PermissionError("simulated upload file lock")
        real_remove(path)

    monkeypatch.setattr(inference.os, "remove", fail_remove)

    def fail_outbox(*_args, **_kwargs):
        raise RuntimeError("simulated database unavailable")

    monkeypatch.setattr(inference, "enqueue_upload_deletions", fail_outbox)
    image = np.full((300, 500), 90, dtype=np.uint8)
    encoded, buffer = cv2.imencode(".png", image)
    assert encoded

    try:
        with caplog.at_level(logging.CRITICAL, logger="backend.app.routers.inference"):
            with TestClient(app) as client:
                response = client.post(
                    "/api/upload",
                    files={"file": ("double-failure.png", buffer.tobytes(), "image/png")},
                )

        assert response.status_code == 400
        record = next(
            (
                item
                for item in caplog.records
                if getattr(item, "upload_cleanup_double_failure", False)
            ),
            None,
        )
        assert record is not None
        assert "double-failure.png" not in record.getMessage()
        assert len(list(tmp_path.glob("*.png"))) == 1
    finally:
        for path in tmp_path.glob("*.png"):
            real_remove(path)
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_upload_rejects_lease_expired_during_decode_and_cleans_staged_file(
    tmp_path, monkeypatch, active_case_lease
):
    from datetime import UTC, datetime

    from backend.app.main import app
    from backend.app.routers import inference
    from backend.services import case_lease_service

    engine = create_engine(
        f"sqlite:///{tmp_path / 'lease-expiry-upload.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(UserModel(id="test-doctor", username="doctor", full_name="Test Doctor", role="DOCTOR"))
        db.add(PatientModel(id="patient", anonymized_pid="PID-LEASE-EXPIRY-UPLOAD"))
        db.add(StudyModel(id="study", patient_id="patient", study_date="2026-10-21", ovary_side="BOTH"))
        db.commit()

    monkeypatch.setattr(inference, "UPLOAD_DIR", str(tmp_path))

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    try:
        with TestClient(app) as client:
            lease = active_case_lease(client, "study")
            original_decode = inference.decode_ultrasound_image

            def expire_lease_after_decode(path):
                image = original_decode(path)
                future = datetime(2099, 1, 1, tzinfo=UTC).replace(tzinfo=None)
                monkeypatch.setattr(case_lease_service, "_now", lambda: future)
                return image

            monkeypatch.setattr(inference, "decode_ultrasound_image", expire_lease_after_decode)
            image = np.full((300, 500), 90, dtype=np.uint8)
            image[60:240, 100:400] = 140
            encoded, buffer = cv2.imencode(".png", image)
            assert encoded
            response = client.post(
                "/api/upload",
                headers={
                    "X-Case-Lease-Token": lease["lease_token"],
                    "X-Case-Page-Instance-Id": lease["page_instance_id"],
                },
                data={"study_id": "study", "laterality": "R"},
                files={"file": ("lease-expiry.png", buffer.tobytes(), "image/png")},
            )

        assert response.status_code == 423
        with Session(engine) as db:
            assert db.query(ImageModel).filter_by(study_id="study").count() == 0
            assert db.query(AuditLogModel).filter_by(action_type="UPLOAD_IMAGE").count() == 0
        assert not list(tmp_path.glob("*.png"))
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_legacy_images_gain_hash_index_without_deleting_duplicates(tmp_path, monkeypatch):
    from backend.db import database

    path = tmp_path / "legacy.db"
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    first.write_bytes(b"same image bytes")
    second.write_bytes(first.read_bytes())
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE images(id TEXT PRIMARY KEY, study_id TEXT, raw_path TEXT)")
        db.executemany("INSERT INTO images(id, study_id, raw_path) VALUES (?, 'study', ?)",
                       [("first", str(first)), ("second", str(second))])
    engine = create_engine(f"sqlite:///{path}")
    monkeypatch.setattr(database, "DB_PATH", str(path))
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    try:
        database.init_db()
        database.init_db()
        with sqlite3.connect(path) as db:
            rows = db.execute("SELECT id, file_hash FROM images ORDER BY id").fetchall()
            digest = hashlib.sha256(first.read_bytes()).hexdigest()
            assert [row[0] for row in rows] == ["first", "second"]
            assert sorted(row[1] for row in rows if row[1]) == [digest]
            with pytest.raises(sqlite3.IntegrityError):
                db.execute("INSERT INTO images(id, study_id, raw_path, file_hash) VALUES (?, ?, ?, ?)",
                           ("third", "study", str(first), digest))
    finally:
        engine.dispose()
