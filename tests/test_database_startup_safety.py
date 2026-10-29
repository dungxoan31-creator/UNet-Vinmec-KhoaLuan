from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest


def test_legacy_studies_receive_stable_unique_visit_numbers(tmp_path):
    import sqlite3

    from backend.db.database import _migrate_visit_numbers_on_connection

    path = tmp_path / "legacy-visit-numbers.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE studies (id TEXT PRIMARY KEY)")
        connection.executemany(
            "INSERT INTO studies (id) VALUES (?)",
            [("legacy-study-a",), ("legacy-study-b",)],
        )
        _migrate_visit_numbers_on_connection(connection.cursor())
        first_numbers = dict(connection.execute("SELECT id, visit_no FROM studies"))
        assert set(first_numbers.values()) == {"000001", "000002"}
        assert connection.execute(
            "SELECT next_value FROM visit_number_sequences WHERE id = 1"
        ).fetchone() == (3,)

        connection.execute("DELETE FROM studies WHERE id = 'legacy-study-b'")
        _migrate_visit_numbers_on_connection(connection.cursor())
        assert dict(connection.execute("SELECT id, visit_no FROM studies")) == {
            "legacy-study-a": "000001"
        }
        assert connection.execute(
            "SELECT next_value FROM visit_number_sequences WHERE id = 1"
        ).fetchone() == (3,)

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO studies (id, visit_no) VALUES ('duplicate', '000001')"
            )


def test_init_db_stops_before_migration_when_metadata_creation_fails(tmp_path, monkeypatch):
    from backend.db import database

    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "startup-failure.db"))
    calls = []

    def fail_create_all(**_kwargs):
        raise OSError("schema storage unavailable")

    monkeypatch.setattr(database.Base.metadata, "create_all", fail_create_all)
    monkeypatch.setattr(
        database,
        "_migrate_auth_email_schema_on_connection",
        lambda *_: calls.append("migration"),
    )

    with pytest.raises(RuntimeError, match="Database schema creation failed"):
        database.init_db()

    assert calls == []


def test_concurrent_init_db_calls_create_one_consistent_schema(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from backend.db import database

    db_path = tmp_path / "concurrent-startup.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False, "timeout": 30})
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.delenv("APP_DOCTOR_PASSWORD", raising=False)
    monkeypatch.delenv("APP_ADMIN_PASSWORD", raising=False)

    start_barrier = Barrier(4)

    def start_concurrent_init():
        start_barrier.wait(timeout=10)
        database.init_db()

    try:
        with ThreadPoolExecutor(max_workers=4) as workers:
            futures = [workers.submit(start_concurrent_init) for _ in range(4)]
            for future in futures:
                future.result(timeout=30)

        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
            tables = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'")
            ).scalars().all()
            assert {"patients", "studies", "images", "reviews", "predictions"} <= set(tables)
            laterality_triggers = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'images'")
            ).scalars().all()
            assert {"trg_images_laterality_insert", "trg_images_laterality_update"} <= set(
                laterality_triggers
            )
            review_triggers = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'reviews'")
            ).scalars().all()
            assert {
                "trg_reviews_doctor_action_insert",
                "trg_reviews_doctor_action_update",
            } <= set(review_triggers)
            hitl_event_triggers = connection.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'trigger' AND tbl_name = 'hitl_events'"
                )
            ).scalars().all()
            assert {
                "trg_hitl_events_event_type_insert",
                "trg_hitl_events_event_type_update",
            } <= set(hitl_event_triggers)
            hitl_session_triggers = connection.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = 'trigger' AND tbl_name = 'hitl_sessions'"
                )
            ).scalars().all()
            assert {
                "trg_hitl_sessions_domain_insert",
                "trg_hitl_sessions_domain_update",
            } <= set(hitl_session_triggers)
            study_triggers = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'studies'")
            ).scalars().all()
            assert {"trg_studies_domain_insert", "trg_studies_domain_update"} <= set(study_triggers)
    finally:
        engine.dispose()


