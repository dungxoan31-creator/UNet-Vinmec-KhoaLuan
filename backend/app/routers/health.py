"""Health and observed dashboard statistics for the research workstation."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import distinct, func, text
from sqlalchemy.orm import Session

from backend.app.config import SYSTEM_ENVIRONMENT, model_registry
from backend.app.routers.auth import get_current_user
from backend.db.database import ImageModel, ReviewModel, StudyModel, engine, get_db
from backend.schemas.schemas import DashboardStatsResponse

router = APIRouter(tags=["System & Metrics"])


def get_system_capabilities() -> dict[str, bool]:
    return {
        "case_workflow": False,
        "research_review": True,
        "research_export": True,
        "hitl_events": True,
        "manual_review": False,
        "remote_lease": False,
        "clinical_production_ready": False,
        "research_use_only": True,
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
        db_error = str(exc)

    adapter = model_registry.get_primary_adapter()
    model_ready = bool(adapter and getattr(adapter, "is_loaded", False))
    engine_obj = getattr(adapter, "engine", None) if model_ready else None
    if engine_obj and getattr(engine_obj, "is_model_ready", False) is False:
        model_ready = False

    is_ready = db_ready and model_ready
    status_code = 200 if is_ready else 503

    payload = {
        "status": "ready" if is_ready else "unhealthy",
        "database": "connected" if db_ready else "disconnected",
        "model_ready": model_ready,
        "primary_model": getattr(adapter, "name", "None") if adapter else None,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if not db_ready:
        payload["database_error"] = db_error

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


@router.get("/api/stats", response_model=DashboardStatsResponse, dependencies=[Depends(get_current_user)])
def get_dashboard_statistics(db: Session = Depends(get_db)):
    """Count real records only; no historical research totals in live counters."""
    total_cases = db.query(StudyModel).count()
    official = db.query(ReviewModel).filter(ReviewModel.is_official_ground_truth.is_(True))
    official_count = official.count()
    approved_cases = (
        db.query(func.count(distinct(StudyModel.id)))
        .join(ImageModel, ImageModel.study_id == StudyModel.id)
        .join(ReviewModel, ReviewModel.image_id == ImageModel.id)
        .filter(ReviewModel.is_official_ground_truth.is_(True))
        .scalar()
        or 0
    )
    accepted = official.filter(ReviewModel.doctor_action == "ACCEPTED_RAW").count()
    acceptance = round(100 * accepted / official_count, 1) if official_count else 0.0
    average_review = official.with_entities(func.avg(ReviewModel.time_spent_seconds)).scalar() or 0.0
    pending = max(0, total_cases - approved_cases)
    return {
        "total_cases_received": total_cases,
        "doctor_approved_cases": approved_cases,
        "pending_evaluation_cases": pending,
        "ai_consensus_rate_pct": acceptance,
        "total_images_collected": db.query(ImageModel).count(),
        "ground_truth_confirmed": official_count,
        "pending_confirmation": pending,
        "empty_masks_normal": 0,
        "doctor_acceptance_rate_pct": acceptance,
        "mean_dice_score": None,
        "average_review_time_seconds": round(float(average_review), 1),
        "realtime_active_users": 0,
        "last_updated": datetime.now(UTC).isoformat(),
    }
