"""The same bytes must not be assigned to both views of one study."""

import hashlib
import sqlite3
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.db.database import Base, ImageModel, PatientModel, StudyModel, get_db

pytestmark = pytest.mark.usefixtures("doctor_access")


@pytest.mark.parametrize("remove_first_file", [False, True])
def test_identical_image_rejected_within_study(tmp_path, monkeypatch, remove_first_file):
    from backend.app.main import app
    from backend.app.routers import inference

    engine = create_engine(f"sqlite:///{tmp_path / 'upload.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
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
            first = client.post("/api/upload", data={"study_id": "study", "laterality": "R"}, files={"file": ("image.png", contents, "image/png")})
            assert first.status_code == 200, first.text
            if remove_first_file:
                with Session(engine) as db:
                    Path(db.get(ImageModel, first.json()["image_id"]).raw_path).unlink()
            second = client.post("/api/upload", data={"study_id": "study", "laterality": "L"}, files={"file": ("same.png", contents, "image/png")})
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
