"""
Admin Governance, Model Registry Overview, Audit Logs, and Dataset Export endpoints.
"""

import json
import os
import secrets
import tempfile
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import and_, desc, false, func, or_, select
from sqlalchemy.orm import Session

from backend.app.config import model_registry
from backend.app.security import hash_password, require_admin
from backend.db.database import (
    AuditLogModel,
    FacilityModel,
    ImageModel,
    PatientModel,
    PredictionModel,
    RegionCaliperEventModel,
    ReviewModel,
    StudyModel,
    UserModel,
    VisitModel,
    get_db,
)
from backend.schemas.schemas import (
    AdminAnalyticsSummary,
    AdminCreateUserRequest,
    AdminCreateUserResponse,
    AdminDepartmentCreateRequest,
    AdminDepartmentUpdateRequest,
    AdminDrilldownCaseItem,
    AdminModelRegistrationRequest,
    AdminResetPasswordRequest,
    AdminSettingsRequest,
    AdminUpdateUserRequest,
    AuditLogItem,
    DoctorProductivityItem,
)
from backend.services.model_service import CandidateModelAdapter

router = APIRouter(tags=["Admin Governance"], dependencies=[Depends(require_admin)])


def _facility_scoped_audit_query(db: Session, current_user: UserModel):
    """Filter audit rows to resolvable records in the admin's facility."""
    query = db.query(AuditLogModel)
    if current_user.role == "ADMIN" and not current_user.facility_id:
        return query
    if not current_user.facility_id:
        return query.filter(false())

    facility_id = current_user.facility_id
    study_subq = db.query(StudyModel.id).filter(StudyModel.facility_id == facility_id)
    image_subq = db.query(ImageModel.id).filter(ImageModel.study_id.in_(study_subq))
    review_subq = db.query(ReviewModel.id).filter(ReviewModel.image_id.in_(image_subq))
    visit_subq = db.query(VisitModel.id).filter(VisitModel.facility_id == facility_id)
    region_subq = db.query(RegionCaliperEventModel.region_id).filter(
        RegionCaliperEventModel.image_id.in_(image_subq)
    )
    return query.filter(
        or_(
            and_(AuditLogModel.entity_name == "study", AuditLogModel.entity_id.in_(study_subq)),
            and_(AuditLogModel.entity_name.in_(["image", "region_assignment"]), AuditLogModel.entity_id.in_(image_subq)),
            and_(AuditLogModel.entity_name == "doctor_reviews", AuditLogModel.entity_id.in_(review_subq)),
            and_(AuditLogModel.entity_name == "visit", AuditLogModel.entity_id.in_(visit_subq)),
            and_(AuditLogModel.entity_name.in_(["region_caliper", "region_cdss_assessment"]), AuditLogModel.entity_id.in_(region_subq)),
            AuditLogModel.entity_id.in_(study_subq),
            AuditLogModel.entity_id.in_(image_subq),
            AuditLogModel.entity_id.in_(visit_subq),
        )
    )


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
def get_audit_logs(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_admin),
):
    """
    Returns detailed audit logs of doctor actions for quality assurance and compliance.
    """
    query = _facility_scoped_audit_query(db, current_user)

    logs = query.order_by(desc(AuditLogModel.timestamp)).limit(limit).all()

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
                "timestamp": log_item.timestamp.strftime("%d/%m/%Y %H:%M:%S") if log_item.timestamp else "",
            }
        )

    return result


