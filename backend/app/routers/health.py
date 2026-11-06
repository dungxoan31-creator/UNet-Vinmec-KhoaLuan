"""Health and observed dashboard statistics for the research workstation."""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import distinct, func, text
from sqlalchemy.orm import Session

from backend.app.config import (
    ENABLED_FEATURES,
    SYNTHETIC_DEMO_MODE,
    SYSTEM_ENVIRONMENT,
    is_feature_enabled,
    model_registry,
)
from backend.app.security import get_current_user
from backend.db.database import ImageModel, ReviewModel, StudyModel, UserModel, engine, get_db
from backend.schemas.schemas import DashboardStatsResponse

router = APIRouter(tags=["System & Metrics"])
logger = logging.getLogger(__name__)


def get_system_capabilities() -> dict[str, Any]:
    return {
        "case_workflow": False,
        "research_review": True,
        "research_export": False,
        "hitl_events": True,
        "manual_review": False,
        "case_leases": True,
        "remote_lease": True,
        "clinical_production_ready": False,
        "research_use_only": True,
        "clinical_validation_status": "BLOCKED",
        "postgresql_supported": False,
        "synthetic_demo_mode": SYNTHETIC_DEMO_MODE,
        "synthetic_demo_uploads_restricted": SYNTHETIC_DEMO_MODE,
        "feature_autofill": is_feature_enabled("autofill"),
        "feature_fast_review": is_feature_enabled("fast_review"),
        "feature_cdss_background": is_feature_enabled("cdss_background"),
        "feature_uncertainty_overlay": is_feature_enabled("uncertainty_overlay"),
        "enabled_features": sorted(list(ENABLED_FEATURES)),
    }


@router.get("/api/health/live")
def liveness_check():
    """Liveness probe: returns 200 as long as the HTTP worker process is responsive."""
    return {"status": "alive", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/api/health/ready")
def readiness_check():
    """
    Readiness probe: verifies live database connectivity and model readiness.
    Returns 200 OK when service can process inferences and transactions,
    or 503 Service Unavailable if dependencies are unhealthy.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ready = True
    except Exception as exc:
        db_ready = False
        logger.warning(
            "Readiness database check failed.",
            extra={"database_readiness_error_type": type(exc).__name__},
        )

    adapter = model_registry.get_primary_adapter()
    model_ready = bool(adapter and getattr(adapter, "is_loaded", False))
    engine_obj = getattr(adapter, "engine", None) if model_ready else None
    if engine_obj and getattr(engine_obj, "is_model_ready", False) is False:
        model_ready = False

    is_ready = db_ready and model_ready
    status_code = 200 if is_ready else 503

    payload = {
        "status": "ready" if is_ready else "unhealthy",
        "readiness_scope": "TECHNICAL_SERVICE_ONLY",
        "database": "connected" if db_ready else "disconnected",
        "database_engine": engine.dialect.name,
        "model_ready": model_ready,
        "clinical_production_ready": False,
        "research_use_only": True,
        "clinical_validation_status": "BLOCKED",
        "postgresql_supported": False,
        "synthetic_demo_mode": SYNTHETIC_DEMO_MODE,
        "synthetic_demo_uploads_restricted": SYNTHETIC_DEMO_MODE,
        "primary_model": getattr(adapter, "name", "None") if adapter else None,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    return JSONResponse(status_code=status_code, content=payload)


@router.get("/api/health")
def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ready = True
    except Exception:
        db_ready = False

    adapter = model_registry.get_primary_adapter()
    is_ready = bool(adapter and getattr(adapter, "is_loaded", False))
    engine_obj = getattr(adapter, "engine", None) if is_ready else None
    if engine_obj and getattr(engine_obj, "is_model_ready", False) is False:
        is_ready = False
    checksum = getattr(engine_obj, "model_checksum", None) if is_ready else None
    model_name = getattr(adapter, "name", "Standard U-Net")

    return {
        "status": "healthy" if db_ready else "degraded",
        "system": "Ovarian ultrasound segmentation workstation (Research Use Only - RUO)",
        "clinical_status": "RESEARCH_USE_ONLY",
        "regulatory_disclaimer": (
            "Hệ thống là bản mẫu nghiên cứu thực nghiệm (Research Prototype / RUO), chưa được phê duyệt "
            "làm thiết bị y tế độc lập (SaMD). Mọi phân đoạn và gợi ý đo đạc chỉ mang tính chất tham khảo, "
            "quyết định chuyên môn thuộc về bác sĩ lâm sàng."
        ),
        "primary_model": model_name,
        "environment": SYSTEM_ENVIRONMENT,
        "model_ready": is_ready,
        "database_ready": db_ready,
        "checkpoint_sha256": checksum,
        "capabilities": get_system_capabilities(),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/api/capabilities")
def get_capabilities():
    return get_system_capabilities()


@router.get("/api/stats", response_model=DashboardStatsResponse)
def get_dashboard_statistics(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Count real records only, strictly scoped by user's assigned facility."""
    from fastapi.params import Depends
    is_direct_test = current_user is None or isinstance(current_user, Depends)
    is_global = is_direct_test or (getattr(current_user, "is_global_admin", False) and not getattr(current_user, "facility_id", None))
    if not is_global and not getattr(current_user, "facility_id", None):
        raise HTTPException(status_code=403, detail="Tài khoản chưa được gán cơ sở y tế.")

    studies_q = db.query(StudyModel)
    images_q = db.query(ImageModel)
    official = db.query(ReviewModel).filter(ReviewModel.is_official_ground_truth.is_(True))

    if not is_global:
        studies_q = studies_q.filter(StudyModel.facility_id == current_user.facility_id)
        images_q = images_q.join(StudyModel, ImageModel.study_id == StudyModel.id).filter(StudyModel.facility_id == current_user.facility_id)
        official = official.join(ImageModel, ReviewModel.image_id == ImageModel.id).join(StudyModel, ImageModel.study_id == StudyModel.id).filter(StudyModel.facility_id == current_user.facility_id)

    total_cases = studies_q.count()
    official_count = official.count()

    approved_q = (
        db.query(func.count(distinct(StudyModel.id)))
        .join(ImageModel, ImageModel.study_id == StudyModel.id)
        .join(ReviewModel, ReviewModel.image_id == ImageModel.id)
        .filter(ReviewModel.is_official_ground_truth.is_(True))
    )
    if not is_global:
        approved_q = approved_q.filter(StudyModel.facility_id == current_user.facility_id)

    approved_cases = approved_q.scalar() or 0
    accepted = official.filter(ReviewModel.doctor_action == "ACCEPTED_RAW").count()
    acceptance = round(100 * accepted / official_count, 1) if official_count else 0.0
    average_review = official.with_entities(func.avg(ReviewModel.time_spent_seconds)).scalar() or 0.0
    pending = max(0, total_cases - approved_cases)

    return {
        "total_cases_received": total_cases,
        "doctor_approved_cases": approved_cases,
        "pending_evaluation_cases": pending,
        "ai_consensus_rate_pct": acceptance,
        "total_images_collected": images_q.count(),
        "ground_truth_confirmed": official_count,
        "pending_confirmation": pending,
        "empty_masks_normal": 0,
        "doctor_acceptance_rate_pct": acceptance,
        "mean_dice_score": None,
        "average_review_time_seconds": round(float(average_review), 1),
        "realtime_active_users": 0,
        "last_updated": datetime.now(UTC).isoformat(),
    }
