"""Health and observed dashboard statistics for the research workstation."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from backend.db.database import ImageModel, ReviewModel, StudyModel, get_db
from backend.schemas.schemas import DashboardStatsResponse

router = APIRouter(tags=["System & Metrics"])


@router.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "system": "Ovarian ultrasound segmentation workstation (research prototype)",
        "primary_model": "Standard U-Net",
        "environment": "EXPERIMENTAL_RESEARCH_PROTOTYPE",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/api/stats", response_model=DashboardStatsResponse)
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