@router.get("/api/admin/doctor-stats", response_model=list[DoctorProductivityItem])
def get_doctor_productivity_stats(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_admin),
):
    """Returns aggregated productivity and AI consensus metrics per clinician."""
    facility_id = getattr(current_user, "facility_id", None)
    users_query = db.query(UserModel).filter(UserModel.role.in_(["DOCTOR", "BS"]))
    if facility_id:
        users_query = users_query.filter(
            or_(UserModel.facility_id == facility_id, UserModel.facility_id.is_(None))
        )
    doctors = users_query.all()

    doctor_map = {d.username: d for d in doctors}
    for d in doctors:
        doctor_map[d.id] = d

    reviewed_ids = [row[0] for row in db.query(ReviewModel.doctor_id).distinct().all() if row[0]]

    results: list[DoctorProductivityItem] = []
    processed_keys = set()

    for doc in doctors:
        if doc.username in processed_keys:
            continue
        processed_keys.add(doc.username)
        processed_keys.add(doc.id)

        revs = db.query(ReviewModel).filter(
            or_(ReviewModel.doctor_id == doc.username, ReviewModel.doctor_id == doc.id)
        ).all()

        signed_count = len(revs)
        raw_accepted = sum(1 for r in revs if r.doctor_action == "ACCEPTED_RAW")
        modified = sum(1 for r in revs if r.doctor_action == "MODIFIED")
        rejected = sum(1 for r in revs if r.doctor_action == "REJECTED_ALL")
        consensus = round((raw_accepted / signed_count) * 100.0, 1) if signed_count > 0 else None

        durations = [r.time_spent_seconds for r in revs if r.time_spent_seconds is not None and r.time_spent_seconds >= 0]
        avg_sec = round(sum(durations) / len(durations), 1) if durations else None

        latest_rev = max(revs, key=lambda r: r.created_at) if revs else None
        last_act = latest_rev.created_at.strftime("%d/%m/%Y %H:%M") if latest_rev and latest_rev.created_at else "Chưa hoạt động"

        results.append(
            DoctorProductivityItem(
                doctor_id=doc.id,
                doctor_name=doc.full_name or doc.username,
                department=doc.department or "Khoa CĐHA",
                signed_count=signed_count,
                raw_accepted_count=raw_accepted,
                modified_count=modified,
                rejected_count=rejected,
                consensus_rate_pct=consensus,
                avg_review_seconds=avg_sec,
                review_duration_count=len(durations),
                last_active=last_act,
            )
        )

    for rev_id in reviewed_ids:
        if rev_id in processed_keys or not rev_id:
            continue
        processed_keys.add(rev_id)
        revs = db.query(ReviewModel).filter(ReviewModel.doctor_id == rev_id).all()
        signed_count = len(revs)
        raw_accepted = sum(1 for r in revs if r.doctor_action == "ACCEPTED_RAW")
        modified = sum(1 for r in revs if r.doctor_action == "MODIFIED")
        rejected = sum(1 for r in revs if r.doctor_action == "REJECTED_ALL")
        consensus = round((raw_accepted / signed_count) * 100.0, 1) if signed_count > 0 else None
        durations = [r.time_spent_seconds for r in revs if r.time_spent_seconds is not None and r.time_spent_seconds >= 0]
        avg_sec = round(sum(durations) / len(durations), 1) if durations else None
        latest_rev = max(revs, key=lambda r: r.created_at) if revs else None
        last_act = latest_rev.created_at.strftime("%d/%m/%Y %H:%M") if latest_rev and latest_rev.created_at else "Chưa hoạt động"

        results.append(
            DoctorProductivityItem(
                doctor_id=rev_id,
                doctor_name=f"BS ({rev_id})",
                department="Khoa CĐHA",
                signed_count=signed_count,
                raw_accepted_count=raw_accepted,
                modified_count=modified,
                rejected_count=rejected,
                consensus_rate_pct=consensus,
                avg_review_seconds=avg_sec,
                review_duration_count=len(durations),
                last_active=last_act,
            )
        )

    return sorted(results, key=lambda x: x.signed_count, reverse=True)


def _classify_lesion_category(lesion_text: str | None) -> str:
    """Normalize free-text and code-based morphology/histology labels into canonical clinical pathology types."""
    if not lesion_text or not isinstance(lesion_text, str):
        return "Khác / Chưa ghi nhận"
    txt = lesion_text.casefold()
    if any(k in txt for k in ["dermoid", "teratoma", "u quái", "u bì"]):
        return "U quái (Dermoid cyst)"
    if any(k in txt for k in ["chocolate", "endometrioma", "lạc nội mạc"]):
        return "Nang lạc nội mạc tử cung (Chocolate cyst)"
    if any(k in txt for k in ["serous", "thanh dịch"]):
        return "U nang tuyến thanh dịch"
    if any(k in txt for k in ["mucinous", "tuyến nhầy", "nhầy"]):
        return "U nang tuyến nhầy"
    if any(k in txt for k in ["simple", "nang đơn", "đơn thùy"]):
        return "Nang đơn giản"
    if any(k in txt for k in ["theca", "tế bào vỏ"]):
        return "U tế bào vỏ (Thecoma)"
    if any(k in txt for k in ["carcinoma", "ung thư", "ác tính"]):
        return "Ung thư biểu mô thanh dịch độ cao"
    if any(k in txt for k in ["normal", "bình thường"]):
        return "Buồng trứng bình thường"
    if "nang" in txt:
        return "Nang đơn giản"
    return "Khác / Chưa ghi nhận"


