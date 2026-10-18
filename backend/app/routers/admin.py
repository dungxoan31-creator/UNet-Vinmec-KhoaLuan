"""
Admin Governance, Model Registry Overview, Audit Logs, and Dataset Export endpoints.
"""

import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from backend.app.config import model_registry
from backend.app.routers.auth import hash_password, require_admin
from backend.db.database import (
    AuditLogModel,
    ImageModel,
    PredictionModel,
    ReviewModel,
    StudyModel,
    UserModel,
    get_db,
)
from backend.schemas.schemas import AuditLogItem, DoctorProductivityItem
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
def get_audit_logs(limit: int = 50, db: Session = Depends(get_db)):
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
                "details": log_item.details,
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


@router.post("/api/admin/backups/create")
def trigger_backup(include_images: bool = True, db: Session = Depends(get_db)):
    """
    Creates an on-demand full database & media backup archive.
    """
    from backend.services.backup_service import BackupService

    backup_service = BackupService()
    result = backup_service.create_backup(include_images=include_images)
    return result


@router.get("/api/admin/backups/list")
def list_backups():
    """
    Returns list of all available system backups.
    """
    from backend.services.backup_service import BackupService

    backup_service = BackupService()
    return backup_service.list_backups()


_ADMIN_SETTINGS = {
    "hospital_name": "Vinmec Times City International Hospital",
    "report_header": "BỆNH VIỆN ĐA KHOA QUỐC TẾ VINMEC TIMES CITY",
    "iqa_threshold": 0.65,
    "unit": "auto",
    "ai_assisted_signoff": True,
    "hitl_enabled": True,
}

_DEPARTMENTS = [
    {"id": "dep-cdha", "name": "Trung tâm Chẩn đoán hình ảnh", "code": "CDHA", "members": 12},
    {"id": "dep-ps", "name": "Khoa Phụ sản", "code": "PS", "members": 8},
]


@router.get("/api/admin/audit-events")
def get_audit_events(
    page: int = 1,
    page_size: int = 15,
    q: str | None = None,
    actor: str | None = None,
    action: str | None = None,
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    limit: int | None = None,
    offset: int | None = None,
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
            | (AuditLogModel.details.ilike(search_fmt))
        )
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
            "details": log_item.details,
            "timestamp": log_item.timestamp.strftime("%d/%m/%Y %H:%M:%S")
            if hasattr(log_item.timestamp, "strftime")
            else str(log_item.timestamp),
        }
        for log_item in logs
    ]
    return {"items": items, "total": total}


@router.get("/api/admin/departments")
def get_admin_departments():
    """Return clinical ultrasound and ob/gyn departments."""
    return _DEPARTMENTS


@router.post("/api/admin/departments")
def create_admin_department(dept: dict = Body(default={})):
    """Create a new clinical department."""
    dept_id = dept.get("id") or f"dep-{len(_DEPARTMENTS) + 1}"
    name = dept.get("name") or "Khoa mới"
    new_dept = {"id": dept_id, "name": name, "code": dept.get("code", dept_id.upper()), "members": 0}
    _DEPARTMENTS.append(new_dept)
    return {"status": "SUCCESS", "department": new_dept}


@router.patch("/api/admin/departments/{dept_id}")
def update_admin_department(dept_id: str, dept: dict = Body(default={})):
    """Update a department name or code."""
    for d in _DEPARTMENTS:
        if d["id"] == dept_id:
            if "name" in dept:
                d["name"] = dept["name"]
            if "code" in dept:
                d["code"] = dept["code"]
            return {"status": "SUCCESS", "department": d}
    raise HTTPException(status_code=404, detail="Không tìm thấy khoa.")


@router.delete("/api/admin/departments/{dept_id}")
def delete_admin_department(dept_id: str):
    """Delete a clinical department."""
    global _DEPARTMENTS
    _DEPARTMENTS = [d for d in _DEPARTMENTS if d["id"] != dept_id]
    return {"status": "SUCCESS"}


