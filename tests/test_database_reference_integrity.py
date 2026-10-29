import sqlite3
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.db.database import Base


def _new_database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'reference-integrity.sqlite3'}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO patients (id, anonymized_pid) VALUES ('patient-1', 'pid-1')")
        )
        connection.execute(
            text(
                "INSERT INTO studies "
                "(id, patient_id, study_date, status, ovary_side, contralateral_status, review_revision) "
                "VALUES ('study-1', 'patient-1', '2026-10-21', 'PENDING', 'BOTH', 'NOT_VISUALIZED', 0)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO images (id, study_id, filename, raw_path) VALUES "
                "('image-1', 'study-1', 'right.png', 'right.png'), "
                "('image-2', 'study-1', 'left.png', 'left.png')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO predictions (id, image_id, raw_mask_rle, measurements) "
                "VALUES ('prediction-1', 'image-1', '[]', '{}')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO hitl_sessions "
                "(id, study_id, actor_id, participant_code, participant_role, data_origin, status) "
                "VALUES ('session-1', 'study-1', 'doctor-1', 'participant-1', 'clinician', 'live', 'IN_PROGRESS')"
            )
        )
    return engine


def _assert_integrity_error(engine, sql, parameters):
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text(sql), parameters)


@pytest.mark.parametrize(
    ("image_id", "prediction_id"),
    [("image-1", "missing-prediction"), ("image-2", "prediction-1")],
    ids=["missing-prediction", "prediction-from-other-image"],
)
def test_review_prediction_reference_must_match_image(tmp_path, image_id, prediction_id):
    engine = _new_database(tmp_path)
    try:
        _assert_integrity_error(
            engine,
            "INSERT INTO reviews (id, image_id, prediction_id, verified_mask_rle) "
            "VALUES (:id, :image_id, :prediction_id, '[]')",
            {"id": str(uuid4()), "image_id": image_id, "prediction_id": prediction_id},
        )
    finally:
        engine.dispose()


def test_review_may_have_no_prediction_reference(tmp_path):
    engine = _new_database(tmp_path)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO reviews (id, image_id, prediction_id, doctor_action, verified_mask_rle) "
                    "VALUES (:id, 'image-1', NULL, 'ACCEPTED_RAW', '[]')"
                ),
                {"id": str(uuid4())},
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize("invalid_action", ["CONFIRMED", "REJECTED", "", None])
def test_review_action_database_constraint_matches_api_contract(tmp_path, invalid_action):
    engine = _new_database(tmp_path)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO reviews (id, image_id, doctor_action, verified_mask_rle) "
                    "VALUES ('review-action', 'image-1', 'ACCEPTED_RAW', '[]')"
                )
            )

        _assert_integrity_error(
            engine,
            "UPDATE reviews SET doctor_action = :action WHERE id = 'review-action'",
            {"action": invalid_action},
        )

        with engine.connect() as connection:
            action = connection.execute(
                text("SELECT doctor_action FROM reviews WHERE id = 'review-action'")
            ).scalar_one()
        assert action == "ACCEPTED_RAW"
    finally:
        engine.dispose()


def test_review_action_migration_installs_insert_and_update_guards_on_legacy_table(tmp_path):
    from backend.db.database import _ensure_review_action_domain

    connection = sqlite3.connect(tmp_path / "legacy-review-actions.sqlite3")
    connection.execute("CREATE TABLE reviews (id TEXT PRIMARY KEY, doctor_action TEXT)")
    connection.execute(
        "INSERT INTO reviews (id, doctor_action) VALUES ('review-1', 'ACCEPTED_RAW')"
    )
    connection.commit()
    try:
        _ensure_review_action_domain(connection)
        connection.commit()
        _ensure_review_action_domain(connection)
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError, match="doctor_action is not supported"):
            connection.execute(
                "INSERT INTO reviews (id, doctor_action) VALUES ('review-2', 'CONFIRMED')"
            )
        with pytest.raises(sqlite3.IntegrityError, match="doctor_action is not supported"):
            connection.execute(
                "UPDATE reviews SET doctor_action = 'REJECTED' WHERE id = 'review-1'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="doctor_action is not supported"):
            connection.execute(
                "UPDATE reviews SET doctor_action = NULL WHERE id = 'review-1'"
            )
        connection.rollback()

        assert connection.execute(
            "SELECT id, doctor_action FROM reviews"
        ).fetchall() == [("review-1", "ACCEPTED_RAW")]
    finally:
        connection.close()


@pytest.mark.parametrize("legacy_action", ["CONFIRMED", None])
def test_review_action_migration_refuses_invalid_legacy_rows_without_rewriting_them(
    tmp_path, legacy_action
):
    from backend.db.database import _ensure_review_action_domain

    connection = sqlite3.connect(tmp_path / "invalid-legacy-review-actions.sqlite3")
    connection.execute("CREATE TABLE reviews (id TEXT PRIMARY KEY, doctor_action TEXT)")
    connection.execute(
        "INSERT INTO reviews (id, doctor_action) VALUES ('review-1', ?)",
        (legacy_action,),
    )
    connection.commit()
    try:
        with pytest.raises(RuntimeError, match="unsupported doctor action"):
            _ensure_review_action_domain(connection)
        connection.rollback()
        assert connection.execute("SELECT id, doctor_action FROM reviews").fetchall() == [
            ("review-1", legacy_action)
        ]
    finally:
        connection.close()


def test_image_laterality_database_constraint_allows_only_right_left_or_null(tmp_path):
    engine = _new_database(tmp_path)
    try:
        with engine.begin() as connection:
            connection.execute(text("UPDATE images SET laterality = 'R' WHERE id = 'image-1'"))
            connection.execute(text("UPDATE images SET laterality = 'L' WHERE id = 'image-2'"))

        _assert_integrity_error(
            engine,
            "UPDATE images SET laterality = 'B' WHERE id = 'image-1'",
            {},
        )

        with engine.connect() as connection:
            laterality = connection.execute(
                text("SELECT laterality FROM images ORDER BY id")
            ).scalars().all()
        assert laterality == ["R", "L"]
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("status", "SIGNED"),
        ("ovary_side", "UNKNOWN_SIDE"),
        ("contralateral_status", "MALIGNANT"),
    ],
)
def test_study_clinical_context_database_constraints_match_api_and_workflow(
    tmp_path, field, invalid_value
):
    engine = _new_database(tmp_path)
    try:
        _assert_integrity_error(
            engine,
            f"UPDATE studies SET {field} = :value WHERE id = 'study-1'",
            {"value": invalid_value},
        )

        with engine.connect() as connection:
            study = connection.execute(
                text(
                    "SELECT status, ovary_side, contralateral_status "
                    "FROM studies WHERE id = 'study-1'"
                )
            ).one()
        assert tuple(study) == ("PENDING", "BOTH", "NOT_VISUALIZED")
    finally:
        engine.dispose()