@router.get("/api/admin/analytics/summary", response_model=AdminAnalyticsSummary)
def get_admin_analytics_summary(
    days: int | None = Query(None, ge=1, le=365),
    doctor_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_admin),
):
    """Returns executive-level MIS metrics across operational, clinical, and AI performance."""
    facility_id = getattr(current_user, "facility_id", None)
    study_query = db.query(StudyModel)
    if facility_id:
        study_query = study_query.filter(StudyModel.facility_id == facility_id)

    # Filter by days
    if days:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        study_query = study_query.filter(StudyModel.created_at >= cutoff)

    # Filter by status
    if status:
        st = status.upper().strip()
        if st in ("COMPLETED", "REVIEWED"):
            study_query = study_query.filter(StudyModel.status.in_(["REVIEWED", "APPROVED", "LOCKED", "SIGNED_PRELIM"]))
        elif st in ("PENDING", "ACTIVE"):
            study_query = study_query.filter(StudyModel.status.notin_(["REVIEWED", "APPROVED", "LOCKED", "SIGNED_PRELIM"]))
        else:
            study_query = study_query.filter(StudyModel.status == status)

    # Filter by doctor_id
    if doctor_id:
        matching_img_study_ids = (
            db.query(ImageModel.study_id)
            .join(ReviewModel, ReviewModel.image_id == ImageModel.id)
            .filter(ReviewModel.doctor_id == doctor_id)
            .subquery()
        )
        study_query = study_query.filter(
            or_(StudyModel.assignee_id == doctor_id, StudyModel.id.in_(select(matching_img_study_ids.c.study_id)))
        )

    study_list = study_query.all()
    total_cases = len(study_list)
    completed_cases = sum(
        1 for s in study_list if s.status in ["REVIEWED", "APPROVED", "LOCKED", "SIGNED_PRELIM"]
    )
    pending_cases = total_cases - completed_cases

    matched_study_ids = [s.id for s in study_list]

    image_query = db.query(ImageModel)
    if matched_study_ids:
        image_query = image_query.filter(ImageModel.study_id.in_(matched_study_ids))
    elif total_cases == 0:
        image_query = image_query.filter(false())
    total_images = image_query.count()

    matched_image_ids = [img.id for img in image_query.all()]

    pred_query = db.query(PredictionModel)
    if matched_image_ids:
        pred_query = pred_query.filter(PredictionModel.image_id.in_(matched_image_ids))
    elif total_images == 0:
        pred_query = pred_query.filter(false())
    total_predictions = pred_query.count()

    scored_predictions = pred_query.filter(PredictionModel.iqa_score.isnot(None))
    iqa_scored_count = scored_predictions.count()
    avg_iqa_val = scored_predictions.with_entities(func.avg(PredictionModel.iqa_score)).scalar()
    avg_iqa_score = round(float(avg_iqa_val), 3) if avg_iqa_val is not None else None
    pass_iqa_count = scored_predictions.filter(PredictionModel.iqa_score >= 0.5).count()
    iqa_pass_rate_pct = round((pass_iqa_count / iqa_scored_count) * 100.0, 1) if iqa_scored_count > 0 else None

    preds_all = pred_query.all()
    iqa_tiers = {
        "Xuất sắc (≥ 0.8)": sum(1 for p in preds_all if p.iqa_score and p.iqa_score >= 0.8),
        "Đạt chuẩn (0.5 - 0.8)": sum(1 for p in preds_all if p.iqa_score and 0.5 <= p.iqa_score < 0.8),
        "Cần chú ý (< 0.5)": sum(1 for p in preds_all if p.iqa_score is not None and p.iqa_score < 0.5),
    }

    rev_query = db.query(ReviewModel)
    if matched_image_ids:
        rev_query = rev_query.filter(ReviewModel.image_id.in_(matched_image_ids))
    elif total_images == 0:
        rev_query = rev_query.filter(false())
    total_reviews = rev_query.count()

    raw_accepted = rev_query.filter(ReviewModel.doctor_action == "ACCEPTED_RAW").count()
    modified = rev_query.filter(ReviewModel.doctor_action == "MODIFIED").count()
    rejected = rev_query.filter(ReviewModel.doctor_action == "REJECTED_ALL").count()
    overall_consensus_rate_pct = round((raw_accepted / total_reviews) * 100.0, 1) if total_reviews > 0 else None

    action_distribution = {
        "ACCEPTED_RAW": raw_accepted,
        "MODIFIED": modified,
        "REJECTED_ALL": rejected,
    }

    recorded_durations = rev_query.filter(ReviewModel.time_spent_seconds.isnot(None), ReviewModel.time_spent_seconds >= 0)
    review_duration_count = recorded_durations.count()
    avg_dur = recorded_durations.with_entities(func.avg(ReviewModel.time_spent_seconds)).scalar()
    avg_review_seconds = round(float(avg_dur), 1) if avg_dur is not None else None

    active_docs = rev_query.with_entities(ReviewModel.doctor_id).distinct().count()

    orads_distribution = {
        "O-RADS 1": 0,
        "O-RADS 2": 0,
        "O-RADS 3": 0,
        "O-RADS 4": 0,
        "O-RADS 5": 0,
        "Chưa ghi nhận": 0,
    }
    for (fb,) in rev_query.with_entities(ReviewModel.hitl_feedback).all():
        if isinstance(fb, dict):
            val = str(fb.get("orads") or fb.get("orads_score") or "").upper().strip()
            matched = False
            for k in ("O-RADS 1", "O-RADS 2", "O-RADS 3", "O-RADS 4", "O-RADS 5"):
                if k in val or k.replace("-", " ") in val or k.replace("-", "") in val:
                    orads_distribution[k] += 1
                    matched = True
                    break
            if not matched:
                orads_distribution["Chưa ghi nhận"] += 1
        else:
            orads_distribution["Chưa ghi nhận"] += 1

    lesion_distribution = {
        "U quái (Dermoid cyst)": 0,
        "Nang lạc nội mạc tử cung (Chocolate cyst)": 0,
        "U nang tuyến thanh dịch": 0,
        "U nang tuyến nhầy": 0,
        "Nang đơn giản": 0,
        "U tế bào vỏ (Thecoma)": 0,
        "Ung thư biểu mô thanh dịch độ cao": 0,
        "Buồng trứng bình thường": 0,
        "Khác / Chưa ghi nhận": 0,
    }
    for (lt, fb) in rev_query.with_entities(ReviewModel.lesion_type, ReviewModel.hitl_feedback).all():
        raw_val = lt
        if (not raw_val or raw_val == "UNSPECIFIED") and isinstance(fb, dict):
            raw_val = fb.get("lesion_type") or fb.get("morphology_description")
        category = _classify_lesion_category(raw_val)
        if category in lesion_distribution:
            lesion_distribution[category] += 1
        else:
            lesion_distribution["Khác / Chưa ghi nhận"] += 1

    # Timeline Trend
    timeline_trend = []
    if study_list:
        trend_days = min(days or 7, 14)
        now_utc = datetime.now(UTC)
        for i in range(trend_days - 1, -1, -1):
            day_date = (now_utc - timedelta(days=i)).date()
            day_label = day_date.strftime("%d/%m")
            day_studies = [s for s in study_list if s.created_at and s.created_at.date() == day_date]
            tot = len(day_studies)
            comp = sum(1 for s in day_studies if s.status in ["REVIEWED", "APPROVED", "LOCKED", "SIGNED_PRELIM"])
            timeline_trend.append({"date": day_label, "total": tot, "completed": comp})

    # Patient Demographics
    demographics = {
        "Tiền mãn kinh (Pre-menopausal)": 0,
        "Sau mãn kinh (Post-menopausal)": 0,
        "Chưa ghi nhận": 0,
    }
    if matched_study_ids:
        patient_rows = (
            db.query(PatientModel.menopausal_status)
            .join(StudyModel, StudyModel.patient_id == PatientModel.id)
            .filter(StudyModel.id.in_(matched_study_ids))
            .all()
        )
        for (meno,) in patient_rows:
            if meno in ("PRE", "PREMENOPAUSAL", "PRE_MENOPAUSAL"):
                demographics["Tiền mãn kinh (Pre-menopausal)"] += 1
            elif meno in ("POST", "POSTMENOPAUSAL", "POST_MENOPAUSAL"):
                demographics["Sau mãn kinh (Post-menopausal)"] += 1
            else:
                demographics["Chưa ghi nhận"] += 1
    if not any(demographics.values()) and total_cases > 0:
        demographics["Chưa ghi nhận"] = total_cases

    return AdminAnalyticsSummary(
        total_cases=total_cases,
        completed_cases=completed_cases,
        pending_cases=pending_cases,
        total_images=total_images,
        total_predictions=total_predictions,
        total_reviews=total_reviews,
        overall_consensus_rate_pct=overall_consensus_rate_pct,
        avg_iqa_score=avg_iqa_score,
        iqa_pass_rate_pct=iqa_pass_rate_pct,
        iqa_scored_count=iqa_scored_count,
        active_doctors_count=active_docs,
        orads_distribution=orads_distribution,
        lesion_distribution=lesion_distribution,
        action_distribution=action_distribution,
        iqa_tiers=iqa_tiers,
        timeline_trend=timeline_trend,
        demographics=demographics,
        avg_review_seconds=avg_review_seconds,
        review_duration_count=review_duration_count,
        generated_at=datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S"),
    )