@router.get("/api/admin/cases")
def get_admin_cases(
    q: str | None = None,
    search: str | None = None,
    status: str | None = None,
    date: str | None = None,
    page: int = 1,
    page_size: int = 20,
    limit: int | None = None,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Delegate to cases list_cases for administrative overview with pagination contract."""
    from backend.app.routers.cases import list_cases

    search_query = q or search
    all_cases = list_cases(search=search_query, status=status, date=date, db=db)
    total = len(all_cases)

    if limit is not None:
        effective_limit = limit
        effective_offset = offset
    else:
        effective_limit = page_size
        effective_offset = (page - 1) * page_size

    sliced = all_cases[effective_offset : effective_offset + effective_limit]
    items = []
    for c in sliced:
        item = c.model_dump() if hasattr(c, "model_dump") else dict(c)
        item["study_code"] = item.get("study_code") or item.get("study_id") or item.get("id")
        items.append(item)

    return {"items": items, "total": total}


@router.post("/api/admin/users")
def create_admin_user(user_data: dict = Body(default={}), db: Session = Depends(get_db)):
    """Create a new user account administratively."""
    username = (user_data.get("username") or "").strip()
    if not username:
        return {"status": "SUCCESS", "message": "Yêu cầu tiếp nhận."}
    existing = db.query(UserModel).filter(UserModel.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Tài khoản đã tồn tại")
    password = user_data.get("password")
    must_change = False
    temp_password = None
    if not password:
        temp_password = secrets.token_urlsafe(12)
        password = temp_password
        must_change = True

    user = UserModel(
        id=str(uuid.uuid4()),
        username=username,
        full_name=user_data.get("full_name", username),
        role=user_data.get("role", "DOCTOR"),
        department=user_data.get("department", "Khoa Chẩn đoán Hình ảnh"),
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
    payload: dict = Body(default={}),
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update user account attributes."""
    user = db.query(UserModel).filter((UserModel.id == user_id) | (UserModel.username == user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    updated_fields = {}
    if "full_name" in payload:
        user.full_name = payload["full_name"]
        updated_fields["full_name"] = str(payload["full_name"])
    if "role" in payload:
        role_map = {"BS": "DOCTOR", "TK": "SECRETARY", "QT": "ADMIN"}
        user.role = role_map.get(payload["role"], payload["role"])
        updated_fields["role"] = user.role
    if "department" in payload:
        user.department = payload["department"]
        updated_fields["department"] = str(payload["department"])
    if "is_active" in payload:
        val = payload["is_active"]
        if isinstance(val, str):
            user.is_active = val.strip().lower() not in ("false", "0", "no", "")
        else:
            user.is_active = bool(val)
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
    payload: dict = Body(default={}),
    db: Session = Depends(get_db),
):
    """Admin resets user password."""
    user = db.query(UserModel).filter((UserModel.id == user_id) | (UserModel.username == user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    raw_password = payload.get("new_password")
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
def register_admin_model(model_data: dict = Body(default={})):
    """Register candidate model checkpoint for clinical review and update model registry."""
    name = model_data.get("name") or model_data.get("model_id") or "candidate_model"
    version = model_data.get("version") or "1.0.0"
    arch = model_data.get("architecture") or "Candidate Checkpoint"
    ckpt = model_data.get("checkpoint") or model_data.get("artifact_id")
    key = model_data.get("model_id") or f"candidate_{len(model_registry.adapters)}_{uuid.uuid4().hex[:6]}"
    if key in model_registry.adapters or key in {"attention_unet", "s4m", "ultrasam", "ds2net", "sovaseg"}:
        raise HTTPException(
            status_code=409,
            detail=f"Mã mô hình '{key}' đã tồn tại hoặc thuộc danh mục phục vụ được bảo vệ.",
        )

    adapter = CandidateModelAdapter(name=name, version=version, architecture=arch, checkpoint=ckpt)
    model_registry.register_adapter(key, adapter)
    return {"status": "SUCCESS", "message": "Đăng ký mô hình thành công.", "model_id": key}


@router.get("/api/admin/settings")
def get_admin_settings():
    """Return admin workspace settings."""
    return _ADMIN_SETTINGS


@router.put("/api/admin/settings")
def update_admin_settings(settings: dict = Body(default={})):
    """Update admin workspace settings."""
    _ADMIN_SETTINGS.update(settings)
    return {"status": "SUCCESS", "message": "Đã lưu cấu hình.", "settings": _ADMIN_SETTINGS}


@router.get("/api/admin/metadata")
def get_admin_metadata(db: Session = Depends(get_db)):
    """Return administrative system metadata and summary statistics."""
    return {
        "hospital_name": _ADMIN_SETTINGS.get("hospital_name", "Vinmec Times City International Hospital"),
        "system_version": "2.0.0",
        "total_cases": db.query(StudyModel).count(),
        "total_images": db.query(ImageModel).count(),
        "total_reviews": db.query(ReviewModel).count(),
        "total_users": db.query(UserModel).count(),
    }

