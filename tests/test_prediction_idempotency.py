"""Persistence and privacy contracts for retry-safe inference requests."""

import sqlite3
from uuid import uuid4

from backend.core.prediction_idempotency import prediction_idempotency_digests
from backend.db.database import _migrate_prediction_idempotency_on_connection


def test_prediction_idempotency_digest_is_actor_and_payload_scoped():
    key = uuid4()
    payload = {"image_id": "synthetic-image", "source_sha256": "a" * 64, "pixel_spacing_mm": 0.1}

    owner_digests = prediction_idempotency_digests(key, "doctor-one", payload)
    assert prediction_idempotency_digests(key, "doctor-one", payload) == owner_digests
    assert prediction_idempotency_digests(key, "doctor-two", payload) != owner_digests
    assert prediction_idempotency_digests(key, "doctor-one", {**payload, "pixel_spacing_mm": 0.2}) != owner_digests
    assert str(key) not in owner_digests[0]


def test_legacy_prediction_table_migrates_idempotency_and_response_fields():
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE TABLE predictions (id VARCHAR(36) PRIMARY KEY, image_id VARCHAR(36))")
        _migrate_prediction_idempotency_on_connection(connection.cursor())
        columns = {row[1] for row in connection.execute("PRAGMA table_info(predictions)")}
        assert {
            "idempotency_key_digest",
            "idempotency_request_digest",
            "response_extras_json",
        } <= columns

        digest = "c" * 64
        connection.execute(
            "INSERT INTO predictions (id, idempotency_key_digest) VALUES (?, ?)", ("one", digest)
        )
        try:
            connection.execute(
                "INSERT INTO predictions (id, idempotency_key_digest) VALUES (?, ?)", ("two", digest)
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("Prediction idempotency digest must be unique.")
        connection.execute(
            "INSERT INTO predictions (id, idempotency_key_digest) VALUES (?, NULL)", ("legacy-one",)
        )
        connection.execute(
            "INSERT INTO predictions (id, idempotency_key_digest) VALUES (?, NULL)", ("legacy-two",)
        )
    finally:
        connection.close()
