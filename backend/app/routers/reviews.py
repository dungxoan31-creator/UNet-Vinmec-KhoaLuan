"""
Doctor Review, Ground Truth Sign-Off, and Medical PDF Report Generation endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.routers.auth import get_current_user
from backend.db.database import ImageModel, UserModel, get_db
from backend.schemas.schemas import (
    BatchReviewRequest,
    BatchReviewResponse,
    DoctorReviewRequest,
    DoctorReviewResponse,
    ResearchExportRequest,
)
from backend.services.review_service import persist_review_batch

router = APIRouter(tags=["Doctor Review & Reports"])


@router.post("/api/reviews/batch", response_model=BatchReviewResponse)
def submit_batch_reviews(
    request: BatchReviewRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Persist atomic, version-guarded, idempotent research reviews for a study.
    """
    return persist_review_batch(db, request, current_user, allow_partial=False)


@router.post("/api/review", response_model=DoctorReviewResponse)
def submit_doctor_review(
    review_req: DoctorReviewRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """Store a reviewed mask and audit record using atomic revision-guarded batch service."""
    if review_req.expected_revision is None:
        raise HTTPException(status_code=422, detail="Yêu cầu cung cấp expected_revision cho phiên rà soát.")
    if not review_req.request_id:
        raise HTTPException(status_code=422, detail="Yêu cầu cung cấp request_id cho phiên rà soát.")

    study_id = review_req.study_id
    if not study_id:
        img_rec = db.query(ImageModel).filter(ImageModel.id == review_req.image_id).first()
        if not img_rec:
            raise HTTPException(status_code=404, detail="Không tìm thấy ảnh y tế tương ứng.")
        study_id = img_rec.study_id

    batch_req = BatchReviewRequest(
        study_id=study_id,
        expected_revision=review_req.expected_revision,
        request_id=review_req.request_id,
        reviews=[review_req],
    )
    result = persist_review_batch(db, batch_req, current_user, allow_partial=True)
    first_review = result["reviews"][0]

    return {
        "review_id": first_review["review_id"],
        "image_id": first_review["image_id"],
        "status": "SUCCESS",
        "message": "Đã lưu mask rà soát và nhật ký thao tác.",
        "is_ground_truth": False,
        "reviewed_at": first_review.get("reviewed_at"),
        "reviewer_id": current_user.username,
    }


@router.post("/api/cases/{study_id}/research-export")
def export_case_research_bundle(
    study_id: str,
    export_req: ResearchExportRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Build and export a traceable ZIP bundle pinning exact review and AI mask snapshots.
    """
    from fastapi.responses import Response
    from backend.services.research_export import build_research_bundle

    bundle_bytes = build_research_bundle(
        db=db,
        study_id=study_id,
        review_ids=export_req.review_ids,
        expected_revision=export_req.expected_revision,
        actor=current_user,
    )
    return Response(
        content=bundle_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=study_{study_id}_research_export.zip",
        },
    )


@router.post("/api/generate-report")
def generate_report_pdf(report_payload: dict):
    """Clinical PDF requires a verified reviewer workflow."""
    raise HTTPException(status_code=501, detail="Chưa hỗ trợ xuất báo cáo lâm sàng khi chưa có xác thực chuyên môn.")