@router.get("/api/admin/reports/cases", response_model=list[AdminDrilldownCaseItem])
def get_admin_drilldown_cases(
    orads: str | None = None,
    lesion_type: str | None = None,
    doctor_id: str | None = None,
    days: int | None = Query(None, ge=1, le=365),
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_admin),
):
    """
    Returns drill-down case metadata matching selected clinical chart filters.
    Only aggregated operational metadata is returned; patient pixel images and PII are omitted.
    """
    facility_id = getattr(current_user, "facility_id", None)
    query = db.query(StudyModel)
    if facility_id:
        query = query.filter(StudyModel.facility_id == facility_id)

    if days:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        query = query.filter(StudyModel.created_at >= cutoff)

    if status:
        st = status.upper().strip()
        if st in ("COMPLETED", "REVIEWED"):
            query = query.filter(StudyModel.status.in_(["REVIEWED", "APPROVED", "LOCKED", "SIGNED_PRELIM"]))
        elif st in ("PENDING", "ACTIVE"):
            query = query.filter(StudyModel.status.notin_(["REVIEWED", "APPROVED", "LOCKED", "SIGNED_PRELIM"]))
        else:
            query = query.filter(StudyModel.status == status)

    studies = query.order_by(desc(StudyModel.created_at)).limit(limit * 3).all()

    doctor_names = {u.id: u.full_name for u in db.query(UserModel).all()}
    for u in db.query(UserModel).all():
        doctor_names[u.username] = u.full_name

    items: list[AdminDrilldownCaseItem] = []
    for s in studies:
        image_ids = [img.id for img in s.images] if s.images else []
        revs = db.query(ReviewModel).filter(ReviewModel.image_id.in_(image_ids)).all() if image_ids else []

        latest_rev = max(revs, key=lambda r: r.created_at) if revs else None

        fb = latest_rev.hitl_feedback if (latest_rev and isinstance(latest_rev.hitl_feedback, dict)) else {}
        extracted_orads = "Chưa ghi nhận"
        if fb:
            val = fb.get("orads") or fb.get("orads_score")
            if val:
                extracted_orads = str(val).strip()

        raw_lt = latest_rev.lesion_type if latest_rev else None
        if (not raw_lt or raw_lt == "UNSPECIFIED") and fb:
            raw_lt = fb.get("lesion_type") or fb.get("morphology_description")
        extracted_category = _classify_lesion_category(raw_lt)

        doc_key = latest_rev.doctor_id if latest_rev else (s.assignee_id or "Chưa phân công")
        doc_display = doctor_names.get(doc_key, doc_key)

        if orads:
            norm_filter_orads = orads.upper().replace("-", "").replace(" ", "")
            norm_actual_orads = extracted_orads.upper().replace("-", "").replace(" ", "")
            if norm_filter_orads not in norm_actual_orads:
                continue

        if lesion_type:
            if (
                lesion_type.casefold() not in extracted_category.casefold()
                and lesion_type.casefold() not in str(raw_lt or "").casefold()
            ):
                continue

        if doctor_id:
            if doctor_id != doc_key:
                continue

        d1 = latest_rev.max_diameter_mm if latest_rev else None
        d2 = latest_rev.ortho_diameter_mm if latest_rev else None
        if d1 and d2:
            meas_text = f"{d1:.1f} × {d2:.1f} mm"
        elif d1:
            meas_text = f"{d1:.1f} mm"
        else:
            meas_text = "Chưa ghi nhận"

        items.append(
            AdminDrilldownCaseItem(
                study_id=s.id,
                study_code=s.study_code or s.id[:8],
                visit_no=s.visit_no,
                study_date=s.study_date or "—",
                status=s.status or "PENDING",
                doctor_id=doc_key,
                doctor_name=doc_display,
                orads=extracted_orads,
                lesion_type=extracted_category,
                measurements_summary=meas_text,
            )
        )
        if len(items) >= limit:
            break

    return items


