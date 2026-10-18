"""Deleting a case must not remove source data before durable DB success."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.routers import cases
from backend.db.database import (
    Base,
    HITLSessionModel,
    PatientModel,
    ReviewBatchModel,
    StudyModel,
)


class QueryResult:
    def __init__(self, study):
        self.study = study

    def filter(self, *_args):
        return self

    def first(self):
        return self.study


class CaseSession:
    def __init__(self, path: Path, fail_commit=False):
        self.study = SimpleNamespace(images=[SimpleNamespace(raw_path=str(path))])
        self.fail_commit = fail_commit

    def query(self, _model):
        return QueryResult(self.study)

    def delete(self, _study):
        pass

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("simulated commit failure")


def test_delete_preserves_upload_when_database_commit_fails(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    image = upload_dir / "image.png"
    image.write_bytes(b"image")
    monkeypatch.setattr(cases, "UPLOAD_DIR", str(upload_dir), raising=False)
    with pytest.raises(RuntimeError, match="commit failure"):
        cases.delete_case("study", db=CaseSession(image, fail_commit=True))
    assert image.exists()


def test_delete_never_removes_file_outside_upload_directory(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    external = tmp_path / "source.png"
    external.write_bytes(b"source")
    monkeypatch.setattr(cases, "UPLOAD_DIR", str(upload_dir), raising=False)
    result = cases.delete_case("study", db=CaseSession(external))
    assert result["status"] == "SUCCESS"
    assert external.exists()


def test_delete_removes_owned_upload_after_database_commit(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    image = upload_dir / "image.png"
    image.write_bytes(b"image")
    monkeypatch.setattr(cases, "UPLOAD_DIR", str(upload_dir), raising=False)
    result = cases.delete_case("study", db=CaseSession(image))
    assert result["status"] == "SUCCESS"
    assert not image.exists()


def test_delete_case_removes_review_batches_referenced_by_hitl_sessions(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(cases, "UPLOAD_DIR", str(upload_dir), raising=False)
    engine = create_engine(f"sqlite:///{tmp_path / 'case-delete.sqlite3'}")
    Base.metadata.create_all(engine)
    try:
        SessionLocal = sessionmaker(bind=engine, autoflush=False)
        with SessionLocal() as db:
            patient = PatientModel(id="patient-1", anonymized_pid="PID-1")
            study = StudyModel(id="study-1", patient=patient, study_date="2026-10-18")
            db.add(study)
            db.flush()
            batch = ReviewBatchModel(
                id="batch-1",
                request_id="request-1",
                actor_id="doctor-1",
                study_id=study.id,
                request_hash="a" * 64,
                response_json={"reviews": []},
            )
            session = HITLSessionModel(
                id="session-1",
                study_id=study.id,
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
            study_id, session_id, batch_id = study.id, session.id, batch.id

            result = cases.delete_case(study_id, db=db)

            assert result["status"] == "SUCCESS"
            assert db.get(StudyModel, study_id) is None
            assert db.get(HITLSessionModel, session_id) is None
            assert db.get(ReviewBatchModel, batch_id) is None
    finally:
        engine.dispose()