def test_study_clinical_context_database_allows_explicit_unknown_side(tmp_path):
    engine = _new_database(tmp_path)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE studies SET ovary_side = 'UNKNOWN' WHERE id = 'study-1'")
            )
            connection.execute(
                text("UPDATE studies SET contralateral_status = 'UNKNOWN' WHERE id = 'study-1'")
            )
        with engine.connect() as connection:
            context = connection.execute(
                text("SELECT ovary_side, contralateral_status FROM studies WHERE id = 'study-1'")
            ).one()
        assert tuple(context) == ("UNKNOWN", "UNKNOWN")
    finally:
        engine.dispose()


def test_study_clinical_context_domains_match_api_contract():
    from backend.core.study_domains import (
        CONTRALATERAL_STATUSES,
        STUDY_OVARY_SIDES,
    )
    from backend.schemas.schemas import CreateCaseRequest

    properties = CreateCaseRequest.model_json_schema()["properties"]
    assert set(properties["active_ovary_side"]["enum"]) == STUDY_OVARY_SIDES
    assert set(properties["contralateral_status"]["enum"]) == CONTRALATERAL_STATUSES


def test_study_domain_migration_installs_insert_and_update_guards_on_legacy_table(tmp_path):
    from backend.db.database import _ensure_study_domains

    connection = sqlite3.connect(tmp_path / "legacy-study-domains.sqlite3")
    connection.execute(
        "CREATE TABLE studies ("
        "id TEXT PRIMARY KEY, status TEXT, ovary_side TEXT, contralateral_status TEXT)"
    )
    connection.execute(
        "INSERT INTO studies (id, status, ovary_side, contralateral_status) "
        "VALUES ('study-1', 'PENDING', 'BOTH', 'NOT_VISUALIZED')"
    )
    connection.commit()
    try:
        _ensure_study_domains(connection)
        connection.commit()
        _ensure_study_domains(connection)
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError, match="study domain value is not supported"):
            connection.execute(
                "INSERT INTO studies (id, status, ovary_side, contralateral_status) "
                "VALUES ('study-2', 'SIGNED', 'RIGHT', 'NORMAL')"
            )
        with pytest.raises(sqlite3.IntegrityError, match="study domain value is not supported"):
            connection.execute(
                "UPDATE studies SET ovary_side = 'UNKNOWN_SIDE' WHERE id = 'study-1'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="study domain value is not supported"):
            connection.execute(
                "UPDATE studies SET contralateral_status = 'MALIGNANT' WHERE id = 'study-1'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="study domain value is not supported"):
            connection.execute("UPDATE studies SET status = NULL WHERE id = 'study-1'")
        connection.rollback()

        assert connection.execute(
            "SELECT id, status, ovary_side, contralateral_status FROM studies"
        ).fetchall() == [("study-1", "PENDING", "BOTH", "NOT_VISUALIZED")]
    finally:
        connection.close()


def test_migration_extends_surgical_absence_check_without_losing_study_references(tmp_path):
    from backend.db.database import _migrate_study_contralateral_constraint

    connection = sqlite3.connect(tmp_path / "legacy-contralateral-check.sqlite3")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("CREATE TABLE patients (id TEXT PRIMARY KEY)")
    connection.execute(
        "CREATE TABLE studies ("
        "id TEXT PRIMARY KEY, patient_id TEXT NOT NULL REFERENCES patients(id), "
        "status TEXT NOT NULL, ovary_side TEXT NOT NULL, contralateral_status TEXT NOT NULL, "
        "CONSTRAINT ck_studies_contralateral_status CHECK "
        "(contralateral_status IS NOT NULL AND contralateral_status IN "
        "('NOT_VISUALIZED', 'NORMAL', 'SUSPECTED', 'UNKNOWN')))"
    )
    connection.execute(
        "CREATE TABLE images (id TEXT PRIMARY KEY, study_id TEXT NOT NULL REFERENCES studies(id))"
    )
    connection.execute("CREATE INDEX idx_studies_patient_id ON studies(patient_id)")
    connection.execute("INSERT INTO patients VALUES ('patient-1')")
    connection.execute(
        "INSERT INTO studies VALUES ('study-1', 'patient-1', 'PENDING', 'LEFT', 'UNKNOWN')"
    )
    connection.execute("INSERT INTO images VALUES ('image-1', 'study-1')")
    connection.commit()

    try:
        assert _migrate_study_contralateral_constraint(connection) is True
        connection.execute(
            "UPDATE studies SET contralateral_status = 'SURGICALLY_ABSENT' WHERE id = 'study-1'"
        )
        assert connection.execute(
            "SELECT id, patient_id, contralateral_status FROM studies"
        ).fetchall() == [("study-1", "patient-1", "SURGICALLY_ABSENT")]
        assert connection.execute("SELECT study_id FROM images").fetchall() == [("study-1",)]
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_studies_patient_id'"
        ).fetchone() == (1,)
    finally:
        connection.close()


def test_study_domain_migration_replaces_stale_legacy_triggers(tmp_path):
    from backend.db.database import _ensure_study_domains

    connection = sqlite3.connect(tmp_path / "stale-study-domain-triggers.sqlite3")
    connection.execute(
        "CREATE TABLE studies ("
        "id TEXT PRIMARY KEY, status TEXT, ovary_side TEXT, contralateral_status TEXT)"
    )
    connection.execute(
        "INSERT INTO studies VALUES ('study-1', 'PENDING', 'BOTH', 'NOT_VISUALIZED')"
    )
    old_predicate = (
        "NEW.status IS NULL OR NEW.status NOT IN "
        "('PENDING','ANALYZED','PARTIALLY_REVIEWED','REVIEWED','SIGNED_PRELIM','APPROVED','LOCKED') "
        "OR NEW.ovary_side IS NULL OR NEW.ovary_side NOT IN ('RIGHT','LEFT','BOTH','UNKNOWN') "
        "OR NEW.contralateral_status IS NULL OR NEW.contralateral_status NOT IN "
        "('NOT_VISUALIZED','NORMAL','SUSPECTED')"
    )
    connection.execute(
        "CREATE TRIGGER trg_studies_domain_insert BEFORE INSERT ON studies "
        f"WHEN {old_predicate} "
        "BEGIN SELECT RAISE(ABORT, 'study domain value is not supported'); END"
    )
    connection.execute(
        "CREATE TRIGGER trg_studies_domain_update "
        "BEFORE UPDATE OF status, ovary_side, contralateral_status ON studies "
        f"WHEN {old_predicate} "
        "BEGIN SELECT RAISE(ABORT, 'study domain value is not supported'); END"
    )
    connection.commit()
    try:
        _ensure_study_domains(connection)
        connection.execute(
            "INSERT INTO studies VALUES ('study-2', 'PENDING', 'UNKNOWN', 'UNKNOWN')"
        )
        connection.execute(
            "UPDATE studies SET contralateral_status = 'UNKNOWN' WHERE id = 'study-1'"
        )
        assert connection.execute(
            "SELECT id, ovary_side, contralateral_status FROM studies ORDER BY id"
        ).fetchall() == [
            ("study-1", "BOTH", "UNKNOWN"),
            ("study-2", "UNKNOWN", "UNKNOWN"),
        ]
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("status", "ovary_side", "contralateral_status"),
    [
        ("SIGNED", "RIGHT", "NORMAL"),
        ("PENDING", "UNKNOWN_SIDE", "NORMAL"),
        ("PENDING", "RIGHT", "MALIGNANT"),
        (None, "RIGHT", "NORMAL"),
    ],
)
def test_study_domain_migration_refuses_invalid_legacy_rows_without_rewriting_them(
    tmp_path, status, ovary_side, contralateral_status
):
    from backend.db.database import _ensure_study_domains

    connection = sqlite3.connect(tmp_path / "invalid-legacy-study-domains.sqlite3")
    connection.execute(
        "CREATE TABLE studies ("
        "id TEXT PRIMARY KEY, status TEXT, ovary_side TEXT, contralateral_status TEXT)"
    )
    connection.execute(
        "INSERT INTO studies (id, status, ovary_side, contralateral_status) "
        "VALUES ('study-1', ?, ?, ?)",
        (status, ovary_side, contralateral_status),
    )
    connection.commit()
    try:
        with pytest.raises(RuntimeError, match="unsupported study status, side, or contralateral status"):
            _ensure_study_domains(connection)
        connection.rollback()
        assert connection.execute(
            "SELECT id, status, ovary_side, contralateral_status FROM studies"
        ).fetchall() == [("study-1", status, ovary_side, contralateral_status)]
    finally:
        connection.close()


