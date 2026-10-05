"""
Pydantic API Schemas for Validation and Data Transfer in Ovarian Ultrasound AI System.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class CaliperPoint(BaseModel):
    x: float
    y: float


class LesionMeasurement(BaseModel):
    lesion_id: int
    center: list[float]
    max_diameter_mm: float | None
    ortho_diameter_mm: float | None
    d3_mm: float | None = None
    volume_cm3: float | None = None
    area_cm2: float | None
    perimeter_mm: float | None
    max_diameter_px: float | None = None
    ortho_diameter_px: float | None = None
    area_px: float | None = None
    caliper_dmax_points: list[list[float]] | None = None
    caliper_dorth_points: list[list[float]] | None = None
    polygon: list[list[int]] | None = None


class OverallMeasurements(BaseModel):
    has_lesion: bool
    total_lesions: int
    lesions: list[LesionMeasurement]
    max_diameter_mm: float | None
    ortho_diameter_mm: float | None
    d3_mm: float | None = None
    total_volume_cm3: float | None = None
    total_area_cm2: float | None
    total_area_px: float | None = None
    calibrated: bool = False


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
    prediction_id: str | None = None
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
    prediction_id: str
    doctor_id: str = "UNVERIFIED_REVIEWER"
    doctor_action: Literal["ACCEPTED_RAW", "MODIFIED", "REJECTED_ALL"] = "ACCEPTED_RAW"
    verified_mask_rle: dict[str, Any]

    @field_validator("verified_mask_rle")
    @classmethod
    def validate_mask_rle(cls, value: dict[str, Any]) -> dict[str, Any]:
        shape = value.get("shape")
        counts = value.get("counts")
        first_val = value.get("first_val")
        if shape != [512, 512] or first_val not in (0, 1):
            raise ValueError("Mask must be binary RLE with shape 512 x 512")
        if not isinstance(counts, list) or not counts or any(type(n) is not int or n <= 0 for n in counts):
            raise ValueError("RLE counts must be positive integers")
        if sum(counts) != 512 * 512:
            raise ValueError("RLE counts do not cover the full mask")
        return value
    lesion_type: str = "UNSPECIFIED"
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
    total_cases_received: int = 0
    doctor_approved_cases: int = 0
    pending_evaluation_cases: int = 0
    ai_consensus_rate_pct: float = 0.0

    # Extended metrics
    total_images_collected: int = 0
    ground_truth_confirmed: int = 0
    pending_confirmation: int = 0
    empty_masks_normal: int = 0
    doctor_acceptance_rate_pct: float = 0.0
    mean_dice_score: float | None = None
    average_review_time_seconds: float = 0.0
    realtime_active_users: int = 0
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
    patient_age: str | None = None
    clinical_notes: str | None = None
    probe_type: str | None = None
    active_ovary_side: Literal["RIGHT", "LEFT", "BOTH"] = "RIGHT"
    contralateral_status: Literal["NOT_VISUALIZED", "NORMAL", "SUSPECTED"] = "NOT_VISUALIZED"


class CaseItem(BaseModel):
    id: str
    study_code: str
    patient_id: str
    study_date: str
    status: str  # PENDING, ANALYZED, REVIEWED
    ovary_side: str = "RIGHT"
    contralateral_status: str = "NOT_VISUALIZED"
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


class CDSSEvaluateRequest(BaseModel):
    vision_findings: dict[str, Any] = Field(
        default_factory=lambda: {
            "max_diameter_mm": 35.0,
            "ortho_diameter_mm": 25.0,
            "has_solid_component": False,
            "papillary_projections_count": 0,
            "acoustic_shadowing": False,
            "fluid_echogenicity": "anechoic",
            "locules_count": 1,
            "color_score": 1,
            "has_ascites": False,
        }
    )
    patient_context: dict[str, Any] | None = Field(
        default_factory=lambda: {"age": 32, "is_postmenopausal": False}
    )


class CaseConfirmRequest(DoctorReviewRequest):
    image_id: str
    study_id: str | None = None
    prediction_id: str
    doctor_id: str = "UNVERIFIED_REVIEWER"
    doctor_action: Literal["ACCEPTED_RAW", "MODIFIED", "REJECTED_ALL"] = "ACCEPTED_RAW"
    verified_mask_rle: dict[str, Any]
    lesion_type: str = "UNSPECIFIED"
    clinical_notes: str = ""
    time_spent_seconds: int = 15


class SegmentAPIResponse(BaseModel):
    success: bool = True
    image_id: str | None = None
    rle_mask: dict[str, Any]
    binary_mask_base64: str
    confidence_score: float
    measurements: dict[str, Any]
    quality_gate: dict[str, Any] | None = None
    uncertainty: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None
