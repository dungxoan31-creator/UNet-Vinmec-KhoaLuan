"""
Doctor Review, Ground Truth Sign-Off, and Medical PDF Report Generation endpoints.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.config import model_registry, preprocessor
from backend.app.security import get_current_user, require_clinical
from backend.db.database import ImageModel, RegionAssignmentBatchModel, ReviewModel, UserModel, get_db
from backend.schemas.schemas import (
    BatchReviewRequest,
    BatchReviewResponse,
    DoctorReviewRequest,
    DoctorReviewResponse,
    RegionCaliperWriteRequest,
    RegionCDSSAssessmentRequest,
    ResearchExportRequest,
)
from backend.services.inference_engine import InferenceEngine
from backend.services.lesion_reconciliation import review_component_candidates
from backend.services.region_assignment_service import (
    RegionAssignmentRequest,
    confirm_regions,
    region_proposals,
    verified_previous_regions,
)
from backend.services.region_clinical_service import (
    get_region_assessments,
    get_region_calipers,
    save_region_assessment,
    save_region_caliper,
)
from backend.services.research_export import build_research_bundle
from backend.services.review_service import persist_review_batch, persist_single_review

router = APIRouter(
    tags=["Doctor Review & Reports"],
    dependencies=[Depends(require_clinical)],
)


@router.post("/api/cases/{study_id}/images/{image_id}/reviews/{review_id}/region-assignments")
def confirm_review_regions(study_id: str, image_id: str, review_id: str, request: RegionAssignmentRequest,
                           db: Session = Depends(get_db), current_user: UserModel = Depends(get_current_user)):
    return confirm_regions(db, study_id, image_id, review_id, request, current_user)


@router.get("/api/cases/{study_id}/images/{image_id}/region-assignments")
def latest_review_regions(study_id: str, image_id: str, db: Session = Depends(get_db)):
    image = db.query(ImageModel).filter_by(id=image_id, study_id=study_id).first()
    if image is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh trong ca.")
    batch = (db.query(RegionAssignmentBatchModel).filter_by(study_id=study_id, image_id=image_id)
             .order_by(RegionAssignmentBatchModel.review_revision.desc()).first())
    if batch is None:
        return {"assignment": None, "stale": False}
    verified_previous_regions(db, batch, image_id)
    latest = (db.query(ReviewModel).filter_by(image_id=image_id)
              .order_by(ReviewModel.created_at.desc(), ReviewModel.id.desc()).first())
    return {
        "assignment": {**batch.response_json, "assignment_request_id": batch.request_id},
        "stale": latest is None or latest.id != batch.review_id,
    }


@router.get("/api/cases/{study_id}/images/{image_id}/regions/{region_id}/calipers")
def read_region_calipers(
    study_id: str,
    image_id: str,
    region_id: str,
    assignment_request_id: UUID,
    review_id: UUID,
    mask_sha256: str,
    limit: int = Query(default=100, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=512),
    db: Session = Depends(get_db),
):
    return get_region_calipers(
        db, study_id, image_id, str(assignment_request_id), str(review_id), region_id, mask_sha256,
        limit=limit, cursor=cursor,
    )


@router.post("/api/cases/{study_id}/images/{image_id}/regions/{region_id}/calipers")
def write_region_caliper(
    study_id: str,
    image_id: str,
    region_id: str,
    request: RegionCaliperWriteRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    if str(request.region_id) != region_id:
        raise HTTPException(status_code=404, detail="Region ID không khớp đường dẫn.")
    return save_region_caliper(db, study_id, image_id, request, current_user)


@router.get("/api/cases/{study_id}/images/{image_id}/regions/{region_id}/cdss-assessments")
def read_region_assessments(
    study_id: str,
    image_id: str,
    region_id: str,
    assignment_request_id: UUID,
    review_id: UUID,
    mask_sha256: str,
    limit: int = Query(default=100, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=512),
    db: Session = Depends(get_db),
):
    return get_region_assessments(
        db, study_id, image_id, str(assignment_request_id), str(review_id), region_id, mask_sha256,
        limit=limit, cursor=cursor,
    )


@router.post("/api/cases/{study_id}/images/{image_id}/regions/{region_id}/cdss-assessments")
def write_region_assessment(
    study_id: str,
    image_id: str,
    region_id: str,
    request: RegionCDSSAssessmentRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    if str(request.region_id) != region_id:
        raise HTTPException(status_code=404, detail="Region ID không khớp đường dẫn.")
    return save_region_assessment(db, study_id, image_id, request, current_user)


@router.get("/api/cases/{study_id}/images/{image_id}/reviews/{review_id}/region-candidates")
def get_review_region_candidates(study_id: str, image_id: str, review_id: str, db: Session = Depends(get_db)):
    """List candidate regions from one immutable review; indices are not lesion IDs."""
    image = db.query(ImageModel).filter_by(id=image_id, study_id=study_id).first()
    review = db.query(ReviewModel).filter_by(id=review_id, image_id=image_id).first() if image else None
    if review is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản rà soát của ảnh trong ca.")
    try:
        mask = InferenceEngine.rle_to_mask(review.verified_mask_rle)
        result = review_component_candidates(mask)
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise HTTPException(status_code=422, detail="Không thể phân tích mask của bản rà soát.") from exc
    return {"study_id": study_id, "image_id": image_id, "review_id": review_id, **result}


@router.get("/api/cases/{study_id}/images/{image_id}/reviews/{review_id}/region-proposals")
def get_review_region_proposals(study_id: str, image_id: str, review_id: str, db: Session = Depends(get_db)):
    return region_proposals(db, study_id, image_id, review_id)


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