def test_laterality_migration_installs_insert_and_update_guards_on_legacy_table(tmp_path):
    from backend.db.database import _ensure_image_laterality_domain

    path = tmp_path / "legacy-laterality.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE images (id TEXT PRIMARY KEY, laterality TEXT)")
    connection.execute("INSERT INTO images (id, laterality) VALUES ('image-1', 'R')")
    connection.commit()
    try:
        _ensure_image_laterality_domain(connection)
        connection.commit()
        _ensure_image_laterality_domain(connection)
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError, match="laterality must be R or L"):
            connection.execute("INSERT INTO images (id, laterality) VALUES ('image-2', 'B')")
        with pytest.raises(sqlite3.IntegrityError, match="laterality must be R or L"):
            connection.execute("UPDATE images SET laterality = 'B' WHERE id = 'image-1'")
        connection.rollback()

        assert connection.execute(
            "SELECT id, laterality FROM images ORDER BY id"
        ).fetchall() == [("image-1", "R")]
    finally:
        connection.close()


def test_laterality_migration_refuses_invalid_legacy_rows_without_rewriting_them(tmp_path):
    from backend.db.database import _ensure_image_laterality_domain

    connection = sqlite3.connect(tmp_path / "invalid-legacy-laterality.sqlite3")
    connection.execute("CREATE TABLE images (id TEXT PRIMARY KEY, laterality TEXT)")
    connection.execute("INSERT INTO images (id, laterality) VALUES ('image-1', 'B')")
    connection.commit()
    try:
        with pytest.raises(RuntimeError, match="laterality other than R, L, or NULL"):
            _ensure_image_laterality_domain(connection)
        connection.rollback()
        assert connection.execute(
            "SELECT id, laterality FROM images"
        ).fetchall() == [("image-1", "B")]
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("image_id", "prediction_id"),
    [
        ("missing-image", None),
        ("image-1", "missing-prediction"),
        ("image-2", "prediction-1"),
    ],
    ids=["missing-image", "missing-prediction", "prediction-from-other-image"],
)
def test_hitl_event_references_must_exist_and_match(tmp_path, image_id, prediction_id):
    engine = _new_database(tmp_path)
    try:
        _assert_integrity_error(
            engine,
            "INSERT INTO hitl_events "
            "(id, event_id, session_id, task_id, image_id, prediction_id, seq, event_type, "
            "client_utc, elapsed_ms, session_elapsed_ms, payload_hash, actor_id) "
            "VALUES (:id, :event_id, 'session-1', :task_id, :image_id, :prediction_id, 1, "
            "'SESSION_START', '2026-10-21T00:00:00Z', 0, 0, 'hash', 'doctor-1')",
            {
                "id": str(uuid4()),
                "event_id": str(uuid4()),
                "task_id": str(uuid4()),
                "image_id": image_id,
                "prediction_id": prediction_id,
            },
        )
    finally:
        engine.dispose()


