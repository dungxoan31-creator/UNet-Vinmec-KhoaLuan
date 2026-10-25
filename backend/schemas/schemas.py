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


class AdminUpdateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    username: StrictStr | None = Field(default=None, max_length=50)
    full_name: StrictStr | None = Field(default=None, max_length=100)
    role: AdminRole | None = None
    department: StrictStr | None = Field(default=None, max_length=100)
    is_active: StrictBool | StrictStr | None = None

    @model_validator(mode="after")
    def reject_explicit_null_values(self):
        for field in ("full_name", "role", "department", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null when supplied")
        return self


class AdminResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_password: StrictStr | None = Field(default=None, max_length=256)


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

    hospital_name: StrictStr | None = Field(default=None, min_length=1, max_length=120)
    report_header: StrictStr | None = Field(default=None, min_length=1, max_length=200)
    unit: Literal["auto"] | None = None

    @model_validator(mode="after")
    def require_setting(self):
        fields = self.model_fields_set
        if not fields:
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
    uncertainty_map_base64: str | None = None
    uncertainty: dict[str, Any] | None = None
    quality_gate: dict[str, Any] | None = None

    provenance: dict[str, Any] | None = None
    timings: dict[str, Any] | None = None
    acoustic_profile: dict[str, Any] | None = None
    cdss_classification: dict[str, Any] | None = None
    clinical_disclaimer: str = (
        "Kết quả này chỉ phục vụ nghiên cứu (RUO), chưa được xác thực lâm sàng. "
        "Bác sĩ cần tự thẩm định kết quả trước khi sử dụng. Hệ thống hỗ trợ phân đoạn và đo lường; "
        "không đưa ra chẩn đoán hoặc phê duyệt báo cáo lâm sàng."
    )



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
    hospital: StrictStr = Field(default="Bệnh viện ĐKQT Vinmec Times City", max_length=100)


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
    department: str
    title: str
    hospital: str
    avatar: str
    is_active: bool


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
    consensus_rate_pct: float
    avg_review_seconds: float
    last_active: str


class CaseSearchRequest(BaseModel):
    """Bounded case-search request; POST keeps source identifiers out of URL logs."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    search: StrictStr | None = Field(default=None, max_length=256)
    status: StrictStr | None = Field(default=None, max_length=30)
    date: StrictStr | None = Field(default=None, max_length=20)
    limit: StrictInt = Field(default=100, ge=1, le=100)
    offset: StrictInt = Field(default=0, ge=0, le=10000)


class CreateCaseRequest(BaseModel):
    """Case intake contract; reject unknown fields instead of silently dropping them."""

    model_config = ConfigDict(extra="forbid")

    patient_id: str
    study_code: str | None = Field(default=None, max_length=64)
    study_date: StrictStr
    patient_age: str | None = Field(default=None, max_length=20)
    clinical_notes: str | None = None
    probe_type: str | None = Field(default=None, max_length=50)
    active_ovary_side: Literal["RIGHT", "LEFT", "BOTH", "UNKNOWN"] = "UNKNOWN"
    contralateral_status: Literal["UNKNOWN", "NOT_VISUALIZED", "NORMAL", "SUSPECTED"] = "UNKNOWN"

    @field_validator("study_code", "patient_age", "probe_type", mode="before")
    @classmethod
    def normalize_optional_metadata(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("patient_id")
    @classmethod
    def validate_patient_id(cls, v: str) -> str:
        trimmed = v.strip() if isinstance(v, str) else ""
        if not trimmed:
            raise ValueError("Mã định danh bệnh nhân (PID) không được để trống.")
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


class CaseItem(BaseModel):
    id: str
    study_code: str
    patient_id: str
    study_date: str
    status: str  # PENDING, ANALYZED, REVIEWED
    ovary_side: str = "UNKNOWN"
    contralateral_status: str = "UNKNOWN"
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
