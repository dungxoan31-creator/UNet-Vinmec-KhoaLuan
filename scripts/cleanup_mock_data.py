"""Remove explicitly marked synthetic runtime cases, with a consistent SQLite backup."""

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

MARKERS = ("DEMO", "MOCK", "TEST", "E2E", "SMOKE", "OTHER_PID", "ANON-TEST")


def cleanup(database: Path, backup_dir: Path, *, apply: bool = False) -> dict:
    database = database.resolve(strict=True)
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        predicate = " OR ".join("UPPER(p.anonymized_pid) GLOB ?" for _ in MARKERS)
        db.execute("CREATE TEMP TABLE selected_studies (id TEXT PRIMARY KEY)")
        db.execute(
            f"INSERT INTO selected_studies SELECT s.id FROM studies s JOIN patients p ON p.id=s.patient_id WHERE {predicate}",
            tuple(f"{marker}*" for marker in MARKERS),
        )
        if "hitl_sessions" in tables:
            db.execute("INSERT OR IGNORE INTO selected_studies SELECT study_id FROM hitl_sessions WHERE data_origin IN ('demo', 'technical_fixture') AND study_id NOT IN (SELECT study_id FROM hitl_sessions WHERE data_origin='live')")
        db.execute("CREATE TEMP TABLE selected_images AS SELECT id, raw_path FROM images WHERE study_id IN (SELECT id FROM selected_studies)")
        db.execute("CREATE TEMP TABLE selected_patients AS SELECT DISTINCT patient_id AS id FROM studies WHERE id IN (SELECT id FROM selected_studies)")
        predicates = [
            ("hitl_events", "session_id IN (SELECT id FROM hitl_sessions WHERE study_id IN (SELECT id FROM selected_studies))"),
            ("hitl_sessions", "study_id IN (SELECT id FROM selected_studies)"),
            ("review_batches", "study_id IN (SELECT id FROM selected_studies)"),
            ("reviews", "image_id IN (SELECT id FROM selected_images)"),
            ("predictions", "image_id IN (SELECT id FROM selected_images)"),
            ("images", "id IN (SELECT id FROM selected_images)"),
            ("studies", "id IN (SELECT id FROM selected_studies)"),
            ("patients", "id IN (SELECT id FROM selected_patients) AND id NOT IN (SELECT patient_id FROM studies WHERE id NOT IN (SELECT id FROM selected_studies))"),
        ]
        counts = {
            table: db.execute(f'SELECT COUNT(*) FROM "{table}" WHERE {where}').fetchone()[0]
            for table, where in predicates if table in tables
        }
        result = {"applied": False, "records": counts}
        if not apply or not any(counts.values()):
            db.rollback()
            return result
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"{database.stem}-before-cleanup-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.sqlite3"
        # A separate read connection can back up the original database while this connection
        # holds the write reservation, before any deletion occurs.
        with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as source:
            with sqlite3.connect(backup) as destination:
                source.backup(destination)
        for table, where in predicates:
            if table in tables:
                db.execute(f'DELETE FROM "{table}" WHERE {where}')
        violations = db.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError("Foreign-key validation failed; cleanup rolled back.")
        if "audit_logs" in tables:
            db.execute(
                "INSERT INTO audit_logs (entity_name, entity_id, action_type, actor_id, details, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                ("database", "runtime", "MOCK_DATA_CLEANUP", "maintenance", json.dumps(counts), datetime.now(UTC).isoformat()),
            )
        db.commit()
        return {**result, "applied": True, "backup": str(backup)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(cleanup(args.database, args.backup_dir, apply=args.apply), indent=2))