def test_hitl_event_may_have_no_prediction_reference(tmp_path):
    engine = _new_database(tmp_path)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO hitl_events "
                    "(id, event_id, session_id, task_id, image_id, prediction_id, seq, event_type, "
                    "client_utc, elapsed_ms, session_elapsed_ms, payload_hash, actor_id) "
                    "VALUES (:id, :event_id, 'session-1', :task_id, 'image-1', NULL, 1, 'SESSION_START', "
                    "'2026-10-21T00:00:00Z', 0, 0, 'hash', 'doctor-1')"
                ),
                {"id": str(uuid4()), "event_id": str(uuid4()), "task_id": str(uuid4())},
            )
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("participant_role", "administrator"),
        ("data_origin", "verified_clinical"),
        ("status", "SIGNED"),
    ],
)
def test_hitl_session_domain_database_constraints_match_api_and_state_machine(
    tmp_path, field, invalid_value
):
    engine = _new_database(tmp_path)
    try:
        _assert_integrity_error(
            engine,
            f"UPDATE hitl_sessions SET {field} = :value WHERE id = 'session-1'",
            {"value": invalid_value},
        )

        with engine.connect() as connection:
            session = connection.execute(
                text(
                    "SELECT participant_role, data_origin, status "
                    "FROM hitl_sessions WHERE id = 'session-1'"
                )
            ).one()
        assert tuple(session) == ("clinician", "live", "IN_PROGRESS")
    finally:
        engine.dispose()


def test_hitl_session_domain_preserves_legacy_active_status(tmp_path):
    engine = _new_database(tmp_path)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE hitl_sessions SET status = 'ACTIVE' WHERE id = 'session-1'")
            )
        with engine.connect() as connection:
            status = connection.execute(
                text("SELECT status FROM hitl_sessions WHERE id = 'session-1'")
            ).scalar_one()
        assert status == "ACTIVE"
    finally:
        engine.dispose()


def test_hitl_session_domains_match_api_literal_contract():
    from backend.core.hitl_session_domains import (
        HITL_SESSION_DATA_ORIGINS,
        HITL_SESSION_ROLES,
    )
    from backend.schemas.schemas import HITLSessionRequest

    properties = HITLSessionRequest.model_json_schema()["properties"]
    assert set(properties["participant_role"]["enum"]) == HITL_SESSION_ROLES
    assert set(properties["data_origin"]["enum"]) == HITL_SESSION_DATA_ORIGINS


