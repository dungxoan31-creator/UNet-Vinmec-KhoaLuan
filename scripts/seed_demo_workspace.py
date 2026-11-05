"""Create an isolated, synthetic-only workspace dataset for local product demos.

This script never writes to the project-root ovarian_ai.db. It creates a separate
SQLite database and uses only allowlisted synthetic E2E images. It does not create
patient records, clinical predictions, or clinician reviews.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIXTURE_NAMES = (
    "synthetic_left.png",
    "synthetic_right.png",
    "synthetic_letterbox_640x480.png",
    "synthetic_left.jpg",
    "synthetic_ovary.dcm",
)
STAFF = (
    ("Pham Minh Anh", "anhpm"), ("Vo Thanh Binh", "binhvt"),
    ("Dang Quoc Cuong", "cuongdq"), ("Bui Ngoc Diep", "diepbn"),
    ("Hoang Thu Ha", "hath"), ("Phan Duc Huy", "huypd"),
    ("Do Thi Huong", "huongdt"), ("Ngo Gia Khanh", "khanhng"),
    ("Duong Mai Lan", "landm"), ("Ly Quang Minh", "minhlq"),
    ("Trinh Hoai Nam", "namth"), ("Cao Thi Ngoc", "ngocct"),
    ("Vu Hoang Oanh", "oanhvh"), ("Ha Duc Phuc", "phuchd"),
    ("Ta Minh Quan", "quantm"), ("Lam Thi Thu", "thult"),
    ("Mai Quoc Tuan", "tuanmq"), ("Chu Van Viet", "vietcv"),
    ("Nguyen Thi Xuan", "xuannt"), ("Dinh Hai Yen", "yendh"),
    ("Pham Thi Anh", "anhpt"), ("Vo Minh Chau", "chauvm"),
    ("Dang Thu Trang", "trangdt"), ("Bui Van Khoa", "khoabv"),
    ("Hoang Duc Long", "longhd"), ("Phan Ngoc Ha", "haphn"),
    ("Do Minh Tam", "tamdm"), ("Ngo Thi Van", "vannt"),
    ("Duong Quoc Bao", "baodq"), ("Ly Thanh Tung", "tunglt"),
    ("Trinh Ngoc Mai", "maitn"), ("Cao Duc Son", "soncd"),
    ("Vu Thi Lien", "lienvt"), ("Ha Minh Duc", "duchm"),
    ("Ta Quynh Nhu", "nhutq"), ("Lam Hoang Phuong", "phuonglh"),
    ("Mai Thanh Thao", "thaomt"), ("Chu Nhat Minh", "minhcn"),
    ("Nguyen Bao Chau", "chaunb"), ("Dinh Thu Hien", "hiendt"),
)
DEMO_PASSWORD = "123456@"
ADMIN_PASSWORD = "DemoAdmin@2026!"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_paths(data_dir: Path) -> tuple[Path, Path]:
    resolved = data_dir.resolve()
    project_data = (ROOT / "data").resolve()
    project_root_db = (ROOT / "ovarian_ai.db").resolve()
    if resolved == ROOT.resolve() or resolved == project_data:
        raise SystemExit("Refusing to seed the project root or shared data directory.")
    if resolved in project_root_db.parents or project_root_db in resolved.parents:
        raise SystemExit("Demo data directory must be separate from the project-root database.")
    db_path = (resolved / "ovarian_ai.db").resolve()
    if resolved not in db_path.parents:
        raise SystemExit("Demo database path must stay inside the requested data directory.")
    return resolved, db_path


def _is_resumable_empty_seed(data_dir: Path, db_path: Path) -> bool:
    """Accept only this script's exact pre-insert layout after an interrupted run."""
    allowed_files = {"ovarian_ai.db", ".patient_pid_hmac_secret", ".app_jwt_secret"}
    allowed_files.update(f"uploads/synthetic-demo/{name}" for name in FIXTURE_NAMES)
    allowed_dirs = {"uploads", "uploads/synthetic-demo"}
    for path in data_dir.rglob("*"):
        relative = path.relative_to(data_dir).as_posix()
        if path.is_dir():
            if relative not in allowed_dirs:
                return False
        elif relative not in allowed_files:
            return False
    if not db_path.exists() or db_path.stat().st_size == 0:
        return True
    try:
        connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        try:
            tables = [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )]
            return all(connection.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone() is None for table in tables)
        finally:
            connection.close()
    except sqlite3.Error:
        return False