def test_init_db_refuses_to_guess_missing_study_context_for_legacy_rows(tmp_path, monkeypatch):
    import sqlite3

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.db import database

    db_path = tmp_path / "legacy-study-context.sqlite3"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setenv(
        "APP_PATIENT_PID_HMAC_SECRET",
        "legacy-study-context-test-secret-at-least-32-bytes",
    )
    monkeypatch.delenv("APP_DOCTOR_PASSWORD", raising=False)
    monkeypatch.delenv("APP_ADMIN_PASSWORD", raising=False)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE patients (id TEXT PRIMARY KEY, anonymized_pid TEXT NOT NULL UNIQUE)"
        )
        connection.execute(
            "CREATE TABLE studies ("
            "id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, study_date TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO patients (id, anonymized_pid) VALUES ('patient-1', 'LEGACY-PID-CONTEXT')"
        )
        connection.execute(
            "INSERT INTO studies (id, patient_id, study_date) "
            "VALUES ('study-1', 'patient-1', '2026-10-21')"
        )

    try:
        with pytest.raises(RuntimeError, match="SQLite schema migration failed"):
            database.init_db()

        with sqlite3.connect(db_path) as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(studies)")}
            assert not {"status", "ovary_side", "contralateral_status"} & columns
            assert connection.execute(
                "SELECT id, patient_id, study_date FROM studies"
            ).fetchall() == [("study-1", "patient-1", "2026-10-21")]
            assert connection.execute(
                "SELECT anonymized_pid FROM patients WHERE id = 'patient-1'"
            ).fetchone() == ("LEGACY-PID-CONTEXT",)
    finally:
        engine.dispose()


def test_init_db_rolls_back_schema_creation_when_migration_fails(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, text

    from backend.db import database

    db_path = tmp_path / "atomic-startup.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setattr(database, "engine", engine)

    def fail_migration(_connection):
        raise OSError("migration storage failure")

    monkeypatch.setattr(database, "_migrate_auth_email_schema_on_connection", fail_migration)
    try:
        with pytest.raises(RuntimeError, match="SQLite schema migration failed"):
            database.init_db()

        with engine.connect() as connection:
            tables = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'")
            ).scalars().all()
            assert tables == []
    finally:
        engine.dispose()


def test_init_db_pseudonymizes_legacy_patient_ids_atomically(tmp_path, monkeypatch):
    import sqlite3

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker

    from backend.core.patient_identity import patient_id_digest, patient_pid_key_id
    from backend.db import database

    db_path = tmp_path / "legacy-patient-identities.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.setenv("APP_PATIENT_PID_HMAC_SECRET", "migration-test-hmac-secret-at-least-32-bytes")
    monkeypatch.delenv("APP_DOCTOR_PASSWORD", raising=False)
    monkeypatch.delenv("APP_ADMIN_PASSWORD", raising=False)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE patients ("
            "id VARCHAR(36) PRIMARY KEY, anonymized_pid VARCHAR(64) UNIQUE NOT NULL, "
            "age_bucket VARCHAR(20), menopausal_status VARCHAR(20), created_at DATETIME)"
        )
    try:
        database.Base.metadata.create_all(engine, checkfirst=True)
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                "INSERT INTO patients (id, anonymized_pid, age_bucket) VALUES (?, ?, ?)",
                ("legacy-patient", "SOURCE-PID-DO-NOT-RETAIN", "40-49"),
            )
            connection.execute(
                "INSERT INTO studies "
                "(id, patient_id, study_date, status, ovary_side, contralateral_status, review_revision) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("legacy-study", "legacy-patient", "2026-10-21", "PENDING", "RIGHT", "NOT_VISUALIZED", 0),
            )

        database.init_db()
        database.init_db()
        with Session(engine) as db:
            patient = db.get(database.PatientModel, "legacy-patient")
            study = db.get(database.StudyModel, "legacy-study")
            assert patient is not None
            assert patient.anonymized_pid.startswith("SYN-")
            assert patient.source_pid_hmac == patient_id_digest("SOURCE-PID-DO-NOT-RETAIN")
            assert patient.pid_hmac_key_id == patient_pid_key_id()
            assert study is not None and study.patient_id == patient.id
            stable_synthetic_id = patient.anonymized_pid

        with sqlite3.connect(db_path) as connection:
            persisted = " ".join(str(value) for row in connection.execute(
                "SELECT anonymized_pid, source_pid_hmac, pid_hmac_key_id FROM patients"
            ) for value in row)
            assert "SOURCE-PID-DO-NOT-RETAIN" not in persisted

        monkeypatch.setenv("APP_PATIENT_PID_HMAC_SECRET", "rotated-migration-hmac-secret-at-least-32-bytes")
        with pytest.raises(RuntimeError, match="SQLite schema migration failed"):
            database.init_db()
        with Session(engine) as db:
            patient = db.get(database.PatientModel, "legacy-patient")
            assert patient is not None
            assert patient.anonymized_pid == stable_synthetic_id
            assert patient.source_pid_hmac == patient_id_digest(
                "SOURCE-PID-DO-NOT-RETAIN", b"migration-test-hmac-secret-at-least-32-bytes"
            )
    finally:
        engine.dispose()