def test_hitl_session_domain_migration_installs_insert_and_update_guards_on_legacy_table(
    tmp_path,
):
    from backend.db.database import _ensure_hitl_session_domains

    connection = sqlite3.connect(tmp_path / "legacy-hitl-session-domains.sqlite3")
    connection.execute(
        "CREATE TABLE hitl_sessions ("
        "id TEXT PRIMARY KEY, participant_role TEXT, data_origin TEXT, status TEXT)"
    )
    connection.execute(
        "INSERT INTO hitl_sessions (id, participant_role, data_origin, status) "
        "VALUES ('session-1', 'technical_tester', 'live', 'ACTIVE')"
    )
    connection.commit()
    try:
        _ensure_hitl_session_domains(connection)
        connection.commit()
        _ensure_hitl_session_domains(connection)
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError, match="domain value is not supported"):
            connection.execute(
                "INSERT INTO hitl_sessions (id, participant_role, data_origin, status) "
                "VALUES ('session-2', 'administrator', 'live', 'IN_PROGRESS')"
            )
        with pytest.raises(sqlite3.IntegrityError, match="domain value is not supported"):
            connection.execute(
                "UPDATE hitl_sessions SET data_origin = 'verified_clinical' WHERE id = 'session-1'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="domain value is not supported"):
            connection.execute(
                "UPDATE hitl_sessions SET status = 'SIGNED' WHERE id = 'session-1'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="domain value is not supported"):
            connection.execute(
                "UPDATE hitl_sessions SET status = NULL WHERE id = 'session-1'"
            )
        connection.rollback()

        assert connection.execute(
            "SELECT id, participant_role, data_origin, status FROM hitl_sessions"
        ).fetchall() == [("session-1", "technical_tester", "live", "ACTIVE")]
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("participant_role", "data_origin", "status"),
    [
        ("administrator", "live", "IN_PROGRESS"),
        ("clinician", "verified_clinical", "IN_PROGRESS"),
        ("clinician", "live", "SIGNED"),
        ("clinician", "live", None),
    ],
)
def test_hitl_session_domain_migration_refuses_invalid_legacy_rows_without_rewriting_them(
    tmp_path, participant_role, data_origin, status
):
    from backend.db.database import _ensure_hitl_session_domains

    connection = sqlite3.connect(tmp_path / "invalid-legacy-hitl-session-domains.sqlite3")
    connection.execute(
        "CREATE TABLE hitl_sessions ("
        "id TEXT PRIMARY KEY, participant_role TEXT, data_origin TEXT, status TEXT)"
    )
    connection.execute(
        "INSERT INTO hitl_sessions (id, participant_role, data_origin, status) "
        "VALUES ('session-1', ?, ?, ?)",
        (participant_role, data_origin, status),
    )
    connection.commit()
    try:
        with pytest.raises(RuntimeError, match="unsupported role, data origin, or status"):
            _ensure_hitl_session_domains(connection)
        connection.rollback()
        assert connection.execute(
            "SELECT id, participant_role, data_origin, status FROM hitl_sessions"
        ).fetchall() == [("session-1", participant_role, data_origin, status)]
    finally:
        connection.close()


@pytest.mark.parametrize("invalid_event_type", ["OPENED", "", "session_start"])
def test_hitl_event_type_database_constraint_matches_api_contract(tmp_path, invalid_event_type):
    engine = _new_database(tmp_path)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO hitl_events "
                    "(id, event_id, session_id, task_id, image_id, prediction_id, seq, event_type, "
                    "client_utc, elapsed_ms, session_elapsed_ms, payload_hash, actor_id) "
                    "VALUES ('event-type', 'event-key', 'session-1', 'task-1', 'image-1', NULL, "
                    "1, 'SESSION_START', '2026-10-21T00:00:00Z', 0, 0, 'hash', 'doctor-1')"
                )
            )

        _assert_integrity_error(
            engine,
            "UPDATE hitl_events SET event_type = :event_type WHERE id = 'event-type'",
            {"event_type": invalid_event_type},
        )

        with engine.connect() as connection:
            event_type = connection.execute(
                text("SELECT event_type FROM hitl_events WHERE id = 'event-type'")
            ).scalar_one()
        assert event_type == "SESSION_START"
    finally:
        engine.dispose()


def test_hitl_event_type_migration_installs_insert_and_update_guards_on_legacy_table(tmp_path):
    from backend.db.database import _ensure_hitl_event_type_domain

    connection = sqlite3.connect(tmp_path / "legacy-hitl-event-types.sqlite3")
    connection.execute("CREATE TABLE hitl_events (id TEXT PRIMARY KEY, event_type TEXT)")
    connection.execute(
        "INSERT INTO hitl_events (id, event_type) VALUES ('event-1', 'SESSION_START')"
    )
    connection.commit()
    try:
        _ensure_hitl_event_type_domain(connection)
        connection.commit()
        _ensure_hitl_event_type_domain(connection)
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError, match="event type is not supported"):
            connection.execute(
                "INSERT INTO hitl_events (id, event_type) VALUES ('event-2', 'OPENED')"
            )
        with pytest.raises(sqlite3.IntegrityError, match="event type is not supported"):
            connection.execute(
                "UPDATE hitl_events SET event_type = 'OPENED' WHERE id = 'event-1'"
            )
        with pytest.raises(sqlite3.IntegrityError, match="event type is not supported"):
            connection.execute(
                "UPDATE hitl_events SET event_type = NULL WHERE id = 'event-1'"
            )
        connection.rollback()

        assert connection.execute(
            "SELECT id, event_type FROM hitl_events"
        ).fetchall() == [("event-1", "SESSION_START")]
    finally:
        connection.close()