@router.get("/api/admin/reports/cases/export-csv")
def export_admin_drilldown_cases_csv(
    orads: str | None = None,
    lesion_type: str | None = None,
    doctor_id: str | None = None,
    days: int | None = Query(None, ge=1, le=365),
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_admin),
):
    """Export drill-down filtered cases to CSV."""
    cases = get_admin_drilldown_cases(
        orads=orads,
        lesion_type=lesion_type,
        doctor_id=doctor_id,
        days=days,
        status=status,
        limit=500,
        db=db,
        current_user=current_user,
    )
    csv_lines = [
        "Mã ca,Đợt khám,Ngày khám,Trạng thái,Bác sĩ phụ trách,Phân tầng O-RADS,Mặt bệnh / Loại tổn thương,Kích thước"
    ]
    for c in cases:
        csv_lines.append(
            f'"{c.study_code}","{c.visit_no or ""}","{c.study_date}","{c.status}","{c.doctor_name}","{c.orads}","{c.lesion_type}","{c.measurements_summary}"'
        )
    csv_content = "\ufeff" + "\n".join(csv_lines)
    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=drilldown_cases_report.csv"},
    )


@router.get("/api/admin/reports/doctor-productivity/export-csv")
def export_doctor_productivity_csv(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_admin),
):
    """Export doctor productivity report as a UTF-8 with BOM CSV file for Excel."""
    stats = get_doctor_productivity_stats(db=db, current_user=current_user)
    csv_lines = ["Mã BS,Họ và tên,Khoa phòng,Số ca ký duyệt,Chấp thuận AI,Chỉnh sửa,Từ chối,Tỷ lệ đồng thuận (%),Thời gian TB (giây),Hoạt động cuối"]
    for s in stats:
        csv_lines.append(
            f'"{s.doctor_id}","{s.doctor_name}","{s.department}",{s.signed_count},{s.raw_accepted_count},{s.modified_count},{s.rejected_count},{s.consensus_rate_pct},{s.avg_review_seconds},"{s.last_active}"'
        )
    csv_content = "\ufeff" + "\n".join(csv_lines)
    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=doctor_productivity_report.csv"},
    )


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
def trigger_backup(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_admin),
):
    """
    Creates a database-only backup; admin routes do not package patient images.
    """
    _require_global_admin(current_user)
    from backend.services.backup_service import BackupService

    backup_service = BackupService()
    result = backup_service.create_backup(include_images=False)
    db.add(AuditLogModel(
        entity_name="backup",
        entity_id=str(result.get("backup_filename", "")),
        action_type="BACKUP_CREATED",
        actor_id=current_user.id,
        details={"included_images": False},
        timestamp=datetime.now(UTC),
    ))
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        backup_path = result.get("backup_path")
        try:
            if backup_path and os.path.isfile(backup_path):
                os.remove(backup_path)
        except OSError as cleanup_exc:
            raise HTTPException(
                status_code=500,
                detail="Không ghi được nhật ký sao lưu và không thể dọn archive vừa tạo.",
            ) from cleanup_exc
        raise HTTPException(
            status_code=500,
            detail="Không ghi được nhật ký sao lưu; archive vừa tạo đã được dọn.",
        ) from exc
    return {
        key: result[key]
        for key in ("status", "backup_filename", "size_mb", "timestamp", "included_images", "encryption")
        if key in result
    }


