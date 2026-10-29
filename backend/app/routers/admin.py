"""
Admin Governance, Model Registry Overview, Audit Logs, and Dataset Export endpoints.
"""

import json
import os
import secrets
import tempfile
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from backend.app.config import model_registry
from backend.app.security import hash_password, require_admin
from backend.db.database import (
    AuditLogModel,
    ImageModel,
    PredictionModel,
    ReviewModel,
    StudyModel,
    UserModel,
    get_db,
)
from backend.schemas.schemas import (
    AdminCreateUserRequest,
    AdminDepartmentCreateRequest,
    AdminDepartmentUpdateRequest,
    AdminModelRegistrationRequest,
    AdminResetPasswordRequest,
    AdminSettingsRequest,
    AdminUpdateUserRequest,
    AuditLogItem,
    DoctorProductivityItem,
)
from backend.services.model_service import CandidateModelAdapter

router = APIRouter(tags=["Admin Governance"], dependencies=[Depends(require_admin)])


@router.get("/api/admin/models")
def get_admin_model_info(db: Session = Depends(get_db)):
    """
    Returns Admin-only model configurations and telemetry.
    """
    overview = model_registry.get_admin_overview()
    latency, count = db.query(
        func.avg(PredictionModel.inference_time_ms), func.count(PredictionModel.id)
    ).filter(PredictionModel.inference_time_ms > 0).one()
    overview["mean_inference_latency_ms"] = float(latency) if count else None
    overview["latency_sample_count"] = count
    # Stored model_version is a shared engine version, not a checkpoint identity.
    # It cannot safely isolate predictions made with the currently loaded weights.
    overview["latency_scope"] = "all_recorded_predictions"
    overview["latency_filter"] = "inference_time_ms > 0"
    overview["latency_model_version"] = None
    return overview


