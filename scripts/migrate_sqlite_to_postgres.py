#!/usr/bin/env python3
"""SQLite to PostgreSQL Database Migration Engine for Ovarian Ultrasound AI.

Author: DevOps & Enterprise Deployment Team
Compliant with: FDA 21 CFR Part 11, ISO 27799, ACR O-RADS US v2022

Migrates all clinical entities with deterministic SHA-256 table checksums,
record count verification, foreign key topological order preservation,
PostgreSQL sequence synchronization, schema validation, and atomic transaction rollback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration.sqlite2pg")

# Strict topological insertion order respecting foreign key constraints across 26 models
TABLE_ORDER = [
    # Level 0: Root independent entities
    "facilities",
    # Level 1: Facility-scoped intake identities and other facility roots
    "patient_directory",
    "patients",
    "visit_number_sequences",
    "pending_file_deletions",
    "audit_logs",
    "email_verification_challenges",
    "consumed_password_reset_tokens",
    "auth_rate_limits",
    # Level 2: Users (facility_id) and Visits (facility_id, patient_id)
    "users",
    "visits",
    # Level 3: Studies (patient_id, patient_directory_id, visit_id, facility_id, assignee_id)
    "studies",
    # Level 4: Images & case lifecycle dependent on studies / users
    "images",
    "case_leases",
    "review_batches",
    "ui_events",
    "notifications",
    "correction_requests",
    # Level 5: Predictions & reviews dependent on images
    "predictions",
    "reviews",
    # Level 6: Active learning queue & confirmed region batches
    "active_learning_queue",
    "region_assignment_batches",
    # Level 7: Caliper measurement events
    "region_caliper_events",
    # Level 8: CDSS rule assessments (tied to calipers & region assignments)
    "region_cdss_assessments",
    # Level 9: HITL sessions & fine-grained UX telemetry
    "hitl_sessions",
    "hitl_events",
]


def canonical_row_hash(row: dict[str, Any]) -> str:
    """Generate deterministic canonical sha256 hash for a row across SQLite and PostgreSQL."""
    normalized: dict[str, Any] = {}
    for k, v in sorted(row.items()):
        if isinstance(v, bytes):
            normalized[k] = hashlib.sha256(v).hexdigest()
        elif isinstance(v, datetime):
            normalized[k] = v.isoformat()
        elif isinstance(v, bool):
            normalized[k] = "true" if v else "false"
        elif v is None:
            normalized[k] = None
        else:
            normalized[k] = str(v)
    data_str = json.dumps(normalized, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(data_str.encode("utf-8")).hexdigest()


def compute_sqlite_table_stats(conn: sqlite3.Connection, table: str) -> tuple[int, str]:
    """Compute row count and cumulative deterministic SHA-256 checksum for a table in SQLite."""
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT * FROM {table} ORDER BY rowid ASC")
    except sqlite3.OperationalError:
        return 0, hashlib.sha256(b"").hexdigest()

    rows = cursor.fetchall()
    count = len(rows)
    hasher = hashlib.sha256()
    for row in rows:
        row_dict = dict(row)
        hasher.update(canonical_row_hash(row_dict).encode("ascii"))
    return count, hasher.hexdigest()


def setup_postgresql_schema(pg_url: str) -> bool:
    """Initialize PostgreSQL tables, indexes, and immutability triggers via SQLAlchemy."""
    logger.info("Initializing PostgreSQL schema using SQLAlchemy models...")
    os.environ["DATABASE_URL"] = pg_url
    try:
        from backend.db.database import Base, _ensure_audit_immutability_postgres, create_engine
        norm_url = pg_url
        if norm_url.startswith("postgres://"):
            norm_url = "postgresql+psycopg://" + norm_url[len("postgres://"):]
        elif norm_url.startswith("postgresql://") and not norm_url.startswith("postgresql+psycopg://"):
            norm_url = "postgresql+psycopg://" + norm_url[len("postgresql://"):]

        engine = create_engine(norm_url, pool_pre_ping=True)
        Base.metadata.create_all(bind=engine, checkfirst=True)
        _ensure_audit_immutability_postgres(engine)
        logger.info("PostgreSQL schema created and verified successfully.")
        return True
    except Exception as exc:
        logger.error("Failed to setup PostgreSQL schema: %s", exc)
        return False


def verify_postgresql_constraints_and_indexes(pg_conn) -> list[str]:
    """Verify PostgreSQL-specific requirements: composite index, audit triggers, multi-facility integrity."""
    errors = []
    with pg_conn.cursor() as cur:
        # 1. Composite Index ix_studies_facility_status_created
        cur.execute(
            "SELECT 1 FROM pg_indexes WHERE tablename = 'studies' AND indexname = 'ix_studies_facility_status_created';"
        )
        if not cur.fetchone():
            errors.append("Missing composite index 'ix_studies_facility_status_created' on studies table.")

        # 2. Audit immutability triggers
        cur.execute(
            "SELECT tgname FROM pg_trigger WHERE tgname IN ('trg_audit_logs_no_update', 'trg_audit_logs_no_delete');"
        )
        found_triggers = {row[0] for row in cur.fetchall()}
        if "trg_audit_logs_no_update" not in found_triggers:
            errors.append("Missing audit trigger 'trg_audit_logs_no_update' on audit_logs.")
        if "trg_audit_logs_no_delete" not in found_triggers:
            errors.append("Missing audit trigger 'trg_audit_logs_no_delete' on audit_logs.")

        # 3. Multi-facility consistency: verify studies with facility_id exist in facilities
        cur.execute(
            """
            SELECT COUNT(*) FROM studies s
            WHERE s.facility_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM facilities f WHERE f.id = s.facility_id);
            """
        )
        orphaned_studies = cur.fetchone()[0]
        if orphaned_studies > 0:
            errors.append(f"Found {orphaned_studies} studies referencing non-existent facility_id.")

    return errors


def migrate(
    sqlite_path: str,
    pg_url: str,
    dry_run: bool = False,
    setup_schema: bool = False,
    verify_only: bool = False,
) -> bool:
    """Perform atomic migration from SQLite to PostgreSQL with data type adaptation and validation."""
    if not os.path.exists(sqlite_path):
        logger.error("Source SQLite database not found: %s", sqlite_path)
        return False

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        logger.error("psycopg v3 is required for PostgreSQL migration. Please install psycopg[binary].")
        return False

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    # Discover tables present in source SQLite database
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    existing_tables = {row[0] for row in cursor.fetchall()}

    tables_to_migrate = [t for t in TABLE_ORDER if t in existing_tables]
    for t in existing_tables:
        if t not in tables_to_migrate and not t.startswith("alembic_"):
            tables_to_migrate.append(t)

    logger.info("Found %d tables to migrate: %s", len(tables_to_migrate), tables_to_migrate)

    # Pre-migration statistics from SQLite
    sqlite_stats: dict[str, tuple[int, str]] = {}
    for table in tables_to_migrate:
        count, chk = compute_sqlite_table_stats(sqlite_conn, table)
        sqlite_stats[table] = (count, chk)
        logger.info("Source SQLite table '%s': %d rows, checksum=%s", table, count, chk[:16])

    if dry_run:
        logger.info("[DRY RUN] Source database analyzed successfully. No changes written.")
        sqlite_conn.close()
        return True

    # Normalize connection URL for psycopg
    norm_pg_url = pg_url
    if norm_pg_url.startswith("postgresql+psycopg://"):
        norm_pg_url = "postgresql://" + norm_pg_url[len("postgresql+psycopg://"):]

    if setup_schema:
        if not setup_postgresql_schema(pg_url):
            sqlite_conn.close()
            return False

    try:
        with psycopg.connect(norm_pg_url) as pg_conn:
            if not verify_only:
                with pg_conn.transaction():
                    with pg_conn.cursor() as pg_cursor:
                        # Attempt to set replication role to bypass FK checks during load if superuser
                        try:
                            pg_cursor.execute("SET session_replication_role = 'replica';")
                        except Exception as e:
                            logger.info("Notice: Running in standard session role (non-superuser): %s", e)

                        for table in tables_to_migrate:
                            count, _ = sqlite_stats[table]
                            if count == 0:
                                logger.info("Skipping empty table '%s'", table)
                                continue

                            # Inspect PostgreSQL column data types for type coercion (e.g. boolean)
                            pg_cursor.execute(
                                """
                                SELECT column_name, data_type
                                FROM information_schema.columns
                                WHERE table_name = %s;
                                """,
                                (table,),
                            )
                            pg_col_types = {row[0]: row[1].lower() for row in pg_cursor.fetchall()}
                            boolean_cols = {col for col, dt in pg_col_types.items() if dt == "boolean"}

                            # Read SQLite data
                            cur = sqlite_conn.cursor()
                            cur.execute(f"SELECT * FROM {table}")
                            columns = [desc[0] for desc in cur.description]
                            rows = cur.fetchall()

                            # Coerce values: SQLite integers (1/0) -> Python booleans for PostgreSQL boolean columns
                            adapted_tuples = []
                            for row in rows:
                                row_vals = []
                                for idx, col in enumerate(columns):
                                    val = row[idx]
                                    if col in boolean_cols and val is not None:
                                        row_vals.append(bool(val))
                                    else:
                                        row_vals.append(val)
                                adapted_tuples.append(tuple(row_vals))

                            cols_clause = ", ".join(f'"{c}"' for c in columns)
                            placeholders = ", ".join(["%s"] * len(columns))
                            insert_query = f'INSERT INTO "{table}" ({cols_clause}) VALUES ({placeholders})'

                            pg_cursor.executemany(insert_query, adapted_tuples)
                            logger.info("Migrated %d rows into PostgreSQL '%s'", len(adapted_tuples), table)

                        # Reset serial sequences (e.g. audit_logs.id)
                        for table in tables_to_migrate:
                            try:
                                pg_cursor.execute(f"SELECT pg_get_serial_sequence('{table}', 'id');")
                                seq_name = pg_cursor.fetchone()[0]
                                if seq_name:
                                    pg_cursor.execute(
                                        f"SELECT setval('{seq_name}', COALESCE((SELECT MAX(id) FROM \"{table}\"), 1));"
                                    )
                                    logger.info("Synchronized PostgreSQL sequence '%s' for table '%s'", seq_name, table)
                            except Exception:
                                pass

                        # Restore replication role
                        try:
                            pg_cursor.execute("SET session_replication_role = 'DEFAULT';")
                        except Exception:
                            pass

                logger.info("Data insertion transaction committed successfully.")

            # Verification Phase
            with pg_conn.cursor(row_factory=dict_row) as pg_cursor:
                validation_errors = []
                for table in tables_to_migrate:
                    expected_count, expected_chk = sqlite_stats[table]
                    pg_cursor.execute(f'SELECT * FROM "{table}"')
                    pg_rows = pg_cursor.fetchall()
                    pg_count = len(pg_rows)

                    hasher = hashlib.sha256()
                    for row in pg_rows:
                        hasher.update(canonical_row_hash(dict(row)).encode("ascii"))
                    pg_chk = hasher.hexdigest()

                    if pg_count != expected_count:
                        validation_errors.append(
                            f"Table '{table}' count mismatch: SQLite={expected_count}, Postgres={pg_count}"
                        )
                    elif expected_count > 0 and pg_chk != expected_chk:
                        validation_errors.append(
                            f"Table '{table}' checksum mismatch: SQLite={expected_chk[:16]}, Postgres={pg_chk[:16]}"
                        )
                    else:
                        logger.info("Table '%s' validation PASSED (rows=%d, checksum=%s)", table, pg_count, pg_chk[:16])

                # Check PostgreSQL constraints & immutability triggers
                constraint_errors = verify_postgresql_constraints_and_indexes(pg_conn)
                if constraint_errors:
                    validation_errors.extend(constraint_errors)

                if validation_errors:
                    logger.error("Migration validation failed with %d error(s):", len(validation_errors))
                    for err in validation_errors:
                        logger.error("  - %s", err)
                    return False

            logger.info("ALL TABLES & CLINICAL CONSTRAINTS PASSED VALIDATION.")
            return True

    except Exception as exc:
        logger.error("Migration encountered error: %s", exc)
        return False
    finally:
        sqlite_conn.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite clinical database to PostgreSQL")
    parser.add_argument(
        "--sqlite-path",
        default=os.environ.get("APP_DB_PATH", "ovarian_ai.db"),
        help="Path to source SQLite database file",
    )
    parser.add_argument(
        "--pg-url",
        default=os.environ.get("DATABASE_URL"),
        help="Target PostgreSQL connection URL (e.g., postgresql://user:pass@host:5432/dbname)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze and verify source SQLite database without writing to PostgreSQL",
    )
    parser.add_argument(
        "--setup-schema",
        action="store_true",
        help="Initialize target PostgreSQL schema, tables, and triggers before migrating",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip data insertion and run post-migration checksum & constraint verification only",
    )
    args = parser.parse_args()

    if not args.pg_url and not args.dry_run:
        logger.error("PostgreSQL URL is required (provide --pg-url or set DATABASE_URL).")
        sys.exit(1)

    success = migrate(
        args.sqlite_path,
        args.pg_url or "",
        dry_run=args.dry_run,
        setup_schema=args.setup_schema,
        verify_only=args.verify_only,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