@router.get("/api/admin/backups/list")
def list_backups(current_user: UserModel = Depends(require_admin)):
    """
    Returns list of all available system backups.
    """
    _require_global_admin(current_user)
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


def _require_global_admin(current_user: UserModel) -> None:
    if not (
        current_user.role == "ADMIN"
        and bool(getattr(current_user, "is_global_admin", False))
        and not current_user.facility_id
    ):
        raise HTTPException(status_code=403, detail="Thao tác này chỉ dành cho quản trị viên toàn hệ thống.")


def _settings_facility(db: Session, current_user: UserModel, requested_id: str | None) -> FacilityModel:
    is_global = bool(getattr(current_user, "is_global_admin", False)) and not current_user.facility_id
    if is_global:
        if not requested_id:
            raise HTTPException(status_code=422, detail="Quản trị viên toàn hệ thống cần chọn cơ sở.")
        facility_id = requested_id
    else:
        if not current_user.facility_id:
            raise HTTPException(status_code=403, detail="Tài khoản chưa được gán cơ sở y tế.")
        if requested_id and requested_id != current_user.facility_id:
            raise HTTPException(status_code=403, detail="Không có quyền cấu hình cơ sở khác.")
        facility_id = current_user.facility_id
    facility = db.get(FacilityModel, facility_id)
    if facility is None or not facility.is_active:
        raise HTTPException(status_code=404, detail="Cơ sở không tồn tại hoặc đã ngừng hoạt động.")
    return facility