@router.get("/api/admin/audit-logs", response_model=list[AuditLogItem])
def get_audit_logs(limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    """
    Returns detailed audit logs of doctor actions for quality assurance and compliance.
    """
    logs = db.query(AuditLogModel).order_by(desc(AuditLogModel.timestamp)).limit(limit).all()

    result = []
    for log_item in logs:
        result.append(
            {
                "id": log_item.id,
                "entity_name": log_item.entity_name,
                "entity_id": log_item.entity_id,
                "action_type": log_item.action_type,
                "actor_id": log_item.actor_id,
                "details": None,
                "timestamp": log_item.timestamp.strftime("%d/%m/%Y %H:%M:%S"),
            }
        )

    return result


@router.get("/api/admin/doctor-stats", response_model=list[DoctorProductivityItem])
def get_doctor_productivity_stats(db: Session = Depends(get_db)):
    """No verified clinician identity or clinical sign-off workflow is available."""
    return []


@router.get("/api/admin/export-dataset")
def export_ground_truth_dataset(db: Session = Depends(get_db)):
    """Export observed review counts without inferring historical clinical approval."""
    data_export = {
        "export_date": datetime.now(UTC).isoformat(),
        "dataset_name": "observed_reviews",
        "total_cases_cataloged": db.query(StudyModel).count(),
        "total_verified_ground_truth": db.query(ReviewModel).filter(
            ReviewModel.is_official_ground_truth.is_(True)
        ).count(),
        "historical_m1_claims_status": "unverified_source_patient_ids_and_clinical_mask_approval",
    }
    return JSONResponse(
        content=data_export,
        headers={"Content-Disposition": "attachment; filename=review_summary.json"},
    )


@router.get("/api/admin/export-ground-truth")
def export_ground_truth_masks():
    """Disable research export until approval, consent, and split identity can be verified."""
    raise HTTPException(
        status_code=501,
        detail=(
            "Ground-truth export is disabled until the system can verify research approval, "
            "participant consent, de-identification, and patient-level split provenance."
        ),
    )


@router.post("/api/admin/backups/create")
def trigger_backup(db: Session = Depends(get_db)):
    """
    Creates a database-only backup; admin routes do not package patient images.
    """
    from backend.services.backup_service import BackupService

    backup_service = BackupService()
    result = backup_service.create_backup(include_images=False)
    return {
        key: result[key]
        for key in ("status", "backup_filename", "size_mb", "timestamp", "included_images", "encryption")
        if key in result
    }


@router.get("/api/admin/backups/list")
def list_backups():
    """
    Returns list of all available system backups.
    """
    from backend.services.backup_service import BackupService

    backup_service = BackupService()
    backups = backup_service.list_backups()
    return [
        {key: backup[key] for key in ("filename", "size_mb", "created_at") if key in backup}
        for backup in backups
    ]


_DEFAULT_ADMIN_SETTINGS = {
    "hospital_name": "Chưa cấu hình",
    "report_header": "BẢN NGHIÊN CỨU RUO · CHƯA CẤU HÌNH CƠ SỞ",
    "unit": "auto",
}


def _get_admin_settings_file() -> str:
    env_dir = os.environ.get("APP_DATA_DIR")
    if env_dir:
        from backend.app.config import PROJECT_ROOT

        data_dir = os.path.abspath(env_dir) if os.path.isabs(env_dir) else os.path.abspath(os.path.join(PROJECT_ROOT, env_dir))
    else:
        from backend.app.config import DATA_DIR

        data_dir = DATA_DIR
    return os.path.join(data_dir, "admin_settings.json")


def _load_admin_settings() -> dict:
    settings = dict(_DEFAULT_ADMIN_SETTINGS)
    filepath = _get_admin_settings_file()
    if os.path.isfile(filepath):
        try:
            with open(filepath, encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    settings.update(
                        {
                            key: value
                            for key, value in saved.items()
                            if key in _DEFAULT_ADMIN_SETTINGS
                            and isinstance(value, type(_DEFAULT_ADMIN_SETTINGS[key]))
                            and (not isinstance(value, str) or value.strip())
                        }
                    )
        except Exception:
            pass
    return settings


def _save_admin_settings(settings: dict) -> None:
    filepath = _get_admin_settings_file()
    _save_json_atomically(filepath, settings)


_ADMIN_SETTINGS = _load_admin_settings()

_DEFAULT_DEPARTMENTS = [
    {"id": "dep-cdha", "name": "Trung tâm Chẩn đoán hình ảnh", "code": "CDHA", "members": 0},
    {"id": "dep-ps", "name": "Khoa Phụ sản", "code": "PS", "members": 0},
]


def _get_admin_departments_file() -> str:
    env_dir = os.environ.get("APP_DATA_DIR")
    if env_dir:
        from backend.app.config import PROJECT_ROOT

        data_dir = os.path.abspath(env_dir) if os.path.isabs(env_dir) else os.path.abspath(os.path.join(PROJECT_ROOT, env_dir))
    else:
        from backend.app.config import DATA_DIR

        data_dir = DATA_DIR
    return os.path.join(data_dir, "admin_departments.json")


def _load_admin_departments() -> list[dict]:
    filepath = _get_admin_departments_file()
    if os.path.isfile(filepath):
        try:
            with open(filepath, encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, list):
                    return saved
        except Exception:
            pass
    return [dict(d) for d in _DEFAULT_DEPARTMENTS]


def _save_admin_departments(departments: list[dict]) -> None:
    filepath = _get_admin_departments_file()
    _save_json_atomically(filepath, departments)


def _save_json_atomically(filepath: str, value) -> None:
    directory = os.path.dirname(filepath) or "."
    os.makedirs(directory, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=directory, prefix=".admin-config-", suffix=".tmp", delete=False
        ) as stream:
            temporary_path = stream.name
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, filepath)
    except Exception:
        if temporary_path:
            try:
                os.remove(temporary_path)
            except OSError:
                pass
        raise


_DEPARTMENTS = _load_admin_departments()


def parse_date_boundary(date_str: str | None, is_end_of_day: bool = False) -> datetime | None:
    if not date_str:
        return None
    raw = date_str.strip()
    if not raw:
        return None
    try:
        if len(raw) == 10:  # YYYY-MM-DD
            dt = datetime.strptime(raw, "%Y-%m-%d")
            if is_end_of_day:
                return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


@router.get("/api/admin/audit-events")
def get_audit_events(
    page: int = Query(1, ge=1, le=1_000_000),
    page_size: int = Query(15, ge=1, le=100),
    q: str | None = None,
    actor: str | None = None,
    action: str | None = None,
    from_date: str | None = Query(None, alias="from"),
    from_param: str | None = Query(None, alias="from_date"),
    start_date: str | None = Query(None, alias="start_date"),
    to_date: str | None = Query(None, alias="to"),
    to_param: str | None = Query(None, alias="to_date"),
    end_date: str | None = Query(None, alias="end_date"),
    limit: int | None = Query(None, ge=1, le=10_000),
    offset: int | None = Query(None, ge=0, le=10_000_000),
    db: Session = Depends(get_db),
):
    """Return paginated audit logs conforming to frontend contract."""
    query = db.query(AuditLogModel)
    if actor:
        query = query.filter(AuditLogModel.actor_id.ilike(f"%{actor}%"))
    if action:
        query = query.filter(AuditLogModel.action_type == action)
    if q:
        search_fmt = f"%{q.strip()}%"
        query = query.filter(
            (AuditLogModel.actor_id.ilike(search_fmt))
            | (AuditLogModel.action_type.ilike(search_fmt))
            | (AuditLogModel.entity_id.ilike(search_fmt))
        )

    # Date range filters (BE-10)
    effective_from = from_date or from_param or start_date
    effective_to = to_date or to_param or end_date
    from_dt = parse_date_boundary(effective_from, is_end_of_day=False)
    to_dt = parse_date_boundary(effective_to, is_end_of_day=True)
    if from_dt:
        query = query.filter(AuditLogModel.timestamp >= from_dt)
    if to_dt:
        query = query.filter(AuditLogModel.timestamp <= to_dt)

    total = query.count()
    if limit is not None:
        effective_limit = limit
        effective_offset = offset or 0
    else:
        effective_limit = page_size
        effective_offset = (page - 1) * page_size

    logs = (
        query.order_by(desc(AuditLogModel.timestamp))
        .offset(effective_offset)
        .limit(effective_limit)
        .all()
    )
    items = [
        {
            "id": log_item.id,
            "entity_name": log_item.entity_name,
            "entity_id": log_item.entity_id,
            "action_type": log_item.action_type,
            "actor_id": log_item.actor_id,
            "details": None,
            "timestamp": log_item.timestamp.strftime("%d/%m/%Y %H:%M:%S")
            if hasattr(log_item.timestamp, "strftime")
            else str(log_item.timestamp),
        }
        for log_item in logs
    ]
    return {"items": items, "total": total}


@router.get("/api/admin/audit-events/export")
def export_audit_events(
    q: str | None = None,
    actor: str | None = None,
    action: str | None = None,
    from_date: str | None = Query(None, alias="from"),
    from_param: str | None = Query(None, alias="from_date"),
    start_date: str | None = Query(None, alias="start_date"),
    to_date: str | None = Query(None, alias="to"),
    to_param: str | None = Query(None, alias="to_date"),
    end_date: str | None = Query(None, alias="end_date"),
    limit: int = Query(5000, ge=1, le=10_000),
    db: Session = Depends(get_db),
):
    """Export audit events filtered by query criteria for admin compliance review (BE-11)."""
    query = db.query(AuditLogModel)
    if actor:
        query = query.filter(AuditLogModel.actor_id.ilike(f"%{actor}%"))
    if action:
        query = query.filter(AuditLogModel.action_type == action)
    if q:
        search_fmt = f"%{q.strip()}%"
        query = query.filter(
            (AuditLogModel.actor_id.ilike(search_fmt))
            | (AuditLogModel.action_type.ilike(search_fmt))
            | (AuditLogModel.entity_id.ilike(search_fmt))
        )

    effective_from = from_date or from_param or start_date
    effective_to = to_date or to_param or end_date
    from_dt = parse_date_boundary(effective_from, is_end_of_day=False)
    to_dt = parse_date_boundary(effective_to, is_end_of_day=True)
    if from_dt:
        query = query.filter(AuditLogModel.timestamp >= from_dt)
    if to_dt:
        query = query.filter(AuditLogModel.timestamp <= to_dt)

    logs = query.order_by(desc(AuditLogModel.timestamp)).limit(min(limit, 10000)).all()
    items = [
        {
            "id": log_item.id,
            "entity_name": log_item.entity_name,
            "entity_id": log_item.entity_id,
            "action_type": log_item.action_type,
            "actor_id": log_item.actor_id,
            "details": None,
            "timestamp": log_item.timestamp.strftime("%d/%m/%Y %H:%M:%S")
            if hasattr(log_item.timestamp, "strftime")
            else str(log_item.timestamp),
        }
        for log_item in logs
    ]
    return {"items": items, "total": len(items)}


@router.get("/api/admin/departments")
def get_admin_departments(db: Session = Depends(get_db)):
    """Return clinical ultrasound and ob/gyn departments with real membership count."""
    global _DEPARTMENTS
    _DEPARTMENTS = _load_admin_departments()
    res = []
    for d in _DEPARTMENTS:
        item = dict(d)
        d_name = item.get("name", "")
        d_code = item.get("code", "")
        try:
            count = db.query(UserModel).filter(
                (UserModel.department == d_name) | (UserModel.department == d_code)
            ).count()
            item["members"] = count
        except Exception:
            item["members"] = item.get("members", 0)
        res.append(item)
    return res


@router.post("/api/admin/departments")
def create_admin_department(dept: AdminDepartmentCreateRequest):
    """Create a new clinical department."""
    global _DEPARTMENTS
    dept_id = dept.id
    name = dept.name
    new_dept = {"id": dept_id, "name": name, "code": dept.code or dept_id.upper(), "members": 0}
    if any(
        d.get("id", "").casefold() == dept_id.casefold()
        or d.get("code", "").casefold() == new_dept["code"].casefold()
        for d in _DEPARTMENTS
    ):
        raise HTTPException(status_code=409, detail="Mã hoặc code khoa đã tồn tại.")
    updated_departments = [dict(d) for d in _DEPARTMENTS] + [new_dept]
    try:
        _save_admin_departments(updated_departments)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Không thể lưu danh mục khoa.") from exc
    _DEPARTMENTS = updated_departments
    return {"status": "SUCCESS", "department": new_dept}


@router.patch("/api/admin/departments/{dept_id}")
def update_admin_department(dept_id: str, dept: AdminDepartmentUpdateRequest):
    """Update a department name or code."""
    global _DEPARTMENTS
    if dept.id and dept.id != dept_id:
        raise HTTPException(status_code=422, detail="Mã khoa trong nội dung không khớp đường dẫn.")
    updated_departments = [dict(d) for d in _DEPARTMENTS]
    for d in updated_departments:
        if d["id"] == dept_id:
            if "code" in dept.model_fields_set:
                if any(
                    other["id"] != dept_id and other.get("code", "").casefold() == dept.code.casefold()
                    for other in updated_departments
                ):
                    raise HTTPException(status_code=409, detail="Code khoa đã tồn tại.")
                d["code"] = dept.code
            if "name" in dept.model_fields_set:
                d["name"] = dept.name
            try:
                _save_admin_departments(updated_departments)
            except OSError as exc:
                raise HTTPException(status_code=500, detail="Không thể lưu danh mục khoa.") from exc
            _DEPARTMENTS = updated_departments
            return {"status": "SUCCESS", "department": d}
    raise HTTPException(status_code=404, detail="Không tìm thấy khoa.")


@router.delete("/api/admin/departments/{dept_id}")
def delete_admin_department(dept_id: str):
    """Delete a clinical department."""
    global _DEPARTMENTS
    updated_departments = [d for d in _DEPARTMENTS if d["id"] != dept_id]
    if len(updated_departments) == len(_DEPARTMENTS):
        raise HTTPException(status_code=404, detail="Không tìm thấy khoa.")
    try:
        _save_admin_departments(updated_departments)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Không thể lưu danh mục khoa.") from exc
    _DEPARTMENTS = updated_departments
    return {"status": "SUCCESS"}


@router.get("/api/admin/cases")
def get_admin_cases(
    q: str | None = None,
    search: str | None = None,
    status: str | None = None,
    date: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    limit: int | None = Query(None, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Return a minimal operational summary without patient or image metadata."""
    search_query = q or search
    query = db.query(StudyModel)
    if search_query:
        query = query.filter(StudyModel.study_code.ilike(f"%{search_query.strip()}%"))
    if status and status.upper() != "ALL":
        query = query.filter(StudyModel.status == status.upper())
    if date:
        query = query.filter(StudyModel.study_date.startswith(date))

    total = query.count()
    effective_limit = limit or page_size
    effective_offset = offset if limit is not None else (page - 1) * page_size
    studies = (
        query.order_by(desc(StudyModel.created_at))
        .offset(effective_offset)
        .limit(effective_limit)
        .all()
    )
    return {
        "items": [
            {
                "study_code": study.study_code or study.id[:8],
                "visit_no": study.visit_no,
                "status": study.status,
                "department": None,
                "created_at": study.created_at.isoformat() if study.created_at else None,
                "version": study.review_revision,
            }
            for study in studies
        ],
        "total": total,
    }


ROLE_ALIAS_MAP = {
    "BS": "DOCTOR",
    "DOCTOR": "DOCTOR",
    "QT": "ADMIN",
    "ADMIN": "ADMIN",
    "TK": "SECRETARY",
    "SECRETARY": "SECRETARY",
}


def canonicalize_user_role(role_val: str | None) -> str:
    if not role_val:
        return "DOCTOR"
    raw_str = str(role_val).strip().upper()
    return ROLE_ALIAS_MAP.get(raw_str, raw_str)


@router.post("/api/admin/users")
def create_admin_user(user_data: AdminCreateUserRequest, db: Session = Depends(get_db)):
    """Create a new user account administratively."""
    raw_username = (user_data.username or "").strip()
    if not raw_username:
        raise HTTPException(status_code=422, detail="Tên đăng nhập không được để trống")
    username = raw_username.lower()
    existing = db.query(UserModel).filter(UserModel.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Tài khoản đã tồn tại")
    password = user_data.password
    must_change = False
    temp_password = None
    if not password:
        temp_password = secrets.token_urlsafe(12)
        password = temp_password
        must_change = True

    role = canonicalize_user_role(user_data.role)

    user = UserModel(
        id=str(uuid.uuid4()),
        username=username,
        full_name=user_data.full_name or raw_username,
        role=role,
        department=user_data.department or "Khoa Chẩn đoán Hình ảnh",
        password_hash=hash_password(password),
        must_change_password=must_change,
    )
    db.add(user)
    db.commit()
    res = {
        "status": "SUCCESS",
        "user_id": user.id,
        "username": user.username,
        "must_change_password": must_change,
    }
    if temp_password:
        res["temp_password"] = temp_password
    return res


@router.patch("/api/admin/users/{user_id}")
def update_admin_user(
    user_id: str,
    payload: AdminUpdateUserRequest,
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update user account attributes."""
    user = db.query(UserModel).filter((UserModel.id == user_id) | (UserModel.username == user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    payload_data = payload.model_dump(exclude_unset=True)
    if "username" in payload_data and payload_data["username"].lower() != user.username:
        raise HTTPException(status_code=422, detail="Tên đăng nhập không thể thay đổi.")
    updated_fields = {}
    if "full_name" in payload_data:
        user.full_name = payload_data["full_name"]
        updated_fields["full_name"] = payload_data["full_name"]
    if "role" in payload_data:
        user.role = canonicalize_user_role(payload_data["role"])
        updated_fields["role"] = user.role
    if "department" in payload_data:
        user.department = payload_data["department"]
        updated_fields["department"] = payload_data["department"]
    if "is_active" in payload_data:
        val = payload_data["is_active"]
        new_active: bool
        if isinstance(val, bool):
            new_active = val
        elif isinstance(val, (int, float)):
            new_active = bool(val)
        elif isinstance(val, str):
            norm = val.strip().lower()
            if norm in ("true", "1", "yes", "on", "active"):
                new_active = True
            elif norm in ("false", "0", "no", "off", "inactive"):
                new_active = False
            else:
                raise HTTPException(
                    status_code=422,
                    detail="Giá trị is_active không hợp lệ. Phải là kiểu boolean (true/false).",
                )
        else:
            raise HTTPException(
                status_code=422,
                detail="Giá trị is_active không hợp lệ. Phải là kiểu boolean (true/false).",
            )

        if user.is_active and not new_active:
            user.tokens_revoked_at = datetime.now(UTC)
            user.token_version = (user.token_version or 1) + 1
        user.is_active = new_active
        updated_fields["is_active"] = user.is_active

    db.add(
        AuditLogModel(
            entity_name="user",
            entity_id=user.id,
            action_type="ADMIN_USER_UPDATE",
            actor_id=current_user.username,
            details=updated_fields,
            timestamp=datetime.now(UTC),
        )
    )
    db.commit()
    return {"status": "SUCCESS", "user_id": user.id, "username": user.username}


@router.post("/api/admin/users/{user_id}/reset-password")
def admin_reset_user_password(
    user_id: str,
    payload: AdminResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Admin resets user password."""
    user = db.query(UserModel).filter((UserModel.id == user_id) | (UserModel.username == user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    raw_password = payload.new_password
    must_change = False
    temp_password = None
    if not raw_password:
        temp_password = secrets.token_urlsafe(12)
        raw_password = temp_password
        must_change = True

    user.password_hash = hash_password(raw_password)
    user.must_change_password = must_change
    user.tokens_revoked_at = datetime.now(UTC)
    user.token_version = (user.token_version or 1) + 1
    db.commit()
    res = {
        "status": "SUCCESS",
        "message": "Đã đặt lại mật khẩu người dùng.",
        "must_change_password": must_change,
    }
    if temp_password:
        res["temp_password"] = temp_password
    return res


@router.delete("/api/admin/users/{user_id}")
def delete_admin_user(user_id: str, db: Session = Depends(get_db)):
    """Delete a user account administratively."""
    user = db.query(UserModel).filter((UserModel.id == user_id) | (UserModel.username == user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    db.delete(user)
    db.commit()
    return {"status": "SUCCESS", "message": "Đã xóa tài khoản."}


@router.post("/api/admin/models/register")
def register_admin_model(
    model_data: AdminModelRegistrationRequest,
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Register candidate checkpoint metadata for RUO review; this does not load or serve it."""
    name = model_data.name or model_data.model_id or "candidate_model"
    version = model_data.version or "1.0.0"
    arch = model_data.architecture or "Candidate Checkpoint"
    ckpt = model_data.checkpoint or model_data.artifact_id
    key = model_data.model_id or f"candidate_{len(model_registry.adapters)}_{uuid.uuid4().hex[:6]}"
    if key in model_registry.adapters or key in {"attention_unet", "s4m", "ultrasam", "ds2net", "sovaseg"}:
        raise HTTPException(
            status_code=409,
            detail=f"Mã mô hình '{key}' đã tồn tại hoặc thuộc danh mục phục vụ được bảo vệ.",
        )

    adapter = CandidateModelAdapter(name=name, version=version, architecture=arch, checkpoint=ckpt)
    try:
        model_registry.register_adapter(key, adapter)
        model_registry.save_persisted_candidates()
    except Exception as exc:
        model_registry.adapters.pop(key, None)
        raise HTTPException(status_code=500, detail="Không thể lưu metadata mô hình.") from exc

    try:
        db.add(
            AuditLogModel(
                entity_name="model_candidate",
                entity_id=key,
                action_type="REGISTER_CANDIDATE_MODEL",
                actor_id=current_user.username,
                details={"name": name, "version": version, "architecture": arch, "checkpoint": ckpt},
                timestamp=datetime.now(UTC),
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        model_registry.adapters.pop(key, None)
        try:
            model_registry.save_persisted_candidates()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Không thể ghi nhật ký đăng ký mô hình.") from exc

    return {"status": "SUCCESS", "message": "Đăng ký mô hình thành công.", "model_id": key}


@router.delete("/api/admin/models/{model_id}")
def remove_admin_candidate_model(
    model_id: str,
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Remove a metadata-only candidate; built-in serving adapters are protected."""
    adapter = model_registry.adapters.get(model_id)
    if adapter is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy mô hình.")
    if not isinstance(adapter, CandidateModelAdapter):
        raise HTTPException(status_code=409, detail="Không thể gỡ mô hình phục vụ được bảo vệ.")

    model_registry.adapters.pop(model_id)
    try:
        model_registry.save_persisted_candidates()
        db.add(
            AuditLogModel(
                entity_name="model_candidate",
                entity_id=model_id,
                action_type="REMOVE_CANDIDATE_MODEL",
                actor_id=current_user.username,
                details={"name": adapter.name},
                timestamp=datetime.now(UTC),
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        model_registry.adapters[model_id] = adapter
        try:
            model_registry.save_persisted_candidates()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Không thể lưu thay đổi danh mục mô hình.") from exc

    return {"status": "SUCCESS", "model_id": model_id}


@router.get("/api/admin/settings")
def get_admin_settings():
    """Return admin workspace settings."""
    _ADMIN_SETTINGS.update(_load_admin_settings())
    return _ADMIN_SETTINGS


@router.put("/api/admin/settings")
def update_admin_settings(settings: AdminSettingsRequest):
    """Update admin workspace settings."""
    updated_settings = {**_ADMIN_SETTINGS, **settings.model_dump(exclude_unset=True)}
    try:
        _save_admin_settings(updated_settings)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Không thể lưu cấu hình quản trị.") from exc
    _ADMIN_SETTINGS.clear()
    _ADMIN_SETTINGS.update(updated_settings)
    return {"status": "SUCCESS", "message": "Đã lưu cấu hình.", "settings": _ADMIN_SETTINGS}


@router.get("/api/admin/metadata")
def get_admin_metadata(db: Session = Depends(get_db)):
    """Return administrative system metadata and summary statistics."""
    return {
        "hospital_name": _ADMIN_SETTINGS.get("hospital_name", "Chưa cấu hình"),
        "system_version": "2.0.0",
        "total_cases": db.query(StudyModel).count(),
        "total_images": db.query(ImageModel).count(),
        "total_reviews": db.query(ReviewModel).count(),
        "total_users": db.query(UserModel).count(),
    }

