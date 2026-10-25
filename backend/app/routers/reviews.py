"""
Doctor Review, Ground Truth Sign-Off, and Medical PDF Report Generation endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.config import model_registry, preprocessor
from backend.app.security import get_current_user, require_clinical
from backend.db.database import UserModel, get_db
from backend.schemas.schemas import (
    BatchReviewRequest,
    BatchReviewResponse,
    DoctorReviewRequest,
    DoctorReviewResponse,
    ResearchExportRequest,
)
from backend.services.research_export import build_research_bundle
from backend.services.review_service import persist_review_batch, persist_single_review

router = APIRouter(
    tags=["Doctor Review & Reports"],
    dependencies=[Depends(require_clinical)],
)


@router.post("/api/reviews/batch", response_model=BatchReviewResponse)
def submit_batch_reviews(
    request: BatchReviewRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Persist atomic, version-guarded, idempotent research reviews for a study.
    """
    return persist_review_batch(
        db,
        request,
        current_user,
        allow_partial=False,
        inference_engine=model_registry.get_primary_adapter().engine,
        image_preprocessor=preprocessor,
    )


@router.post("/api/review", response_model=DoctorReviewResponse)
def submit_doctor_review(
    review_req: DoctorReviewRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Persist one review through the shared atomic review service."""
    return persist_single_review(
        db,
        review_req,
        current_user,
        inference_engine=model_registry.get_primary_adapter().engine,
        image_preprocessor=preprocessor,
    )


@router.post("/api/cases/{study_id}/research-export")
def export_case_research_bundle(
    study_id: str,
    export_req: ResearchExportRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_clinical),
):
    """
    Research export is unavailable until authorization and de-identification can be verified.
    """
    bundle_bytes = build_research_bundle(
        db=db,
        study_id=study_id,
        review_ids=export_req.review_ids,
        expected_revision=export_req.expected_revision,
        actor=current_user,
        ethics_approval_code=export_req.ethics_approval_code,
        patient_consent_confirmed=export_req.patient_consent_confirmed,
    )
    return Response(
        content=bundle_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=study_{study_id}_research_export.zip",
        },
    )


@router.post("/api/generate-report")
def generate_report_pdf():
    """Clinical PDF requires a verified reviewer workflow."""
    raise HTTPException(status_code=501, detail="Chưa hỗ trợ xuất báo cáo lâm sàng khi chưa có xác thực chuyên môn.")

