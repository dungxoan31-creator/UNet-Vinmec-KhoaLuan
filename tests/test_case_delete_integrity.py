"""Deleting a case must keep database and upload cleanup recoverable."""

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.routers import cases
from backend.db.database import (
    AuditLogModel,
    Base,
    ImageModel,
    PatientModel,
    PredictionModel,
    ReviewModel,
    StudyModel,
)


def _case_database(tmp_path, image_paths, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(exist_ok=True)
    monkeypatch.setattr(cases, "UPLOAD_DIR", str(upload_dir), raising=False)

    engine = create_engine(f"sqlite:///{tmp_path / 'case-delete.sqlite3'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    with sessions() as db:
        patient = PatientModel(id="patient-1", anonymized_pid="PID-1")
        study = StudyModel(id="study-1", patient=patient, study_date="2026-10-18")
        db.add(study)
        db.flush()
        for index, path in enumerate(image_paths):
            db.add(
                ImageModel(
                    id=f"image-{index}",
                    study_id=study.id,
                    filename=Path(path).name,
                    raw_path=str(path),
                )
            )
        db.commit()
    return engine, sessions, "study-1"


def _delete_case(study_id, db):
    return cases.delete_case(
        study_id,
        current_user=SimpleNamespace(username="test-admin"),
        db=db,
    )


def test_delete_preserves_case_and_upload_when_database_commit_fails(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    image = upload_dir / "image.png"
    image.write_bytes(b"image")
    engine, sessions, study_id = _case_database(tmp_path, [image], monkeypatch)
    try:
        with sessions() as db:
            def fail_commit():
                raise RuntimeError("simulated commit failure")

            monkeypatch.setattr(db, "commit", fail_commit)
            with pytest.raises(RuntimeError, match="commit failure"):
                _delete_case(study_id, db)
            db.rollback()

        with sessions() as db:
            assert db.get(StudyModel, study_id) is not None
            assert db.query(ImageModel).filter(ImageModel.study_id == study_id).count() == 1
            assert (
                db.query(AuditLogModel)
                .filter(AuditLogModel.action_type == "CLINICAL_CASE_DELETE")
                .count()
                == 0
            )
        assert image.exists()
    finally:
        engine.dispose()


def test_delete_rollback_failure_does_not_mask_uncommitted_commit_error(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    image = upload_dir / "image.png"
    image.write_bytes(b"image")
    engine, sessions, study_id = _case_database(tmp_path, [image], monkeypatch)
    try:
        with sessions() as db:
            def fail_commit():
                raise RuntimeError("simulated commit failure")

            def fail_rollback():
                raise RuntimeError("simulated rollback failure")

            monkeypatch.setattr(db, "commit", fail_commit)
            monkeypatch.setattr(db, "rollback", fail_rollback)
            with pytest.raises(RuntimeError, match="simulated commit failure"):
                _delete_case(study_id, db)

        with sessions() as db:
            assert db.get(StudyModel, study_id) is not None
            assert db.query(ImageModel).filter_by(study_id=study_id).count() == 1
            assert db.query(AuditLogModel).filter_by(action_type="CLINICAL_CASE_DELETE").count() == 0
        assert image.exists()
    finally:
        engine.dispose()


def test_delete_commit_acknowledgement_failure_reconciles_persisted_delete(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    image = upload_dir / "image.png"
    image.write_bytes(b"image")
    engine, sessions, study_id = _case_database(tmp_path, [image], monkeypatch)
    try:
        with sessions() as db:
            real_commit = db.commit

            def commit_then_lose_acknowledgement():
                real_commit()
                raise RuntimeError("simulated lost commit acknowledgement")

            def fail_rollback():
                raise RuntimeError("simulated rollback failure")

            monkeypatch.setattr(db, "commit", commit_then_lose_acknowledgement)
            monkeypatch.setattr(db, "rollback", fail_rollback)
            result = _delete_case(study_id, db)

        assert result["status"] == "SUCCESS"
        assert result["file_cleanup"] == "COMPLETE"
        assert not image.exists()
        with sessions() as db:
            assert db.get(StudyModel, study_id) is None
            assert db.query(AuditLogModel).filter_by(
                entity_id=study_id, action_type="CLINICAL_CASE_DELETE"
            ).count() == 1
    finally:
        engine.dispose()


def test_delete_never_removes_file_outside_upload_directory(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    external = tmp_path / "source.png"
    external.write_bytes(b"source")
    engine, sessions, study_id = _case_database(tmp_path, [external], monkeypatch)
    try:
        with sessions() as db:
            result = _delete_case(study_id, db)
        assert result["status"] == "SUCCESS"
        assert external.exists()
        with sessions() as db:
            pending_model = getattr(importlib.import_module("backend.db.database"), "PendingFileDeletionModel")
            assert db.query(pending_model).count() == 0
    finally:
        engine.dispose()


def test_delete_removes_owned_upload_after_database_commit(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    image = upload_dir / "image.png"
    image.write_bytes(b"image")
    engine, sessions, study_id = _case_database(tmp_path, [image], monkeypatch)
    try:
        with sessions() as db:
            result = _delete_case(study_id, db)
        assert result["status"] == "SUCCESS"
        assert result["file_cleanup"] == "COMPLETE"
        assert not image.exists()
        with sessions() as db:
            pending_model = getattr(importlib.import_module("backend.db.database"), "PendingFileDeletionModel")
            assert db.query(pending_model).count() == 0
    finally:
        engine.dispose()


def test_delete_records_retry_when_owned_upload_cannot_be_removed(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    image = upload_dir / "locked-image.png"
    image.write_bytes(b"image")
    engine, sessions, study_id = _case_database(tmp_path, [image], monkeypatch)
    real_unlink = Path.unlink

    def deny_image_unlink(path, *args, **kwargs):
        if path == image.resolve():
            raise PermissionError("file is locked")
        return real_unlink(path, *args, **kwargs)

    try:
        monkeypatch.setattr(Path, "unlink", deny_image_unlink)
        with sessions() as db:
            result = _delete_case(study_id, db)

        assert result["status"] == "SUCCESS"
        assert result["file_cleanup"] == "PENDING"
        assert image.exists()
        with sessions() as db:
            assert db.get(StudyModel, study_id) is None
            pending_model = getattr(importlib.import_module("backend.db.database"), "PendingFileDeletionModel")
            pending = db.query(pending_model).one()
            assert pending.relative_path == image.relative_to(upload_dir).as_posix()

        monkeypatch.setattr(Path, "unlink", real_unlink)
        deletion_service = importlib.import_module("backend.services.file_deletion_service")
        with sessions() as db:
            deletion_service.retry_pending_file_deletions(db, upload_dir)

        assert not image.exists()
        with sessions() as db:
            assert db.query(pending_model).count() == 0
    finally:
        engine.dispose()


def test_retry_rejects_database_paths_outside_upload_root(tmp_path):
    database = importlib.import_module("backend.db.database")
    deletion_service = importlib.import_module("backend.services.file_deletion_service")
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    external = tmp_path / "source.png"
    external.write_bytes(b"source")
    engine = create_engine(f"sqlite:///{tmp_path / 'retry-path.sqlite3'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    try:
        with sessions() as db:
            db.add(database.PendingFileDeletionModel(id="bad-path", relative_path="../source.png"))
            db.commit()
            deletion_service.retry_pending_file_deletions(db, upload_dir)
            assert db.query(database.PendingFileDeletionModel).count() == 1
        assert external.exists()
    finally:
        engine.dispose()


def test_retry_is_idempotent_when_outbox_commit_fails_after_unlink(tmp_path):
    database = importlib.import_module("backend.db.database")
    deletion_service = importlib.import_module("backend.services.file_deletion_service")
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    image = upload_dir / "retry-image.png"
    image.write_bytes(b"image")
    engine = create_engine(f"sqlite:///{tmp_path / 'retry-commit.sqlite3'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    try:
        with sessions() as db:
            db.add(
                database.PendingFileDeletionModel(
                    id="retry-image", relative_path=image.name
                )
            )
            db.commit()

        with sessions() as db:
            real_commit = db.commit

            def fail_commit():
                raise RuntimeError("simulated outbox commit failure")

            db.commit = fail_commit
            assert deletion_service.retry_pending_file_deletions(db, upload_dir) is True
            assert not image.exists()
            db.commit = real_commit

        with sessions() as db:
            assert deletion_service.retry_pending_file_deletions(db, upload_dir) is False
            assert db.query(database.PendingFileDeletionModel).count() == 0
        assert not image.exists()
    finally:
        engine.dispose()


def test_delete_case_removes_review_batches_referenced_by_hitl_sessions(tmp_path, monkeypatch):
    from backend.db.database import HITLSessionModel, ReviewBatchModel

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    engine, sessions, study_id = _case_database(tmp_path, [], monkeypatch)
    try:
        with sessions() as db:
            batch = ReviewBatchModel(
                id="batch-1",
                request_id="request-1",
                actor_id="doctor-1",
                study_id=study_id,
                request_hash="a" * 64,
                response_json={"reviews": []},
            )
            session = HITLSessionModel(
                id="session-1",
                study_id=study_id,
                actor_id="doctor-1",
                participant_code="tester-1",
                participant_role="clinician",
                data_origin="technical_fixture",
                review_batch_id=batch.id,
            )
            db.add(batch)
            db.flush()
            db.add(session)
            db.commit()
            session_id, batch_id = session.id, batch.id

            result = _delete_case(study_id, db)

            assert result["status"] == "SUCCESS"
            assert db.get(StudyModel, study_id) is None
            assert db.get(HITLSessionModel, session_id) is None
            assert db.get(ReviewBatchModel, batch_id) is None
    finally:
        engine.dispose()


def test_delete_case_removes_reviews_before_referenced_predictions(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    image_path = upload_dir / "image.png"
    engine, sessions, study_id = _case_database(tmp_path, [image_path], monkeypatch)
    image_path.write_bytes(b"test image")
    try:
        with sessions() as db:
            prediction = PredictionModel(
                id="prediction-1",
                image_id="image-0",
                raw_mask_rle={"size": [1, 1], "counts": [1]},
                measurements={},
            )
            db.add(prediction)
            db.flush()
            review = ReviewModel(
                id="review-1",
                image_id="image-0",
                prediction_id=prediction.id,
                verified_mask_rle={"size": [1, 1], "counts": [1]},
            )
            db.add(review)
            db.commit()
            prediction_id = prediction.id
            review_id = review.id

            result = _delete_case(study_id, db)

            assert result["status"] == "SUCCESS"
            assert db.get(StudyModel, study_id) is None
            assert db.get(ImageModel, "image-0") is None
            assert db.get(PredictionModel, prediction_id) is None
            assert db.get(ReviewModel, review_id) is None
        assert not image_path.exists()
    finally:
        engine.dispose()