def test_init_db_removes_legacy_client_filenames_from_image_and_upload_audit_metadata(
    tmp_path, monkeypatch
):
    import hashlib
    import json
    import sqlite3

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker

    from backend.db import database

    db_path = tmp_path / "filename-privacy.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.delenv("APP_DOCTOR_PASSWORD", raising=False)
    monkeypatch.delenv("APP_ADMIN_PASSWORD", raising=False)
    database.Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(database.PatientModel(id="patient", anonymized_pid="PID-FILENAME-PRIVACY"))
        db.add(database.StudyModel(id="study", patient_id="patient", study_date="2026-10-21"))
        db.add(
            database.ImageModel(
                id="image-id",
                study_id="study",
                filename="PRIVATE_IDENTIFIER_SENTINEL.png",
                raw_path="/uploads/image-id.png",
            )
        )
        db.add(
            database.AuditLogModel(
                entity_name="image",
                entity_id="image-id",
                action_type="UPLOAD_IMAGE",
                actor_id="doctor",
                details={
                    "filename": "PRIVATE_IDENTIFIER_SENTINEL.png",
                    "dimensions": [512, 512],
                    "study_id": "study",
                },
            )
        )
        db.commit()
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO audit_logs (entity_name, entity_id, action_type, actor_id, details) "
            "VALUES (?, ?, ?, ?, ?)",
            ("image", "image-id", "UPLOAD_IMAGE", "doctor", "{PRIVATE_IDENTIFIER_SENTINEL"),
        )

    try:
        database.init_db()
        database.init_db()
        with Session(engine) as db:
            image = db.get(database.ImageModel, "image-id")
            audits = (
                db.query(database.AuditLogModel)
                .filter_by(action_type="UPLOAD_IMAGE")
                .order_by(database.AuditLogModel.id)
                .all()
            )
            assert image.filename == f"{hashlib.sha256(b'image-id').hexdigest()}.png"
            assert audits[0].details == {"dimensions": [512, 512], "study_id": "study"}
            assert audits[1].details is None
        with sqlite3.connect(db_path) as db:
            persisted = " ".join(str(value) for row in db.execute(
                "SELECT filename FROM images UNION ALL SELECT details FROM audit_logs"
            ) for value in row)
            assert "PRIVATE_IDENTIFIER_SENTINEL" not in persisted
            assert json.loads(
                db.execute(
                    "SELECT details FROM audit_logs WHERE action_type='UPLOAD_IMAGE' ORDER BY id LIMIT 1"
                ).fetchone()[0]
            ) == {"dimensions": [512, 512], "study_id": "study"}
    finally:
        engine.dispose()
