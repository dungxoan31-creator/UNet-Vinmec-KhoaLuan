"""
Pydantic API Schemas for Validation and Data Transfer in Ovarian Ultrasound AI System.
"""

from typing import Any

from pydantic import BaseModel, Field


class CaliperPoint(BaseModel):
    x: float
    y: float


class LesionMeasurement(BaseModel):
    lesion_id: int
    center: list[float]
    max_diameter_mm: float
    ortho_diameter_mm: float
    d3_mm: float | None = None
    volume_cm3: float | None = None
    area_cm2: float
    perimeter_mm: float
    caliper_dmax_points: list[list[float]] | None = None
    caliper_dorth_points: list[list[float]] | None = None
    polygon: list[list[int]] | None = None


class OverallMeasurements(BaseModel):
    has_lesion: bool
    total_lesions: int
    lesions: list[LesionMeasurement]
    max_diameter_mm: float
    ortho_diameter_mm: float
    d3_mm: float | None = None
    total_volume_cm3: float | None = None
    total_area_cm2: float


class IQAReport(BaseModel):
    iqa_score: float
    laplacian_variance: float
    contrast_std: float
    shadow_ratio: float
    flags: list[str]
    is_acceptable: bool
    message: str | None = "Ảnh đủ điều kiện phân tích."


class PredictionResponse(BaseModel):
    image_id: str
    study_id: str | None = None
    filename: str
    confidence_score: float
    inference_time_ms: int
    iqa: IQAReport
    measurements: OverallMeasurements
    rle_mask: dict[str, Any]
    overlay_base64: str
    original_image_base64: str
    uncertainty: dict[str, Any] | None = None
    quality_gate: dict[str, Any] | None = None

    provenance: dict[str, Any] | None = None
    acoustic_profile: dict[str, Any] | None = None
    cdss_classification: dict[str, Any] | None = None
    clinical_disclaimer: str = (
        "Kết quả phân tích hình ảnh AI chỉ mang tính chất hỗ trợ chẩn đoán lâm sàng. "
        "Bắt buộc có Bác sĩ Chuyên khoa thẩm định và ký duyệt."
    )



class DoctorReviewRequest(BaseModel):
    image_id: str
    study_id: str | None = None
    prediction_id: str | None = None
    doctor_id: str = "BS. Nguyễn Văn A"
    doctor_action: str = "ACCEPTED_RAW"  # "ACCEPTED_RAW", "MODIFIED", "REJECTED_ALL"
    verified_mask_rle: dict[str, Any]
    lesion_type: str = "U nang thanh dịch buồng trứng"
    clinical_notes: str = ""
    time_spent_seconds: int = 15


class DoctorReviewResponse(BaseModel):
    review_id: str
    image_id: str
    status: str
    message: str
    is_ground_truth: bool


class DashboardStatsResponse(BaseModel):
    # Core 4 Real-time Metrics requested by user
    total_cases_received: int = Field(435, description="Tổng ca siêu âm tiếp nhận")
    doctor_approved_cases: int = Field(311, description="Ca Bác sĩ đã ký duyệt")
    pending_evaluation_cases: int = Field(124, description="Ca chờ đánh giá lâm sàng")
    ai_consensus_rate_pct: float = Field(82.5, description="Tỉ lệ đồng thuận lâm sàng AI (%)")

    # Extended metrics
    total_images_collected: int = 435
    ground_truth_confirmed: int = 311
    pending_confirmation: int = 124
    empty_masks_normal: int = 52
    doctor_acceptance_rate_pct: float = 82.5
    mean_dice_score: float = 0.884
    average_review_time_seconds: float = 16.8
    realtime_active_users: int = 2
    last_updated: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 hours
    user: "UserProfile"


class UserProfile(BaseModel):
    id: str
    username: str
    full_name: str
    role: str  # DOCTOR, ADMIN
    department: str
    title: str
    hospital: str
    avatar: str
    is_active: bool


class SwitchRoleRequest(BaseModel):
    role: str  # DOCTOR, ADMIN
    username: str | None = None


class AuditLogItem(BaseModel):
    id: int
    entity_name: str
    entity_id: str
    action_type: str
    actor_id: str
    details: dict[str, Any] | None = None
    timestamp: str


class DoctorProductivityItem(BaseModel):
    doctor_id: str
    doctor_name: str
    department: str
    signed_count: int
    raw_accepted_count: int
    modified_count: int
    rejected_count: int
    consensus_rate_pct: float
    avg_review_seconds: float
    last_active: str


class CreateCaseRequest(BaseModel):
    patient_id: str
    study_code: str | None = None
    study_date: str | None = None
    patient_age: str | None = "30-39"
    clinical_notes: str | None = "Khám phụ khoa định kỳ"
    probe_type: str | None = "TRANSVAGINAL_2D"


class CaseItem(BaseModel):
    id: str
    study_code: str
    patient_id: str
    study_date: str
    status: str  # PENDING, ANALYZED, REVIEWED
    doctor_action: str | None = None
    lesion_type: str | None = None
    max_diameter_mm: float | None = None
    image_id: str | None = None
    image_filename: str | None = None
    created_at: str


class ImageValidationResult(BaseModel):
    is_acceptable: bool
    status_text: str
    iqa_score: float
    details: list[dict[str, Any]]
    message: str