def seed(data_dir: Path, case_count: int) -> dict:
    data_dir, db_path = _safe_paths(data_dir)
    manifest_path = data_dir / "DEMO_DATA_MANIFEST.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("database") != str(db_path):
            raise SystemExit("Existing demo manifest points to a different database; refusing to reuse it.")
        for secret_name in (".patient_pid_hmac_secret", ".app_jwt_secret"):
            secret_path = data_dir / secret_name
            if not secret_path.exists():
                secret_path.write_text(secrets.token_urlsafe(48), encoding="ascii")
        return {"status": "already_seeded", **manifest["counts"], "database": str(db_path)}
    if data_dir.exists() and any(data_dir.iterdir()) and not _is_resumable_empty_seed(data_dir, db_path):
        raise SystemExit("Target exists and is not an empty demo directory; refusing to modify it.")
    if case_count < 4 or case_count > 500 or case_count % 4:
        raise SystemExit("case-count must be divisible by four and between 4 and 500.")

    fixture_dir = ROOT / "artifacts" / "synthetic_fixtures"
    fixtures = []
    for name in FIXTURE_NAMES:
        source = fixture_dir / name
        if not source.is_file():
            raise SystemExit(f"Required synthetic fixture is missing: {source}")
        fixtures.append((source, _sha256(source)))

    os.environ.pop("DATABASE_URL", None)
    os.environ["APP_DATA_DIR"] = str(data_dir)
    os.environ["APP_DB_PATH"] = str(db_path)
    os.environ["APP_SYNTHETIC_DEMO_MODE"] = "0"
    data_dir.mkdir(parents=True, exist_ok=True)
    pid_secret_path = data_dir / ".patient_pid_hmac_secret"
    if not pid_secret_path.exists():
        pid_secret_path.write_text(secrets.token_urlsafe(48), encoding="ascii")
    os.environ["APP_PATIENT_PID_HMAC_SECRET"] = pid_secret_path.read_text(encoding="ascii").strip()
    jwt_secret_path = data_dir / ".app_jwt_secret"
    if not jwt_secret_path.exists():
        jwt_secret_path.write_text(secrets.token_urlsafe(48), encoding="ascii")
    os.environ["APP_JWT_SECRET"] = jwt_secret_path.read_text(encoding="ascii").strip()

    from backend.app.security import hash_password
    from backend.db.database import (
        AuditLogModel,
        CorrectionRequestModel,
        FacilityModel,
        ImageModel,
        NotificationModel,
        SessionLocal,
        StudyModel,
        UserModel,
        VisitModel,
        generate_visit_code,
        init_db,
    )

    upload_dir = data_dir / "uploads" / "synthetic-demo"
    upload_dir.mkdir(parents=True, exist_ok=True)
    copied_fixtures = []
    for source, digest in fixtures:
        target = upload_dir / source.name
        shutil.copyfile(source, target)
        if _sha256(target) != digest:
            raise RuntimeError(f"Synthetic fixture copy failed integrity check: {source.name}")
        copied_fixtures.append((target, digest))

    init_db()
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
    facility_ids = [str(uuid.uuid4()) for _ in range(4)]
    doctors_by_facility: list[list[UserModel]] = [[] for _ in facility_ids]
    technicians_by_facility: list[UserModel] = []
    ids_by_username: dict[str, str] = {}

    with SessionLocal() as db:
        facilities = [
            FacilityModel(
                id=facility_ids[i],
                facility_code=f"DEMO-F{i + 1:02d}",
                name=f"Cơ sở minh họa {i + 1:02d} · dữ liệu tổng hợp",
                is_active=True,
                config={"data_origin": "synthetic_demo", "clinical_use": False},
                created_at=now,
            )
            for i in range(4)
        ]
        db.add_all(facilities)
        db.flush()

        global_admin = UserModel(
            id=str(uuid.uuid4()), username="demo.admin", full_name="DEMO · Quản trị toàn cục",
            role="ADMIN", department="Quản trị demo", facility_id=None,
            password_hash=hash_password(ADMIN_PASSWORD), is_active=True,
            must_change_password=False,
        )
        db.add(global_admin)
        ids_by_username[global_admin.username] = global_admin.id

        for facility_index, facility_id in enumerate(facility_ids):
            facility_admin = UserModel(
                id=str(uuid.uuid4()), username=f"demo.admin.f{facility_index + 1:02d}",
                full_name=f"DEMO · Quản trị cơ sở {facility_index + 1:02d}", role="ADMIN",
                department="Quản trị demo", facility_id=facility_id,
                password_hash=hash_password(ADMIN_PASSWORD), is_active=True,
                must_change_password=False,
            )
            db.add(facility_admin)
            ids_by_username[facility_admin.username] = facility_admin.id

            technician = UserModel(
                id=str(uuid.uuid4()), username=f"demo.tk{facility_index + 1:02d}",
                full_name=f"DEMO · Chuyên viên rà soát {facility_index + 1:02d}",
                role="SENIOR", department="Khoa Chẩn đoán Hình ảnh", facility_id=facility_id,
                password_hash=hash_password(DEMO_PASSWORD), is_active=True,
                must_change_password=False,
            )
            db.add(technician)
            technicians_by_facility.append(technician)
            ids_by_username[technician.username] = technician.id

        for index, (full_name, username) in enumerate(STAFF):
            facility_index = index % 4
            user = UserModel(
                id=str(uuid.uuid4()), username=username,
                full_name=f"DEMO · {full_name}", role="DOCTOR",
                department="Khoa Chẩn đoán Hình ảnh", facility_id=facility_ids[facility_index],
                password_hash=hash_password(DEMO_PASSWORD), is_active=True,
                must_change_password=False,
            )
            db.add(user)
            doctors_by_facility[facility_index].append(user)
            ids_by_username[username] = user.id
        db.flush()

        cases_created = 0
        correction_count = 0
        image_count = 0
        for index in range(case_count):
            facility_index = index % 4
            facility_id = facility_ids[facility_index]
            doctor = doctors_by_facility[facility_index][(index // 4) % len(doctors_by_facility[facility_index])]
            technician = technicians_by_facility[facility_index]
            visit_id = str(uuid.uuid4())
            visit = VisitModel(
                id=visit_id,
                visit_code=generate_visit_code(),
                facility_id=facility_id,
                patient_id=None,
                status="ACTIVE",
                is_locked=False,
                created_at=now - timedelta(days=index % 45, hours=index % 9),
                updated_at=now - timedelta(days=index % 45, hours=index % 9),
            )
            study_id = str(uuid.uuid4())
            case_date = (date.today() - timedelta(days=index % 45)).isoformat()
            case_created = now - timedelta(days=index % 45, hours=index % 9)
            study = StudyModel(
                id=study_id,
                study_code=f"DEMO-{facility_index + 1:02d}-{index + 1:04d}",
                study_date=case_date,
                status="PENDING",
                ovary_side="BOTH",
                contralateral_status="UNKNOWN",
                clinical_indication=(
                    "DỮ LIỆU TỔNG HỢP DEMO — minh họa quy trình, không phải hồ sơ bệnh nhân."
                ),
                visit_id=visit_id,
                facility_id=facility_id,
                assignee_id=doctor.id,
                review_revision=0,
                device_vendor="DEMO SYNTHETIC",
                probe_type="DEMO",
                created_at=case_created,
            )
            db.add_all([visit, study])
            db.flush()

            chosen = [copied_fixtures[index % len(copied_fixtures)], copied_fixtures[(index + 1) % len(copied_fixtures)]]
            for side, (fixture_path, digest) in zip(("L", "R"), chosen, strict=True):
                width, height = (640, 480) if "letterbox" in fixture_path.name else (512, 512)
                db.add(
                    ImageModel(
                        id=str(uuid.uuid4()),
                        study_id=study_id,
                        filename=fixture_path.name,
                        laterality=side,
                        raw_path=str(fixture_path),
                        file_hash=digest,
                        source_content_sha256=digest,
                        width=width,
                        height=height,
                    )
                )
                image_count += 1

            db.add(
                NotificationModel(
                    id=str(uuid.uuid4()), recipient_id=doctor.id, facility_id=facility_id,
                    study_id=study_id, event_type="CASE_ASSIGNED",
                    title="Phân công ca demo mới",
                    message=f"Bạn được giao ca tổng hợp {study.study_code}.",
                    is_read=False, created_at=case_created,
                    dedup_key=f"DEMO:ASSIGN:{study_id}",
                )
            )
            db.add(
                AuditLogModel(
                    entity_name="study", entity_id=study_id, action_type="DEMO_CASE_SEEDED",
                    actor_id="demo-seed", details={"data_origin": "synthetic_demo"},
                    timestamp=case_created,
                )
            )

            if index % 5 == 0:
                correction = CorrectionRequestModel(
                    id=str(uuid.uuid4()), study_id=study_id, review_revision=0,
                    reason="DEMO · rà soát mask trên ảnh tổng hợp trước khi chuyển bác sĩ.",
                    doctor_id=doctor.id, technician_id=technician.id,
                    status="PENDING", created_at=case_created, updated_at=case_created,
                )
                db.add(correction)
                db.add(
                    NotificationModel(
                        id=str(uuid.uuid4()), recipient_id=technician.id,
                        facility_id=facility_id, study_id=study_id,
                        event_type="CORRECTION_REQUESTED",
                        title="Yêu cầu rà soát demo",
                        message=f"Ca tổng hợp {study.study_code} được gửi để minh họa luồng correction.",
                        is_read=False, created_at=case_created,
                        dedup_key=f"DEMO:CORRECTION:{correction.id}",
                    )
                )
                correction_count += 1
            cases_created += 1

        db.commit()

    counts = {
        "facilities": 4,
        "users": len(ids_by_username),
        "doctors": len(STAFF),
        "technicians": len(technicians_by_facility),
        "cases": cases_created,
        "visits": cases_created,
        "images": image_count,
        "pending_corrections": correction_count,
        "patient_records": 0,
        "prediction_records": 0,
        "review_records": 0,
    }
    manifest = {
        "dataset": "synthetic_demo_only",
        "database": str(db_path),
        "created_at": now.replace(tzinfo=UTC).isoformat(),
        "counts": counts,
        "fixture_sha256": {path.name: digest for path, digest in copied_fixtures},
        "credentials": {
            "demo_admin_usernames": ["demo.admin", "demo.admin.f01", "demo.admin.f02", "demo.admin.f03", "demo.admin.f04"],
            "admin_password": ADMIN_PASSWORD,
            "staff_password": DEMO_PASSWORD,
        },
        "safety": "Synthetic images only; no patient IDs, predictions, or clinician reviews were generated.",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "seeded", **counts, "database": str(db_path), "manifest": str(manifest_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "demo_workspace")
    parser.add_argument("--case-count", type=int, default=80)
    args = parser.parse_args()
    print(json.dumps(seed(args.data_dir, args.case_count), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