@pytest.mark.parametrize("legacy_event_type", ["OPENED", None])
def test_hitl_event_type_migration_refuses_invalid_legacy_rows_without_rewriting_them(
    tmp_path, legacy_event_type
):
    from backend.db.database import _ensure_hitl_event_type_domain

    connection = sqlite3.connect(tmp_path / "invalid-legacy-hitl-event-types.sqlite3")
    connection.execute("CREATE TABLE hitl_events (id TEXT PRIMARY KEY, event_type TEXT)")
    connection.execute(
        "INSERT INTO hitl_events (id, event_type) VALUES ('event-1', ?)",
        (legacy_event_type,),
    )
    connection.commit()
    try:
        with pytest.raises(RuntimeError, match="unsupported event type"):
            _ensure_hitl_event_type_domain(connection)
        connection.rollback()
        assert connection.execute(
            "SELECT id, event_type FROM hitl_events"
        ).fetchall() == [("event-1", legacy_event_type)]
    finally:
        connection.close()


def test_hitl_event_cannot_link_image_from_another_study(tmp_path, monkeypatch):
    engine = _new_database(tmp_path)
    database = _initialize_engine(
        engine, tmp_path, monkeypatch, database_filename="reference-integrity.sqlite3"
    )
    try:
        database.init_db()
        _add_other_study_image(engine)

        _assert_integrity_error(
            engine,
            "INSERT INTO hitl_events "
            "(id, event_id, session_id, task_id, image_id, prediction_id, seq, event_type, "
            "client_utc, elapsed_ms, session_elapsed_ms, payload_hash, actor_id) "
            "VALUES (:id, :event_id, 'session-1', :task_id, 'image-3', NULL, 1, 'SESSION_START', "
            "'2026-10-21T00:00:00Z', 0, 0, 'hash', 'doctor-1')",
            {"id": str(uuid4()), "event_id": str(uuid4()), "task_id": str(uuid4())},
        )
    finally:
        engine.dispose()


@pytest.mark.parametrize("target", ["event", "session", "image"])
def test_hitl_study_guard_prevents_invalidating_existing_events(tmp_path, monkeypatch, target):
    engine = _new_database(tmp_path)
    database = _initialize_engine(
        engine, tmp_path, monkeypatch, database_filename="reference-integrity.sqlite3"
    )
    try:
        database.init_db()
        _add_other_study_image(engine)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO hitl_events "
                    "(id, event_id, session_id, task_id, image_id, prediction_id, seq, event_type, "
                    "client_utc, elapsed_ms, session_elapsed_ms, payload_hash, actor_id) "
                    "VALUES ('guard-event', 'guard-key', 'session-1', 'guard-task', 'image-1', NULL, "
                    "1, 'SESSION_START', '2026-10-21T00:00:00Z', 0, 0, 'hash', 'doctor-1')"
                )
            )

        updates = {
            "event": "UPDATE hitl_events SET image_id = 'image-3' WHERE id = 'guard-event'",
            "session": "UPDATE hitl_sessions SET study_id = 'study-2' WHERE id = 'session-1'",
            "image": "UPDATE images SET study_id = 'study-2' WHERE id = 'image-1'",
        }
        _assert_integrity_error(engine, updates[target], {})
    finally:
        engine.dispose()


def _add_other_study_image(engine):
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO patients (id, anonymized_pid) VALUES ('patient-2', 'pid-2')")
        )
        connection.execute(
            text(
                "INSERT INTO studies "
                "(id, patient_id, study_date, status, ovary_side, contralateral_status, review_revision) "
                "VALUES ('study-2', 'patient-2', '2026-10-21', 'PENDING', 'BOTH', 'NOT_VISUALIZED', 0)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO images (id, study_id, filename, raw_path) "
                "VALUES ('image-3', 'study-2', 'other.png', 'other.png')"
            )
        )


def test_partial_prediction_index_does_not_satisfy_composite_reference_key(tmp_path):
    from backend.db.database import _ensure_prediction_reference_key

    engine = create_engine(f"sqlite:///{tmp_path / 'partial-prediction-key.sqlite3'}")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE predictions (id VARCHAR(36) PRIMARY KEY, image_id VARCHAR(36))"
            )
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX old_partial_prediction_key "
                "ON predictions(id, image_id) WHERE image_id IS NOT NULL"
            )
            _ensure_prediction_reference_key(connection)

            indexes = connection.exec_driver_sql("PRAGMA index_list(predictions)").all()
            assert any(
                row[2]
                and not row[4]
                and [column[2] for column in connection.exec_driver_sql(
                    f'PRAGMA index_info("{row[1]}")'
                )]
                == ["id", "image_id"]
                for row in indexes
            )
    finally:
        engine.dispose()


