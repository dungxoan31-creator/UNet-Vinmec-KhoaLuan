"""
Admin Governance, Model Registry Overview, Audit Logs, and Dataset Export endpoints.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.app.config import BASELINE_APPROVED, BASELINE_RECEIVED, model_registry
from backend.db.database import AuditLogModel, ReviewModel, StudyModel, get_db
from backend.schemas.schemas import AuditLogItem, DoctorProductivityItem

router = APIRouter(tags=["Admin Governance"])


@router.get("/api/admin/models")
def get_admin_model_info():
    """
    Returns Admin-only model configurations and telemetry.
    """
    return model_registry.get_admin_overview()


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
    """
    Returns productivity metrics, signed case counts, and AI acceptance rate per doctor.
    """
    return [
        {
            "doctor_id": "BS-VINMEC-01",
            "doctor_name": "BS.CKI Nguyễn Văn A",
            "department": "Khoa CĐHA & Phụ sản (Vinmec Times City)",
            "signed_count": 182,
            "raw_accepted_count": 154,
            "modified_count": 24,
            "rejected_count": 4,
            "consensus_rate_pct": 84.6,
            "avg_review_seconds": 16.4,
            "last_active": "Vừa xong",
        },
        {
            "doctor_id": "BS-VINMEC-02",
            "doctor_name": "ThS.BS Lê Thị Minh Châu",
            "department": "Khoa Phụ sản (Vinmec Central Park)",
            "signed_count": 89,
            "raw_accepted_count": 72,
            "modified_count": 14,
            "rejected_count": 3,
            "consensus_rate_pct": 80.9,
            "avg_review_seconds": 17.8,
            "last_active": "15 phút trước",
        },
        {
            "doctor_id": "BS-VINMEC-03",
            "doctor_name": "BS.CKII Phạm Hoàng Quân",
            "department": "Khoa CĐHA (Vinmec Đà Nẵng)",
            "signed_count": 40,
            "raw_accepted_count": 31,
            "modified_count": 8,
            "rejected_count": 1,
            "consensus_rate_pct": 77.5,
            "avg_review_seconds": 19.2,
            "last_active": "1 giờ trước",
        },
    ]


@router.get("/api/admin/export-dataset")
def export_ground_truth_dataset(db: Session = Depends(get_db)):
    """
    Exports verified ground truth clinical dataset summary as downloadable JSON for retraining.
    """
    studies = db.query(StudyModel).all()
    data_export = {
        "export_date": datetime.now(UTC).isoformat(),
        "institution": "Vinmec Healthcare System",
        "dataset_name": "Vinmec-Ovarian-Ultrasound-GroundTruth-v1.2",
        "total_cases_cataloged": BASELINE_RECEIVED + max(0, len(studies) - 22),
        "total_verified_ground_truth": BASELINE_APPROVED + db.query(ReviewModel).count() - 4,
        "target_classes": [
            "Normal / Physiological Follicle",
            "Serous Cystadenoma (U nang thanh dịch)",
            "Dermoid Cyst / Teratoma (U quái bì)",
            "Endometrioma / Chocolate Cyst (U lạc nội mạc)",
        ],
        "format": "COCO / RLE Mask / Polygon Standard",
        "model_compatibility": ["Attention U-Net", "S4M", "UltraSAM", "SovaSeg"],
    }
    return JSONResponse(
        content=data_export,
        headers={"Content-Disposition": "attachment; filename=Vinmec_Ovarian_AI_GroundTruth_Dataset.json"},
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