def _facility_settings(facility: FacilityModel) -> dict:
    config = facility.config if isinstance(facility.config, dict) else {}
    saved = config.get("admin_settings", {})
    settings = {**_DEFAULT_ADMIN_SETTINGS, "hospital_name": facility.name, "report_header": facility.name}
    if isinstance(saved, dict):
        settings.update({key: value for key, value in saved.items() if key in _DEFAULT_ADMIN_SETTINGS})
    return {**settings, "facility_id": facility.id, "facility_name": facility.name}

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
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return paginated audit logs conforming to frontend contract."""
    query = _facility_scoped_audit_query(db, current_user)
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
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Export audit events filtered by query criteria for admin compliance review (BE-11)."""
    query = _facility_scoped_audit_query(db, current_user)
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
    offset: int | None = Query(None, ge=0),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_admin),
):
    """Return a minimal operational summary without patient or image metadata."""
    search_query = q or search
    query = db.query(StudyModel)
    if current_user.facility_id:
        query = query.filter(StudyModel.facility_id == current_user.facility_id)
    if search_query:
        query = query.filter(StudyModel.study_code.ilike(f"%{search_query.strip()}%"))
    if status and status.upper() != "ALL":
        query = query.filter(StudyModel.status == status.upper())
    if date:
        query = query.filter(StudyModel.study_date.startswith(date))

    total = query.count()
    if limit is not None or offset is not None:
        effective_limit = limit if limit is not None else page_size
        effective_offset = offset if offset is not None else 0
    else:
        effective_limit = page_size
        effective_offset = (page - 1) * page_size

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


@router.post("/api/admin/users", response_model=AdminCreateUserResponse)
def create_admin_user(
    user_data: AdminCreateUserRequest,
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db),
):
    is_global = getattr(current_user, "is_global_admin", False) and not current_user.facility_id
    if not is_global and not current_user.facility_id:
        raise HTTPException(status_code=403, detail="Tài khoản chưa được gán cơ sở y tế.")
    user_fac_id = getattr(user_data, "facility_id", None)
    if not is_global and user_fac_id and user_fac_id != current_user.facility_id:
        raise HTTPException(status_code=403, detail="Không có quyền tạo tài khoản cho cơ sở khác.")
    assigned_facility_id = user_fac_id if is_global else current_user.facility_id
    """Create a new user account administratively."""
    raw_username = (user_data.username or "").strip()
    if not raw_username:
        raise HTTPException(status_code=422, detail="Tên đăng nhập không được để trống")
    if len(raw_username) > 50:
        raise HTTPException(status_code=422, detail="Tên đăng nhập không được vượt quá 50 ký tự")
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
        facility_id=assigned_facility_id,
        is_global_admin=False,
        password_hash=hash_password(password),
        must_change_password=must_change,
    )
    db.add(user)
    db.commit()
    return {
        "status": "SUCCESS",
        "user_id": user.id,
        "username": user.username,
        "must_change_password": must_change,
        "temp_password": temp_password,
    }


