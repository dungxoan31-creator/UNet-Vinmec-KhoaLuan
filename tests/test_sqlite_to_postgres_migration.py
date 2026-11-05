"""Test suite for SQLite to PostgreSQL migration engine."""

import os
import sqlite3
from unittest.mock import MagicMock
import pytest
from backend.db.database import Base
from scripts.migrate_sqlite_to_postgres import (
    canonical_row_hash,
    compute_sqlite_table_stats,
    migrate,
    verify_postgresql_constraints_and_indexes,
    TABLE_ORDER,
)


def test_canonical_row_hash_is_deterministic():
    row1 = {"id": 1, "name": "test", "data": None, "is_active": True}
    row2 = {"data": None, "is_active": True, "id": 1, "name": "test"}
    assert canonical_row_hash(row1) == canonical_row_hash(row2)
    assert len(canonical_row_hash(row1)) == 64


def test_compute_sqlite_table_stats(tmp_path):
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE test_tab (id INTEGER PRIMARY KEY, val TEXT)")
    conn.execute("INSERT INTO test_tab VALUES (1, 'alpha'), (2, 'beta')")
    conn.commit()

    count, chk = compute_sqlite_table_stats(conn, "test_tab")
    assert count == 2
    assert len(chk) == 64

    # Non-existent table returns 0
    empty_count, empty_chk = compute_sqlite_table_stats(conn, "missing_tab")
    assert empty_count == 0
    conn.close()


def test_dry_run_migration(tmp_path):
    db_file = tmp_path / "sample.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE patients (id TEXT PRIMARY KEY, anonymized_pid TEXT)")
    conn.execute("INSERT INTO patients VALUES ('p1', 'PID-001')")
    conn.commit()
    conn.close()

    success = migrate(str(db_file), "", dry_run=True)
    assert success is True


def test_topological_table_order_has_required_clinical_entities():
    required = ["patients", "studies", "images", "predictions", "reviews", "users", "facilities", "audit_logs"]
    for ent in required:
        assert ent in TABLE_ORDER


def test_topological_table_order_covers_all_database_tables():
    """Verify that every table defined in Base.metadata exists in TABLE_ORDER."""
    metadata_tables = set(Base.metadata.tables.keys())
    ordered_tables = set(TABLE_ORDER)
    missing = metadata_tables - ordered_tables
    assert not missing, f"Tables missing from TABLE_ORDER: {missing}"


def test_verify_postgresql_constraints_mocked():
    """Verify the constraint verification helper catches missing indexes/triggers."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Case 1: All present
    mock_cursor.fetchone.side_effect = [(1,), (0,)]  # index found, 0 orphaned studies
    mock_cursor.fetchall.return_value = [("trg_audit_logs_no_update",), ("trg_audit_logs_no_delete",)]
    errors = verify_postgresql_constraints_and_indexes(mock_conn)
    assert errors == []

    # Case 2: Missing index and trigger
    mock_cursor.fetchone.side_effect = [None, (3,)]  # index missing, 3 orphaned studies
    mock_cursor.fetchall.return_value = []  # triggers missing
    errors = verify_postgresql_constraints_and_indexes(mock_conn)
    assert len(errors) == 4
    assert any("ix_studies_facility_status_created" in e for e in errors)
    assert any("trg_audit_logs_no_update" in e for e in errors)
    assert any("trg_audit_logs_no_delete" in e for e in errors)
    assert any("3 studies referencing" in e for e in errors)