def _legacy_database(tmp_path, *, mismatched_review=False, cross_study_event=False):
    from backend.db.database import HITLEventModel, PredictionModel, ReviewModel

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy-reference-integrity.sqlite3'}")
    legacy_tables = {
        PredictionModel.__tablename__,
        ReviewModel.__tablename__,
        HITLEventModel.__tablename__,
    }
    for table in Base.metadata.sorted_tables:
        if table.name not in legacy_tables:
            table.create(engine, checkfirst=True)

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE predictions ("
            "id VARCHAR(36) NOT NULL PRIMARY KEY, image_id VARCHAR(36) NOT NULL, "
            "model_version VARCHAR(100), inference_time_ms INTEGER, confidence_score FLOAT, iqa_score FLOAT, "
            "raw_mask_rle JSON NOT NULL, measurements JSON NOT NULL, provenance_json JSON, created_at DATETIME)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE reviews ("
            "id VARCHAR(36) NOT NULL PRIMARY KEY, image_id VARCHAR(36) NOT NULL REFERENCES images(id), "
            "prediction_id VARCHAR(36), doctor_id VARCHAR(64), doctor_action VARCHAR(30), "
            "verified_mask_rle JSON NOT NULL, max_diameter_mm FLOAT, ortho_diameter_mm FLOAT, "
            "total_area_cm2 FLOAT, lesion_type VARCHAR(100), clinical_notes TEXT, "
            "time_spent_seconds INTEGER, hitl_feedback JSON, is_official_ground_truth BOOLEAN, created_at DATETIME)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE hitl_events ("
            "id VARCHAR(36) NOT NULL PRIMARY KEY, event_id VARCHAR(36) NOT NULL UNIQUE, "
            "session_id VARCHAR(36) NOT NULL REFERENCES hitl_sessions(id), task_id VARCHAR(36) NOT NULL, "
            "image_id VARCHAR(36) NOT NULL, prediction_id VARCHAR(36), seq INTEGER NOT NULL, "
            "event_type VARCHAR(50) NOT NULL, client_utc VARCHAR(50) NOT NULL, elapsed_ms FLOAT NOT NULL, "
            "session_elapsed_ms FLOAT NOT NULL, payload_hash VARCHAR(64) NOT NULL, payload JSON, "
            "actor_id VARCHAR(64) NOT NULL, received_at DATETIME, UNIQUE(session_id, task_id, seq))"
        )
        connection.exec_driver_sql("CREATE INDEX ix_hitl_events_session_id ON hitl_events(session_id)")
        connection.exec_driver_sql("CREATE INDEX ix_hitl_events_task_id ON hitl_events(task_id)")
        connection.exec_driver_sql("CREATE UNIQUE INDEX ix_hitl_events_event_id ON hitl_events(event_id)")
        connection.exec_driver_sql(
            "INSERT INTO patients (id, anonymized_pid) VALUES ('patient-1', 'pid-1')"
        )
        connection.exec_driver_sql(
            "INSERT INTO studies "
            "(id, patient_id, study_date, status, ovary_side, contralateral_status, review_revision) "
            "VALUES ('study-1', 'patient-1', '2026-10-21', 'PENDING', 'BOTH', 'NOT_VISUALIZED', 0)"
        )
        connection.exec_driver_sql(
            "INSERT INTO images (id, study_id, filename, raw_path) VALUES "
            "('image-1', 'study-1', 'right.png', 'right.png'), "
            "('image-2', 'study-1', 'left.png', 'left.png')"
        )
        connection.exec_driver_sql(
            "INSERT INTO predictions (id, image_id, raw_mask_rle, measurements) "
            "VALUES ('prediction-1', 'image-1', '[]', '{}')"
        )
        connection.exec_driver_sql(
            "INSERT INTO hitl_sessions "
            "(id, study_id, actor_id, participant_code, participant_role, data_origin, status) "
            "VALUES ('session-1', 'study-1', 'doctor-1', 'participant-1', 'clinician', 'live', 'IN_PROGRESS')"
        )
        if cross_study_event:
            connection.exec_driver_sql(
                "INSERT INTO patients (id, anonymized_pid) VALUES ('patient-2', 'pid-2')"
            )
            connection.exec_driver_sql(
                "INSERT INTO studies "
                "(id, patient_id, study_date, status, ovary_side, contralateral_status, review_revision) "
                "VALUES ('study-2', 'patient-2', '2026-10-21', 'PENDING', 'BOTH', 'NOT_VISUALIZED', 0)"
            )
            connection.exec_driver_sql(
                "INSERT INTO images (id, study_id, filename, raw_path) "
                "VALUES ('image-3', 'study-2', 'other.png', 'other.png')"
            )
        connection.exec_driver_sql(
            "INSERT INTO reviews (id, image_id, prediction_id, doctor_action, verified_mask_rle) "
            "VALUES ('review-1', ?, 'prediction-1', 'ACCEPTED_RAW', '[]')",
            ("image-2" if mismatched_review else "image-1",),
        )
        connection.exec_driver_sql(
            "INSERT INTO hitl_events "
            "(id, event_id, session_id, task_id, image_id, prediction_id, seq, event_type, "
            "client_utc, elapsed_ms, session_elapsed_ms, payload_hash, actor_id) "
            "VALUES ('event-1', 'event-key-1', 'session-1', 'task-1', ?, ?, "
            "1, 'SESSION_START', '2026-10-21T00:00:00Z', 0, 0, 'hash', 'doctor-1')",
            ("image-3" if cross_study_event else "image-1", None if cross_study_event else "prediction-1"),
        )
    return engine