@router.patch("/api/admin/users/{user_id}")
def update_admin_user(
    user_id: str,
    payload: AdminUpdateUserRequest,
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update user account attributes."""
    is_global = getattr(current_user, "is_global_admin", False) and not current_user.facility_id
    user = db.query(UserModel).filter((UserModel.id == user_id) | (UserModel.username == user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    if not is_global and user.facility_id != current_user.facility_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    payload_data = payload.model_dump(exclude_unset=True)
    if "username" in payload_data and payload_data["username"].lower() != user.username:
        raise HTTPException(status_code=422, detail="Tên đăng nhập không thể thay đổi.")
    updated_fields = {}
    if "full_name" in payload_data:
        user.full_name = payload_data["full_name"]
        updated_fields["full_name"] = payload_data["full_name"]
    if "role" in payload_data:
        new_role = canonicalize_user_role(payload_data["role"])
        if user.id == current_user.id and new_role != "ADMIN":
            raise HTTPException(status_code=400, detail="Không thể tự tước quyền quản trị của chính mình.")
        if getattr(user, "is_global_admin", False) and new_role != "ADMIN":
            remaining = db.query(UserModel).filter(
                UserModel.is_global_admin.is_(True),
                UserModel.id != user.id,
                UserModel.role == "ADMIN",
                UserModel.is_active.is_(True),
            ).count()
            if remaining == 0:
                raise HTTPException(status_code=400, detail="Không thể hạ cấp quản trị viên hệ thống duy nhất.")
        user.role = new_role
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

        if user.id == current_user.id and not new_active:
            raise HTTPException(status_code=400, detail="Không thể tự khóa tài khoản của chính mình.")
        if getattr(user, "is_global_admin", False) and not new_active:
            remaining = db.query(UserModel).filter(
                UserModel.is_global_admin.is_(True),
                UserModel.id != user.id,
                UserModel.is_active.is_(True),
            ).count()
            if remaining == 0:
                raise HTTPException(status_code=400, detail="Không thể khóa quản trị viên hệ thống duy nhất.")
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
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin resets user password."""
    is_global = getattr(current_user, "is_global_admin", False) and not current_user.facility_id
    user = db.query(UserModel).filter((UserModel.id == user_id) | (UserModel.username == user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    if not is_global and user.facility_id != current_user.facility_id:
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
    return {
        "status": "SUCCESS",
        "message": "Đã đặt lại mật khẩu người dùng.",
        "must_change_password": must_change,
        "temp_password": temp_password,
    }


@router.delete("/api/admin/users/{user_id}")
def delete_admin_user(
    user_id: str,
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a user account administratively."""
    is_global = getattr(current_user, "is_global_admin", False) and not current_user.facility_id
    user = db.query(UserModel).filter((UserModel.id == user_id) | (UserModel.username == user_id)).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    if not is_global and user.facility_id != current_user.facility_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Không thể tự xóa tài khoản của chính mình.")
    if getattr(user, "is_global_admin", False):
        remaining = db.query(UserModel).filter(UserModel.is_global_admin.is_(True), UserModel.id != user.id).count()
        if remaining == 0:
            raise HTTPException(status_code=400, detail="Không thể xóa quản trị viên hệ thống duy nhất.")
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
def get_admin_settings(
    facility_id: str | None = Query(None, min_length=1, max_length=36),
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return report settings for the administrator's facility."""
    facility = _settings_facility(db, current_user, facility_id)
    return _facility_settings(facility)


@router.put("/api/admin/settings")
def update_admin_settings(
    settings: AdminSettingsRequest,
    current_user: UserModel = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update settings only for the administrator's assigned facility."""
    facility = _settings_facility(db, current_user, settings.facility_id)
    values = settings.model_dump(exclude_unset=True)
    values.pop("facility_id", None)
    config = dict(facility.config) if isinstance(facility.config, dict) else {}
    current = config.get("admin_settings")
    facility_settings = dict(current) if isinstance(current, dict) else {}
    facility_settings.update(values)
    config["admin_settings"] = facility_settings
    facility.config = config
    db.add(AuditLogModel(
        entity_name="facility_settings",
        entity_id=facility.id,
        action_type="SETTINGS_UPDATED",
        actor_id=current_user.id,
        details={"fields": sorted(values)},
        timestamp=datetime.now(UTC),
    ))
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Không thể lưu cấu hình quản trị.") from exc
    return {
        "status": "SUCCESS",
        "message": "Đã lưu cấu hình.",
        "settings": _facility_settings(facility),
    }


@router.get("/api/admin/metadata")
def get_admin_metadata(
    facility_id: str | None = Query(None, min_length=1, max_length=36),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_admin),
):
    """Return administrative metadata for one authorized facility."""
    facility = _settings_facility(db, current_user, facility_id)
    study_ids = db.query(StudyModel.id).filter(StudyModel.facility_id == facility.id)
    image_ids = db.query(ImageModel.id).filter(ImageModel.study_id.in_(study_ids))
    return {
        "hospital_name": _facility_settings(facility)["hospital_name"],
        "facility_id": facility.id,
        "system_version": "2.0.0",
        "total_cases": db.query(StudyModel).filter(StudyModel.facility_id == facility.id).count(),
        "total_images": db.query(ImageModel).filter(ImageModel.study_id.in_(study_ids)).count(),
        "total_reviews": db.query(ReviewModel).filter(ReviewModel.image_id.in_(image_ids)).count(),
        "total_users": db.query(UserModel).filter(UserModel.facility_id == facility.id).count(),
    }

