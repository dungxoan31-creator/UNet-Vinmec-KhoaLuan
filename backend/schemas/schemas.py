"""
Pydantic API Schemas for Validation and Data Transfer in Ovarian Ultrasound AI System.
"""

import json
import math
import re
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
    field_validator,
    model_validator,
)

from backend.core.hitl_event_types import CLIENT_HITL_EVENT_TYPES

VisitNumber = Annotated[StrictStr, StringConstraints(pattern=r"^[0-9]{6}$", min_length=6, max_length=6)]

ORADS_REVIEW_VALUE = Literal[
    "",
    "O-RADS 0",
    "O-RADS 1",
    "O-RADS 2",
    "O-RADS 3",
    "O-RADS 4",
    "O-RADS 5",
]
ReviewRequestId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=36, strict=True),
]


class NotificationReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[str] = Field(default_factory=list, max_length=100)


class UserFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=120, strict=True)
    message: str = Field(min_length=1, max_length=2000, strict=True)


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    old_password: StrictStr | None = Field(default=None, max_length=256)
    current_password: StrictStr | None = Field(default=None, max_length=256)
    new_password: StrictStr = Field(max_length=256)
    confirmation: StrictStr | None = Field(default=None, max_length=256)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: StrictStr = Field(min_length=1, max_length=50)


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: StrictStr | None = Field(default=None, max_length=50)
    token: StrictStr | None = Field(default=None, max_length=4096)
    new_password: StrictStr | None = Field(default=None, max_length=256)


AdminRole = Literal["BS", "DOCTOR", "QT", "ADMIN"]


class AdminCreateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: StrictStr | None = Field(default=None, max_length=50)
    full_name: StrictStr | None = Field(default=None, max_length=100)
    role: AdminRole = "DOCTOR"
    department: StrictStr | None = Field(default=None, max_length=100)
    password: StrictStr | None = Field(default=None, max_length=256)
    facility_id: StrictStr | None = Field(default=None, max_length=36)


class AdminUpdateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: StrictStr | None = Field(default=None, max_length=50)
    full_name: StrictStr | None = Field(default=None, max_length=100)
    role: AdminRole | None = None
    department: StrictStr | None = Field(default=None, max_length=100)
    is_active: StrictBool | StrictStr | None = None
    facility_id: StrictStr | None = Field(default=None, max_length=36)

    @model_validator(mode="after")
    def reject_explicit_null_values(self):
        for field in ("full_name", "role", "department", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null when supplied")
        return self


class AdminResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_password: str | None = Field(default=None, max_length=256)


class AdminCreateUserResponse(BaseModel):
    status: str
    user_id: str
    username: str
    must_change_password: bool
    temp_password: str | None = None


class AdminDepartmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: StrictStr = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr = Field(min_length=1, max_length=100)
    code: StrictStr | None = Field(default=None, min_length=1, max_length=32)


class AdminDepartmentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: StrictStr | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: StrictStr | None = Field(default=None, min_length=1, max_length=100)
    code: StrictStr | None = Field(default=None, min_length=1, max_length=32)

    @model_validator(mode="after")
    def require_update_fields(self):
        if not ({"name", "code"} & self.model_fields_set):
            raise ValueError("At least one department field must be updated")
        for field in ("name", "code"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null when supplied")
        return self


class AdminModelRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    model_id: StrictStr | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    name: StrictStr | None = Field(default=None, min_length=1, max_length=100)
    version: StrictStr | None = Field(default=None, min_length=1, max_length=32)
    architecture: StrictStr | None = Field(default=None, min_length=1, max_length=100)
    checkpoint: StrictStr | None = Field(default=None, min_length=1, max_length=512)
    artifact_id: StrictStr | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def require_checkpoint_reference(self):
        if not self.checkpoint and not self.artifact_id:
            raise ValueError("A checkpoint path or server artifact identifier is required")
        return self


class AdminSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    facility_id: StrictStr | None = Field(default=None, min_length=1, max_length=36)
    hospital_name: StrictStr | None = Field(default=None, min_length=1, max_length=120)
    report_header: StrictStr | None = Field(default=None, min_length=1, max_length=200)
    unit: Literal["auto"] | None = None

    @model_validator(mode="after")
    def require_setting(self):
        fields = self.model_fields_set
        if not fields.intersection({"hospital_name", "report_header", "unit"}):
            raise ValueError("At least one supported setting must be supplied")
        for field in ("hospital_name", "report_header", "unit"):
            if field in fields and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null when supplied")
        return self


class CaseLeaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tab_id: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    page_instance_id: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    lease_token: str | None = Field(
        default=None,
        min_length=32,
        max_length=256,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class CaseLeaseReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lease_token: str = Field(min_length=32, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")
    page_instance_id: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


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
    follicles: dict[str, Any] | None = None


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
    overlay_base64: str | None = None
    original_image_base64: str | None = None
    uncertainty_map_base64: str | None = None
    uncertainty: dict[str, Any] | None = None
    quality_gate: dict[str, Any] | None = None

    provenance: dict[str, Any] | None = None
    timings: dict[str, Any] | None = None
    acoustic_profile: dict[str, Any] | None = None
    cdss_classification: dict[str, Any] | None = None
    ai_diagnosis: dict[str, Any] | None = None
    unified_findings: dict[str, Any] | None = None
    idempotent_replay: bool = False
    clinical_disclaimer: str = (
        "Kết quả này chỉ phục vụ nghiên cứu (RUO), chưa được xác thực lâm sàng. "
        "Bác sĩ cần tự thẩm định kết quả trước khi sử dụng. Hệ thống hỗ trợ phân đoạn và đo lường; "
        "không đưa ra chẩn đoán hoặc phê duyệt báo cáo lâm sàng."
    )


InferenceResponse = PredictionResponse



class HITLFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usability_rating: StrictInt | None = Field(default=None, ge=1, le=5)
    issues: list[Literal["FALSE_NEGATIVE", "FALSE_POSITIVE", "BOUNDARY_MISMATCH", "NO_ERROR"]] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def validate_issues(self):
        if len(set(self.issues)) != len(self.issues):
            raise ValueError("Survey issues must not contain duplicates")
        if "NO_ERROR" in self.issues and len(self.issues) != 1:
            raise ValueError("NO_ERROR cannot be combined with segmentation errors")
        return self


class ManualCaliper(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Literal["D1", "D2"]
    points: list[list[StrictInt | StrictFloat]] = Field(min_length=2, max_length=2)
    coordinate_space: Literal["decoded-source-image"] = "decoded-source-image"

    @field_validator("points")
    @classmethod
    def validate_points(cls, points):
        if len(points) != 2 or any(len(point) != 2 for point in points):
            raise ValueError("Caliper requires two finite, non-negative source-image points.")

        normalized_points = []
        for point in points:
            normalized_point = []
            for value in point:
                if type(value) not in (int, float) or value < 0:
                    raise ValueError("Caliper requires two finite, non-negative source-image points.")
                try:
                    numeric_value = float(value)
                except (OverflowError, TypeError, ValueError) as exc:
                    raise ValueError(
                        "Caliper requires two finite, non-negative source-image points."
                    ) from exc
                if not math.isfinite(numeric_value):
                    raise ValueError("Caliper requires two finite, non-negative source-image points.")
                normalized_point.append(numeric_value)
            normalized_points.append(normalized_point)

        if normalized_points[0] == normalized_points[1]:
            raise ValueError("Caliper endpoints must be different.")
        return normalized_points


class DoctorReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
        unknown_fields = set(value) - {"shape", "counts", "first_val", "encoding"}
        if unknown_fields:
            raise ValueError("RLE fields are not recognized.")
        if (
            not isinstance(shape, (list, tuple))
            or len(shape) != 2
            or type(shape[0]) is not int
            or type(shape[1]) is not int
            or shape[0] != 512
            or shape[1] != 512
            or type(first_val) is not int
            or first_val not in (0, 1)
            or ("encoding" in value and value["encoding"] != "standard_rle")
        ):
            raise ValueError("Mask must be binary RLE with shape 512 x 512")
        if not isinstance(counts, list) or not counts:
            raise ValueError("RLE counts must be positive integers")
        if len(counts) > 512 * 512:
            raise ValueError("RLE counts exceed the maximum run count")
        if any(type(n) is not int or n <= 0 for n in counts):
            raise ValueError("RLE counts must be positive integers")
        if sum(counts) != 512 * 512:
            raise ValueError("RLE counts do not cover the full mask")
        return value
    lesion_type: str = Field(default="UNSPECIFIED", max_length=100)
    clinical_notes: str = ""
    orads: ORADS_REVIEW_VALUE | None = None
    orads_score: ORADS_REVIEW_VALUE | None = None
    morphology_description: str | None = None
    time_spent_seconds: int | None = Field(default=None, ge=0)
    hitl_feedback: HITLFeedback | None = None
    manual_calipers: list[ManualCaliper] = Field(default_factory=list, max_length=2)
    lease_token: str | None = Field(
        default=None,
        min_length=32,
        max_length=256,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    page_instance_id: str | None = Field(
        default=None,
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    expected_revision: int | None = None
    request_id: ReviewRequestId | None = None
    clinician_overrides: dict[str, Any] | None = None

    @field_validator("orads", "orads_score", mode="before")
    @classmethod
    def normalize_legacy_orads_codes(cls, value):
        if isinstance(value, str) and value in {str(score) for score in range(6)}:
            return f"O-RADS {value}"
        return value

    @model_validator(mode="after")
    def validate_orads_aliases(self):
        if self.orads and self.orads_score and self.orads != self.orads_score:
            raise ValueError("orads and orads_score must match when both are set")
        labels = [item.label for item in self.manual_calipers]
        if len(labels) != len(set(labels)):
            raise ValueError("Only one manual caliper is allowed for each of D1 and D2.")
        return self


class ReviewSummaryItem(BaseModel):
    review_id: str
    image_id: str
    prediction_id: str
    doctor_action: str
    reviewed_at: str | None = None


class BatchReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_id: str
    expected_revision: int
    request_id: ReviewRequestId
    reviews: list[DoctorReviewRequest]
    hitl_session_id: str | None = None
    telemetry_tasks: list[dict[str, Any]] | None = None
    lease_token: str | None = Field(
        default=None,
        min_length=32,
        max_length=256,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    page_instance_id: str | None = Field(
        default=None,
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class BatchReviewResponse(BaseModel):
    status: str = "SUCCESS"
    study_id: str
    review_revision: int
    reviews: list[ReviewSummaryItem]
    message: str = "Đã lưu rà soát nghiên cứu thành công."


class ResearchExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_ids: list[str]
    expected_revision: int
    ethics_approval_code: str = Field(..., min_length=1, description="Mã phê duyệt Hội đồng Đạo đức y sinh (IRB Approval Code) bắt buộc")
    patient_consent_confirmed: bool = Field(False, description="Xác nhận đồng thuận của bệnh nhân (bắt buộc phải là True)")


class HITLSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_id: str
    participant_code: str = Field(min_length=1, max_length=64)
    participant_role: Literal["clinician", "technical_tester"] = "technical_tester"
    data_origin: Literal["live", "technical_fixture", "demo"] = "live"


class HITLEventItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: StrictStr = Field(min_length=1, max_length=36)
    task_id: StrictStr = Field(min_length=1, max_length=36)
    image_id: StrictStr = Field(min_length=1, max_length=36)
    prediction_id: StrictStr | None = Field(default=None, min_length=1, max_length=36)
    seq: StrictInt = Field(ge=1)
    event_type: StrictStr = Field(min_length=1, max_length=50)
    client_utc: StrictStr = Field(min_length=1, max_length=50)
    elapsed_ms: float = Field(ge=0)
    session_elapsed_ms: float = Field(ge=0)
    payload: dict[StrictStr, StrictStr | StrictInt | StrictFloat | StrictBool | None] | None = Field(
        default=None,
        max_length=32,
    )

    @field_validator("event_type")
    @classmethod
    def validate_client_event_type(cls, value: str) -> str:
        if value not in CLIENT_HITL_EVENT_TYPES:
            raise ValueError(f"Sự kiện client không hợp lệ hoặc bị cấm: {value}")
        return value

    @field_validator("client_utc")
    @classmethod
    def validate_client_utc_timestamp(cls, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("client_utc must be an ISO 8601 UTC timestamp.") from exc
        if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise ValueError("client_utc must include a UTC timezone.")
        return value

    @field_validator("elapsed_ms", "session_elapsed_ms")
    @classmethod
    def validate_finite_duration(cls, value: float) -> float:
        if not math.isfinite(value) or value < 0:
            raise ValueError("Thời lượng phải là số hữu hạn không âm")
        return value


    @field_validator("payload")
    @classmethod
    def validate_payload_size(cls, value):
        if value is None:
            return None
        try:
            encoded = json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("HITL payload must be bounded JSON scalar data.") from exc
        if len(encoded) > 4096:
            raise ValueError("HITL payload must not exceed 4096 UTF-8 bytes.")
        return value


class HITLEventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[HITLEventItem] = Field(min_length=1, max_length=100)


class UIEventItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    case_id: str | None = Field(default=None, max_length=64)
    event: str = Field(..., min_length=1, max_length=50)
    t_ms: float
    payload: dict[str, Any] | None = None


class UIEventBatchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    events: list[UIEventItem] = Field(min_length=1, max_length=500)


class HITLSessionResponse(BaseModel):
    id: str
    study_id: str
    actor_id: str
    participant_code: str
    participant_role: str
    data_origin: str
    status: str
    created_at: str
    completed_at: str | None = None
    review_batch_id: str | None = None




class MaskMeasurementsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rle_mask: dict[str, Any]

    @field_validator("rle_mask")
    @classmethod
    def validate_mask_rle(cls, value):
        return DoctorReviewRequest.validate_mask_rle(value)


class DoctorReviewResponse(BaseModel):
    review_id: str
    image_id: str
    status: str
    message: str
    is_ground_truth: bool
    reviewed_at: str | None = None
    reviewer_id: str | None = None



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
    model_config = ConfigDict(extra="forbid")

    username: StrictStr = Field(max_length=50)
    password: StrictStr | None = Field(default=None, max_length=256)


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: StrictStr = Field(max_length=50)
    password: StrictStr = Field(max_length=256)
    full_name: StrictStr = Field(max_length=100)
    email: StrictStr = Field(max_length=254)
    role: Literal["DOCTOR", "ADMIN"] = "DOCTOR"
    department: StrictStr = Field(default="Khoa Chẩn đoán Hình ảnh & Sản Phụ khoa", max_length=100)
    title: StrictStr = Field(default="BS", max_length=50)
    hospital: StrictStr = Field(default="Chưa cấu hình", max_length=100)


    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        pattern = r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$"
        if len(email) > 254 or not re.fullmatch(pattern, email):
            raise ValueError("A valid email address is required.")
        return email


class EmailVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: StrictStr = Field(max_length=254)
    code: StrictStr = Field(pattern=r"^[0-9]{6}$", max_length=6)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ResendEmailVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: StrictStr = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RegistrationResponse(BaseModel):
    status: Literal["PENDING_EMAIL_VERIFICATION"] = "PENDING_EMAIL_VERIFICATION"
    email: str
    email_verification_required: bool = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 hours
    user: "UserProfile"
    must_change_password: bool = False


class UserProfile(BaseModel):
    id: str
    username: str
    full_name: str
    role: str  # DOCTOR, ADMIN
    facility_id: str | None = None
    is_global_admin: bool = False
    department: str
    title: str
    hospital: str
    avatar: str
    is_active: bool
    must_change_password: bool = False


class SwitchRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    consensus_rate_pct: float | None
    avg_review_seconds: float | None
    review_duration_count: int = 0
    last_active: str


class AdminDrilldownCaseItem(BaseModel):
    study_id: str
    study_code: str
    visit_no: VisitNumber | None = None
    study_date: str
    status: str
    doctor_id: str
    doctor_name: str
    orads: str
    lesion_type: str
    measurements_summary: str


class AdminAnalyticsSummary(BaseModel):
    total_cases: int
    completed_cases: int
    pending_cases: int
    total_images: int
    total_predictions: int
    total_reviews: int
    overall_consensus_rate_pct: float | None
    avg_iqa_score: float | None
    iqa_pass_rate_pct: float | None
    iqa_scored_count: int = 0
    active_doctors_count: int
    orads_distribution: dict[str, int]
    lesion_distribution: dict[str, int]
    action_distribution: dict[str, int]
    iqa_tiers: dict[str, int] = {}
    timeline_trend: list[dict[str, Any]] = []
    demographics: dict[str, int] = {}
    avg_review_seconds: float | None
    review_duration_count: int = 0
    generated_at: str


class CaseSearchRequest(BaseModel):
    """Bounded case-search request; POST keeps source identifiers out of URL logs."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    search: StrictStr | None = Field(default=None, max_length=256)
    patient_id: StrictStr | None = Field(default=None, min_length=1, max_length=64)
    status: StrictStr | None = Field(default=None, max_length=30)
    statuses: list[
        Literal[
            "PENDING",
            "ANALYZED",
            "PARTIALLY_REVIEWED",
            "REVIEWED",
            "SIGNED_PRELIM",
            "APPROVED",
            "LOCKED",
        ]
    ] | None = Field(default=None, max_length=10)
    date: StrictStr | None = Field(default=None, max_length=20)
    limit: StrictInt = Field(default=100, ge=1, le=100)
    offset: StrictInt = Field(default=0, ge=0)
    sort: Literal["study_code", "status", "study_date", "created_at"] = "created_at"
    direction: Literal["asc", "desc"] = "desc"


class CreateCaseRequest(BaseModel):
    """Case intake contract; reject unknown fields instead of silently dropping them."""

    model_config = ConfigDict(extra="forbid")

    patient_id: StrictStr | None = Field(default=None, min_length=9, max_length=64, pattern=r"^([0-9]{9}|DEMO-SYNTHETIC-[A-Za-z0-9-]+)$")
    patient_directory_id: StrictStr | None = Field(default=None, min_length=1, max_length=36)
    study_code: str | None = Field(default=None, max_length=64)
    study_date: StrictStr
    patient_age: str | None = Field(default=None, max_length=20)
    clinical_notes: str | None = None
    probe_type: str | None = Field(default=None, max_length=50)
    active_ovary_side: Literal["RIGHT", "LEFT", "BOTH", "UNKNOWN"] = "UNKNOWN"
    contralateral_status: Literal["UNKNOWN", "NOT_VISUALIZED", "SURGICALLY_ABSENT", "NORMAL", "SUSPECTED"] = "UNKNOWN"
    facility_id: str | None = Field(default=None, max_length=64)

    @field_validator("study_code", "patient_age", "probe_type", mode="before")
    @classmethod
    def normalize_optional_metadata(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("patient_id")
    @classmethod
    def validate_patient_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        trimmed = v.strip() if isinstance(v, str) else ""
        if not trimmed:
            return None
        if len(trimmed) > 64:
            raise ValueError("Mã định danh bệnh nhân (PID) không được vượt quá 64 ký tự.")
        return trimmed

    @field_validator("study_date")
    @classmethod
    def validate_study_date(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Ngày khảo sát không được để trống. Vui lòng cung cấp định dạng YYYY-MM-DD hoặc YYYY-MM-DDTHH:MM.")
        try:
            if "T" in trimmed:
                parsed = datetime.fromisoformat(trimmed.replace("Z", "+00:00"))
                if len(trimmed) > 10:
                    return parsed.strftime("%Y-%m-%d %H:%M")
                return parsed.strftime("%Y-%m-%d")
            if " " in trimmed:
                parsed = datetime.strptime(trimmed, "%Y-%m-%d %H:%M")
                return parsed.strftime("%Y-%m-%d %H:%M")
            parsed = datetime.strptime(trimmed, "%Y-%m-%d")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Ngày khám '{v}' không đúng định dạng YYYY-MM-DD hoặc YYYY-MM-DDTHH:MM hợp lệ.")


class PatientDirectoryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: StrictStr = Field(min_length=1, max_length=120)
    birth_year: StrictInt | None = Field(default=None, ge=1900, le=2100)

    @field_validator("birth_year")
    @classmethod
    def validate_birth_year_not_in_future(cls, value: int | None) -> int | None:
        if value is not None and value > datetime.now().year:
            raise ValueError("Năm sinh không thể ở tương lai.")
        return value


class PatientDirectoryUpdateRequest(PatientDirectoryCreateRequest):
    expected_version: StrictInt = Field(ge=1)


class PatientDirectoryItem(BaseModel):
    id: str
    display_name: str
    birth_year: int | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class CaseIntakeSidesRequest(BaseModel):
    """Complete laterality on an explicitly reserved, image-free examination."""

    model_config = ConfigDict(extra="forbid")
    active_ovary_side: Literal["RIGHT", "LEFT", "BOTH"]
    contralateral_status: Literal["UNKNOWN", "NOT_VISUALIZED", "SURGICALLY_ABSENT", "NORMAL", "SUSPECTED"] = "UNKNOWN"


class CaseImageSummary(BaseModel):
    id: str
    filename: str
    laterality: str | None = None


class CaseItem(BaseModel):
    id: str
    study_id: str | None = None
    study_code: str
    visit_no: VisitNumber | None = None
    patient_id: str | None = None
    patient_directory_id: str | None = None
    patient_name: str | None = None
    patient_age: str | None = None
    study_date: str
    status: str  # PENDING, ANALYZED, REVIEWED
    ovary_side: str = "UNKNOWN"
    contralateral_status: str = "UNKNOWN"
    images: list[CaseImageSummary] = Field(default_factory=list)
    image_id: str | None = None
    image_filename: str | None = None
    lesion_type: str | None = None
    max_diameter_mm: float | None = None
    doctor_action: str | None = None
    created_at: str


class WorkspaceCaseSearchResponse(BaseModel):
    items: list[CaseItem] = Field(default_factory=list)
    total: int


WorkspaceCaseSearchResult = WorkspaceCaseSearchResponse


class CaseCreateResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    study_id: str
    study_code: str
    visit_no: VisitNumber | None = None
    patient_id: str | None = None
    patient_directory_id: str | None = None
    patient_name: str | None = None
    patient_age: str | None = None
    study_date: str | None = None
    status: str | None = None
    ovary_side: str | None = None
    contralateral_status: str | None = None
    message: str


class CaseDetailImagePrediction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    ai_diagnosis: dict[str, Any] | None = None
    prediction_id: str
    confidence_score: float | None = None
    inference_time_ms: float | None = None
    iqa_score: float | None = None
    measurements: dict[str, Any] = Field(default_factory=dict)
    rle_mask: Any = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    model_version: str | None = None
    uncertainty_map_base64: str | None = None


class CaseDetailImageReview(BaseModel):
    model_config = ConfigDict(extra="ignore")
    review_id: str
    prediction_id: str | None = None
    doctor_id: str | None = None
    doctor_action: str | None = None
    time_spent_seconds: float | None = None
    lesion_type: str | None = None
    orads: Any = None
    orads_score: Any = None
    morphology_description: str | None = None
    clinical_notes: str | None = None
    hitl_feedback: dict[str, Any] = Field(default_factory=dict)
    reviewed_at: str | None = None
    reviewer_id: str | None = None
    max_diameter_mm: float | None = None
    ortho_diameter_mm: float | None = None
    total_area_cm2: float | None = None
    verified_mask_rle: Any = None
    created_at: str | None = None


class CaseDetailImage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    image_id: str
    laterality: str | None = None
    filename: str | None = None
    width: int | None = None
    height: int | None = None
    pixel_spacing_mm: float | None = None
    calibration_source: str | None = None
    is_calibrated: bool | None = None
    calibration_confidence: float | None = None
    prediction: CaseDetailImagePrediction | None = None
    review: CaseDetailImageReview | None = None


class CaseDetailResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    study_id: str
    study_code: str | None = None
    visit_no: VisitNumber | None = None
    patient_id: str | None = None
    patient_directory_id: str | None = None
    patient_name: str | None = None
    report_header: str | None = None
    patient_age: str | None = None
    study_date: str | None = None
    status: str | None = None
    review_revision: int = 0
    correction_id: str | None = None
    correction_by: str | None = None
    correction_status: str | None = None
    correction_reason: str | None = None
    correction_revision: int | None = None
    correction_draft: dict[str, Any] | None = None
    latest_review_request_id: str | None = None
    ovary_side: str | None = None
    contralateral_status: str | None = None
    probe_type: str | None = None
    clinical_indication: str | None = None
    images: list[CaseDetailImage] = Field(default_factory=list)
    created_at: str


class ImageValidationResult(BaseModel):
    is_acceptable: bool
    status_text: str
    iqa_score: float
    details: list[dict[str, Any]]
    message: str


class ADNEXInputs(BaseModel):
    """Explicit clinician inputs for an unvalidated, research-only ADNEX run."""

    model_config = ConfigDict(extra="forbid", strict=True)

    model_variant: Literal["WITH_CA125", "WITHOUT_CA125"] | None = None
    age_years: StrictInt | StrictFloat | None = None
    ca125_u_ml: StrictInt | StrictFloat | None = None
    is_oncology_center: StrictBool | None = None
    is_persistent_adnexal_mass: StrictBool | None = None
    surgery_indicated: StrictBool | None = None
    assessment_source: Literal["clinician"] | None = None
    modality: Literal["ultrasound_2d"] | None = None
    ultrasound_exam_complete: StrictBool | None = None
    max_lesion_diameter_mm: StrictInt | StrictFloat | None = None
    largest_solid_component_mm: StrictInt | StrictFloat | None = None
    cyst_locules_count: StrictInt | None = None
    papillary_projections_count: StrictInt | None = None
    acoustic_shadowing: StrictBool | None = None
    has_ascites: StrictBool | None = None
    physiologic_follicle_confirmed: StrictBool | None = None


class CDSSEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vision_findings: dict[str, Any] | None = None
    patient_context: dict[str, Any] | None = None
    adnex_inputs: ADNEXInputs | None = None


class RegionCaliperWriteRequest(BaseModel):
    """Source-image caliper points explicitly attached to one persisted region snapshot."""

    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: StrictStr = Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
    expected_revision: StrictInt = Field(ge=0)
    assignment_request_id: StrictStr = Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
    review_id: StrictStr = Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
    region_id: StrictStr = Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
    mask_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    label: Literal["D1", "D2"]
    points: list[list[StrictInt | StrictFloat]] = Field(min_length=2, max_length=2)
    coordinate_space: Literal["decoded-source-image"] = "decoded-source-image"
    lease_token: str = Field(min_length=32, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")
    page_instance_id: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("points")
    @classmethod
    def validate_source_points(cls, points):
        if len(points) != 2 or any(len(point) != 2 for point in points):
            raise ValueError("Caliper requires two finite non-negative source-image points.")

        normalized_points = []
        for point in points:
            normalized_point = []
            for value in point:
                if isinstance(value, bool) or value < 0:
                    raise ValueError("Caliper requires two finite non-negative source-image points.")
                try:
                    numeric_value = float(value)
                except (OverflowError, TypeError, ValueError) as exc:
                    raise ValueError(
                        "Caliper requires two finite non-negative source-image points."
                    ) from exc
                if not math.isfinite(numeric_value):
                    raise ValueError("Caliper requires two finite non-negative source-image points.")
                normalized_point.append(numeric_value)
            normalized_points.append(normalized_point)

        if normalized_points[0] == normalized_points[1]:
            raise ValueError("Caliper endpoints must be different.")
        return normalized_points


class RegionCDSSAssessmentRequest(BaseModel):
    """Persist one explicit RUO assessment against a confirmed region and source review."""

    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: StrictStr = Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
    expected_assessment_revision: StrictInt = Field(ge=0)
    assignment_request_id: StrictStr = Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
    review_id: StrictStr = Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
    region_id: StrictStr = Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
    mask_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmed: StrictBool
    vision_findings: dict[str, Any] = Field(default_factory=dict, max_length=64)
    patient_context: dict[str, Any] = Field(default_factory=dict, max_length=24)
    source_caliper_event_id: StrictStr | None = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$",
    )
    lease_token: str = Field(min_length=32, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")
    page_instance_id: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")

    @model_validator(mode="after")
    def validate_explicit_source(self):
        if not self.confirmed:
            raise ValueError("A clinician must confirm the descriptors before saving the RUO assessment.")
        source = self.vision_findings.get("assessment_source")
        if source not in (None, "clinician"):
            raise ValueError("Only explicitly clinician-entered descriptors are accepted.")

        for field_name in ("max_diameter_mm", "ortho_diameter_mm"):
            value = self.vision_findings.get(field_name)
            if value is None:
                continue
            if type(value) not in (int, float):
                raise ValueError(f"{field_name} must be a finite numeric measurement.")
            try:
                finite_value = math.isfinite(float(value))
            except (OverflowError, TypeError, ValueError):
                finite_value = False
            if not finite_value:
                raise ValueError(f"{field_name} must be a finite numeric measurement.")

        try:
            serialized = json.dumps(
                {"vision_findings": self.vision_findings, "patient_context": self.patient_context},
                sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("Assessment descriptors must be finite bounded JSON.") from exc
        if len(serialized) > 16_384:
            raise ValueError("Assessment descriptors must not exceed 16384 UTF-8 bytes.")

        allowed_patient_context = {
            "is_premenopausal", "is_persistent_adnexal_mass", "surgery_indicated",
        }
        if set(self.patient_context) - allowed_patient_context:
            raise ValueError("Unsupported patient-context fields are not persisted.")
        if any(type(value) is not bool for value in self.patient_context.values()):
            raise ValueError("Patient-context values must be explicit clinician-confirmed booleans.")

        from backend.services.cdss_engine import IOTA_B_FEATURES, IOTA_M_FEATURES, VISION_FINDING_FIELDS

        if set(self.vision_findings) - VISION_FINDING_FIELDS:
            raise ValueError("Unsupported vision descriptor fields are not persisted.")
        iota_features = self.vision_findings.get("iota_simple_rules")
        if iota_features is not None and (
            not isinstance(iota_features, dict)
            or set(iota_features) - set(IOTA_B_FEATURES + IOTA_M_FEATURES)
            or any(type(value) is not bool for value in iota_features.values())
        ):
            raise ValueError("IOTA descriptors must contain recognized features with explicit booleans.")
        return self


class CaseConfirmRequest(DoctorReviewRequest):
    image_id: str
    study_id: str | None = None
    prediction_id: str
    doctor_id: str = "UNVERIFIED_REVIEWER"
    doctor_action: Literal["ACCEPTED_RAW", "MODIFIED", "REJECTED_ALL"] = "ACCEPTED_RAW"
    verified_mask_rle: dict[str, Any]
    lesion_type: str = Field(default="UNSPECIFIED", max_length=100)
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


class SegmentationCandidateRequest(BaseModel):
    """Explicit parameters for a non-persistent research mask candidate."""

    model_config = ConfigDict(extra="forbid", strict=True)

    study_id: StrictStr = Field(min_length=1, max_length=36)
    image_id: StrictStr = Field(min_length=1, max_length=36)
    prediction_id: StrictStr = Field(min_length=1, max_length=36)
    min_component_area: StrictInt = Field(ge=0, le=262144)
    closing_kernel_size: StrictInt = Field(ge=0, le=31)
    fill_holes: StrictBool
    smoothing_kernel_size: StrictInt | None

    @field_validator("study_id", "image_id", "prediction_id")
    @classmethod
    def reject_blank_identifiers(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Identifiers must not be blank")
        return value

    @model_validator(mode="after")
    def validate_kernel_sizes(self):
        if self.closing_kernel_size != 0 and (
            self.closing_kernel_size < 3 or self.closing_kernel_size % 2 == 0
        ):
            raise ValueError("closing_kernel_size must be 0 or an odd value from 3 to 31")
        if self.smoothing_kernel_size is not None and (
            self.smoothing_kernel_size < 3
            or self.smoothing_kernel_size > 31
            or self.smoothing_kernel_size % 2 == 0
        ):
            raise ValueError("smoothing_kernel_size must be null or an odd value from 3 to 31")
        return self


class SegmentationCandidateParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    min_component_area: StrictInt
    closing_kernel_size: StrictInt
    fill_holes: StrictBool
    smoothing_kernel_size: StrictInt | None


class SegmentationCandidateProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    prediction_id: StrictStr
    model_version: StrictStr | None
    checkpoint_sha256: StrictStr | None
    algorithm: Literal["explicit_morphology_candidate"]
    algorithm_version: Literal["1.0.0"]


class SegmentationCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    success: Literal[True] = True
    baseline_mask_rle: dict[str, Any]
    candidate_mask_rle: dict[str, Any]
    candidate_parameters: SegmentationCandidateParameters
    provenance: SegmentationCandidateProvenance


class FeatureEstimate(BaseModel):
    model_config = ConfigDict(extra="allow")

    value: Any = None
    source: Literal["ai_estimated", "clinician_entered", "clinician_confirmed", "unavailable", "not_applicable", "not_evaluated"] = "unavailable"
    confidence: float | None = None


class AIDiagnosisFindings(BaseModel):
    model_config = ConfigDict(extra="allow")

    lesion_type: dict[str, Any] | None = None
    malignancy_risk: dict[str, Any] | None = None
    features: dict[str, FeatureEstimate] = Field(default_factory=dict)
    orads_suggested: dict[str, Any] = Field(
        default_factory=lambda: {"category": None, "complete": False, "missing": []}
    )
    pcos_suggestion: dict[str, Any] | None = None
    abstain: bool = False
    abstain_reason: str | None = None


class UnifiedCaseFindingsResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    study_id: str
    side: Literal["left", "right"]
    pixel_spacing_mm: float | None = None
    ovary: dict[str, Any] = Field(default_factory=dict)
    follicles: dict[str, Any] = Field(default_factory=dict)
    lesion: dict[str, Any] = Field(default_factory=dict)
    ai_diagnosis: AIDiagnosisFindings | None = None
    review_status: Literal["PENDING", "ACCEPTED_RAW", "MODIFIED", "REJECTED_ALL"] = "PENDING"
    clinician_overrides: dict[str, Any] = Field(default_factory=dict)


class InteractivePromptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    image_id: str
    box: list[int] = Field(..., min_length=4, max_length=4)
    point_prompts: list[list[int]] | None = None
    pixel_spacing_mm: float | None = None

    @field_validator("box")
    @classmethod
    def validate_box_coords(cls, v: list[int]) -> list[int]:
        x1, y1, x2, y2 = v
        if not (0 <= x1 < x2 <= 512 and 0 <= y1 < y2 <= 512):
            raise ValueError("Box coordinates must satisfy 0 <= x1 < x2 <= 512 and 0 <= y1 < y2 <= 512")
        if (x2 - x1) < 8 or (y2 - y1) < 8:
            raise ValueError("Box width and height must each be at least 8 pixels.")
        return v


class InteractivePromptResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    success: bool = True
    image_id: str
    box: list[int]
    mask_rle: dict[str, Any]
    measurements: dict[str, Any]
    message: str = "Tạo mặt nạ tương tác thành công từ Bounding Box."


class ApplyClinicalTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(..., min_length=1, max_length=100)
    max_diameter_mm: float | None = Field(default=None, ge=0.0, le=500.0)
    patient_context: dict[str, Any] | None = None


class ApplyClinicalTemplateResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    template_id: str
    label: str
    badge: str
    recommendation: str | None = None
    status: str
    findings: dict[str, Any]
    cdss_result: dict[str, Any]


class VisitCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str | None = None
    facility_id: str | None = None
    study_id: str | None = None
    status: str = Field(default="ACTIVE", pattern="^(ACTIVE|COMPLETED|LOCKED)$")


class VisitStudySummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    study_date: str
    status: str
    ovary_side: str
    images_count: int = 0


class VisitResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    visit_code: str
    facility_id: str | None = None
    patient_id: str | None = None
    status: str
    is_locked: bool
    created_at: datetime
    updated_at: datetime
    studies: list[VisitStudySummary] = []


class VisitListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    items: list[VisitResponse]
    total: int
    page: int
    page_size: int


class FacilityCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facility_code: str = Field(..., min_length=2, max_length=32)
    name: str = Field(..., min_length=2, max_length=128)
    config: dict[str, Any] | None = None


class FacilityResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    facility_code: str
    name: str
    is_active: bool
    created_at: datetime


class CaseAssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignee_id: str = Field(..., min_length=1, max_length=36)


class CaseClaimResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    study_id: str
    assignee_id: str


class CorrectionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    technician_id: str = Field(..., min_length=1, max_length=36)
    reason: str = Field(..., min_length=1, max_length=1000)


class CorrectionSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correction_id: str = Field(..., min_length=1, max_length=36)
    base_revision: StrictInt = Field(ge=0)
    lease_token: str = Field(min_length=32, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")
    page_instance_id: str = Field(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    draft_payload: dict[str, Any]

    @field_validator("draft_payload")
    @classmethod
    def validate_correction_draft(cls, value: dict[str, Any]) -> dict[str, Any]:
        if set(value) != {"images"} or not isinstance(value.get("images"), list):
            raise ValueError("Correction draft must contain only an images list.")
        image_rows = value["images"]
        if not image_rows or len(image_rows) > 20:
            raise ValueError("Correction draft must contain between 1 and 20 images.")
        seen_ids: set[str] = set()
        for row in image_rows:
            if not isinstance(row, dict) or set(row) - {"image_id", "verified_mask_rle", "notes", "morphology"}:
                raise ValueError("Correction image fields are not recognized.")
            image_id = row.get("image_id")
            if not isinstance(image_id, str) or not image_id or image_id in seen_ids:
                raise ValueError("Correction image IDs must be unique non-empty strings.")
            seen_ids.add(image_id)
            mask = row.get("verified_mask_rle")
            if not isinstance(mask, dict):
                raise ValueError("Each correction image requires a binary mask.")
            DoctorReviewRequest.validate_mask_rle(mask)
            if not isinstance(row.get("notes", ""), str) or len(row.get("notes", "")) > 10000:
                raise ValueError("Correction notes exceed the allowed size.")
            if not isinstance(row.get("morphology", ""), str) or len(row.get("morphology", "")) > 1000:
                raise ValueError("Correction morphology exceeds the allowed size.")
        return value


class NotificationResponseItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    recipient_id: str
    facility_id: str | None = None
    study_id: str | None = None
    case_id: str | None = None
    event_type: str
    title: str
    message: str
    is_read: bool = False
    read_at: str | None = None
    created_at: str


class NotificationListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    items: list[NotificationResponseItem]
    total: int


class CDSSMultiLesionEvaluateRequest(BaseModel):
    lesions: list[dict[str, Any]]
    patient_context: dict[str, Any] | None = None
    adnex_inputs: ADNEXInputs | None = None