def _initialize_engine(engine, tmp_path, monkeypatch, database_filename="legacy-reference-integrity.sqlite3"):
    from backend.db import database

    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / database_filename))
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.delenv("APP_DOCTOR_PASSWORD", raising=False)
    monkeypatch.delenv("APP_ADMIN_PASSWORD", raising=False)
    return database


def test_init_db_migrates_legacy_reference_keys_without_losing_rows(tmp_path, monkeypatch):
    engine = _legacy_database(tmp_path)
    database = _initialize_engine(engine, tmp_path, monkeypatch)
    try:
        database.init_db()
        database.init_db()

        with engine.connect() as connection:
            assert connection.execute(text("SELECT id FROM reviews")).scalar_one() == "review-1"
            assert connection.execute(text("SELECT id FROM hitl_events")).scalar_one() == "event-1"
            assert connection.execute(text("PRAGMA foreign_key_check")).all() == []

            event_indexes = {
                row[1] for row in connection.exec_driver_sql("PRAGMA index_list(hitl_events)")
            }
            assert {"ix_hitl_events_event_id", "ix_hitl_events_session_id", "ix_hitl_events_task_id"} <= event_indexes
            prediction_indexes = connection.exec_driver_sql("PRAGMA index_list(predictions)").all()
            prediction_fks = connection.exec_driver_sql("PRAGMA foreign_key_list(predictions)").all()
            assert any(
                row[2] == "images" and row[3] == "image_id" and row[4] == "id"
                for row in prediction_fks
            )
            assert any(
                row[2]
                and [column[2] for column in connection.exec_driver_sql(
                    f'PRAGMA index_info("{row[1]}")'
                )]
                == ["id", "image_id"]
                for row in prediction_indexes
            )
    finally:
        engine.dispose()


def test_init_db_rolls_back_legacy_table_rebuild_on_cross_image_reference(tmp_path, monkeypatch):
    engine = _legacy_database(tmp_path, mismatched_review=True)
    database = _initialize_engine(engine, tmp_path, monkeypatch)
    try:
        with pytest.raises(RuntimeError, match="SQLite schema migration failed"):
            database.init_db()

        with engine.connect() as connection:
            assert connection.execute(text("SELECT image_id FROM reviews WHERE id = 'review-1'")).scalar_one() == "image-2"
            assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
            prediction_indexes = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'uq_prediction_id_image'")
            ).all()
            assert prediction_indexes == []
            review_fks = connection.exec_driver_sql("PRAGMA foreign_key_list(reviews)").all()
            assert not any(row[2] == "predictions" for row in review_fks)
            prediction_fks = connection.exec_driver_sql("PRAGMA foreign_key_list(predictions)").all()
            assert not any(row[2] == "images" for row in prediction_fks)
    finally:
        engine.dispose()


def test_init_db_rejects_legacy_cross_study_hitl_events(tmp_path, monkeypatch):
    engine = _legacy_database(tmp_path, cross_study_event=True)
    database = _initialize_engine(engine, tmp_path, monkeypatch)
    try:
        with pytest.raises(RuntimeError, match="SQLite schema migration failed"):
            database.init_db()

        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT image_id FROM hitl_events WHERE id = 'event-1'")
            ).scalar_one() == "image-3"
            triggers = connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'trigger' AND name LIKE 'trg_hitl_%'")
            ).all()
            assert triggers == []
    finally:
        engine.dispose()


def test_init_db_rejects_existing_rows_that_violate_declared_foreign_keys(tmp_path, monkeypatch):
    engine = _new_database(tmp_path)
    db_path = tmp_path / "reference-integrity.sqlite3"
    raw_connection = sqlite3.connect(db_path)
    try:
        raw_connection.execute("PRAGMA foreign_keys=OFF")
        raw_connection.execute(
            "INSERT INTO reviews (id, image_id, prediction_id, doctor_action, verified_mask_rle) "
            "VALUES ('legacy-bad-review', 'image-2', 'prediction-1', 'ACCEPTED_RAW', '[]')"
        )
        raw_connection.commit()
    finally:
        raw_connection.close()

    database = _initialize_engine(engine, tmp_path, monkeypatch)
    try:
        with pytest.raises(RuntimeError, match="SQLite schema migration failed"):
            database.init_db()

        with engine.connect() as connection:
            assert connection.execute(
                text("SELECT id FROM reviews WHERE id = 'legacy-bad-review'")
            ).scalar_one() == "legacy-bad-review"
            assert connection.execute(text("PRAGMA foreign_key_check(reviews)")).all()
    finally:
        engine.dispose()
