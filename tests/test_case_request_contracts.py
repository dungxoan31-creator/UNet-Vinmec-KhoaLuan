import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import app
from backend.schemas.schemas import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    BatchReviewRequest,
    CaseConfirmRequest,
    CaseLeaseReleaseRequest,
    CaseLeaseRequest,
    CreateCaseRequest,
    DoctorReviewRequest,
    EmailVerificationRequest,
    ForgotPasswordRequest,
    HITLSessionRequest,
    MaskMeasurementsRequest,
    NotificationReadRequest,
    ResearchExportRequest,
    ResendEmailVerificationRequest,
    ResetPasswordRequest,
)


@pytest.mark.parametrize(
    ("field", "limit"),
    [("study_code", 64), ("patient_age", 20), ("probe_type", 50)],
)
def test_optional_case_metadata_matches_persisted_column_lengths(field, limit):
    value = "x" * limit
    case = CreateCaseRequest(patient_id="PID-LENGTH", study_date="2026-10-21", **{field: value})
    assert getattr(case, field) == value

    with pytest.raises(ValidationError):
        CreateCaseRequest(patient_id="PID-LENGTH", study_date="2026-10-21", **{field: value + "x"})


def test_whitespace_only_optional_case_metadata_is_normalized_to_none():
    case = CreateCaseRequest(
        patient_id="PID-LENGTH",
        study_date="2026-10-21",
        study_code="  ",
        patient_age="  ",
        probe_type="  ",
    )
    assert (case.study_code, case.patient_age, case.probe_type) == (None, None, None)


@pytest.mark.parametrize("request_model", [DoctorReviewRequest, CaseConfirmRequest])
def test_review_lesion_type_matches_persisted_column_length(request_model):
    accepted = request_model.model_validate(_review_payload(lesion_type="x" * 100))
    assert accepted.lesion_type == "x" * 100

    with pytest.raises(ValidationError):
        request_model.model_validate(_review_payload(lesion_type="x" * 101))


@pytest.mark.parametrize(
    "request_model",
    [
        ForgotPasswordRequest,
        ResetPasswordRequest,
        AdminCreateUserRequest,
        AdminUpdateUserRequest,
    ],
)
def test_username_request_lengths_match_persisted_user_column(request_model):
    accepted = request_model.model_validate({"username": "u" * 50})
    assert accepted.username == "u" * 50

    with pytest.raises(ValidationError):
        request_model.model_validate({"username": "u" * 51})


def test_case_request_rejects_non_string_study_date():
    with pytest.raises(ValidationError):
        CreateCaseRequest(patient_id="PID-CONTRACT", study_date=20261021)


def test_case_request_accepts_datetime_local_format():
    case_dt = CreateCaseRequest(patient_id="PID-DATETIME", study_date="2026-10-25T18:24")
    assert case_dt.study_date == "2026-10-25 18:24"

    case_d = CreateCaseRequest(patient_id="PID-DATEONLY", study_date="2026-10-25")
    assert case_d.study_date == "2026-10-25"



@pytest.mark.parametrize("unknown_field", ["patinet_age", "patient_name", "visit_no"])
def test_case_request_rejects_fields_outside_the_api_contract(unknown_field):
    with pytest.raises(ValidationError):
        CreateCaseRequest.model_validate(
            {"patient_id": "PID-CONTRACT", "study_date": "2026-10-21", unknown_field: "unexpected"}
        )


def test_create_case_endpoint_returns_422_for_unknown_request_fields(doctor_access):
    with TestClient(app) as client:
        response = client.post(
            "/api/cases",
            json={"patient_id": "PID-CONTRACT", "study_date": "2026-10-21", "patient_name": "unexpected"},
        )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (NotificationReadRequest, {"ids": []}),
        (EmailVerificationRequest, {"email": "doctor@example.org", "code": "123456"}),
        (ResendEmailVerificationRequest, {"email": "doctor@example.org"}),
        (CaseLeaseRequest, {"tab_id": "t" * 16, "page_instance_id": "p" * 16}),
        (CaseLeaseReleaseRequest, {"lease_token": "l" * 32, "page_instance_id": "p" * 16}),
        (
            DoctorReviewRequest,
            {
                "image_id": "image-1",
                "prediction_id": "prediction-1",
                "verified_mask_rle": {
                    "shape": [512, 512],
                    "counts": [512 * 512],
                    "first_val": 0,
                },
            },
        ),
        (
            BatchReviewRequest,
            {
                "study_id": "study-1",
                "expected_revision": 0,
                "request_id": "r" * 36,
                "reviews": [
                    {
                        "image_id": "image-1",
                        "prediction_id": "prediction-1",
                        "verified_mask_rle": {
                            "shape": [512, 512],
                            "counts": [512 * 512],
                            "first_val": 0,
                        },
                    }
                ],
            },
        ),
        (
            ResearchExportRequest,
            {"review_ids": ["review-1"], "expected_revision": 0, "ethics_approval_code": "IRB-1"},
        ),
        (HITLSessionRequest, {"study_id": "study-1", "participant_code": "participant-1"}),
        (
            MaskMeasurementsRequest,
            {"rle_mask": {"shape": [512, 512], "counts": [512 * 512], "first_val": 0}},
        ),
    ],
)
def test_request_models_reject_unknown_fields(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate({**payload, "unexpected_field": "untrusted"})


def test_review_rejects_unknown_keys_inside_mask_rle():
    with pytest.raises(ValidationError, match="RLE fields"):
        DoctorReviewRequest.model_validate(
            _review_payload(
                verified_mask_rle={
                    "shape": [512, 512],
                    "counts": [512 * 512],
                    "first_val": 0,
                    "unexpected_field": "untrusted",
                }
            )
        )


def test_review_accepts_the_frontend_standard_rle_encoding():
    review = DoctorReviewRequest.model_validate(
        _review_payload(
            verified_mask_rle={
                "shape": [512, 512],
                "counts": [512 * 512],
                "first_val": 0,
                "encoding": "standard_rle",
            }
        )
    )

    assert review.verified_mask_rle["encoding"] == "standard_rle"


def test_review_feedback_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        DoctorReviewRequest.model_validate(
            _review_payload(
                hitl_feedback={
                    "usability_rating": 5,
                    "issues": ["NO_ERROR"],
                    "free_text": "unexpected",
                }
            )
        )


@pytest.mark.parametrize(
    ("field", "limit"), [("anonymized_pid", 64), ("patient_age", 20)]
)
def test_upload_form_rejects_values_exceeding_patient_column_lengths(
    doctor_access, field, limit
):
    data = {field: "x" * (limit + 1)}
    with TestClient(app) as client:
        response = client.post(
            "/api/upload",
            data=data,
            files={"file": ("image.png", b"unused", "image/png")},
        )
    assert response.status_code == 422


def _review_payload(**updates):
    return {
        "image_id": "image-1",
        "prediction_id": "prediction-1",
        "verified_mask_rle": {
            "shape": [512, 512],
            "counts": [512 * 512],
            "first_val": 0,
        },
        **updates,
    }


def _batch_review_payload(request_id):
    return {
        "study_id": "study-1",
        "expected_revision": 0,
        "request_id": request_id,
        "reviews": [_review_payload()],
    }


@pytest.mark.parametrize("value", ["", "  ", "\t\r\n", "x" * 37, 123, True])
def test_single_review_request_id_is_nonempty_strict_and_limited(value):
    with pytest.raises(ValidationError):
        DoctorReviewRequest.model_validate(_review_payload(request_id=value))


@pytest.mark.parametrize("value", ["", "  ", "\t\r\n", "x" * 37, 123, True])
def test_batch_review_request_id_is_nonempty_strict_and_limited(value):
    with pytest.raises(ValidationError):
        BatchReviewRequest.model_validate(_batch_review_payload(value))


def test_review_request_ids_trim_whitespace_and_allow_database_max_length():
    request_id = "x" * 36
    single = DoctorReviewRequest.model_validate(
        _review_payload(request_id=f" {request_id} ")
    )
    batch = BatchReviewRequest.model_validate(
        _batch_review_payload(f" {request_id} ")
    )

    assert single.request_id == batch.request_id == request_id


@pytest.mark.parametrize(
    "field", ["orads", "orads_score"]
)
@pytest.mark.parametrize(
    "value", [None, "", *(f"O-RADS {score}" for score in range(6))]
)
def test_review_contract_accepts_only_unclassified_or_standard_orads_values(field, value):
    review = DoctorReviewRequest.model_validate(_review_payload(**{field: value}))
    assert getattr(review, field) == value


@pytest.mark.parametrize("field", ["orads", "orads_score"])
@pytest.mark.parametrize("score", range(6))
def test_review_contract_normalizes_legacy_numeric_orads_strings(field, score):
    review = DoctorReviewRequest.model_validate(
        _review_payload(**{field: str(score)})
    )
    assert getattr(review, field) == f"O-RADS {score}"


@pytest.mark.parametrize("field", ["orads", "orads_score"])
@pytest.mark.parametrize("value", ["O-RADS 6", "malignant", " O-RADS 2", 2, True])
def test_review_contract_rejects_nonstandard_orads_values(field, value):
    with pytest.raises(ValidationError):
        DoctorReviewRequest.model_validate(_review_payload(**{field: value}))


def test_review_contract_rejects_conflicting_orads_aliases():
    with pytest.raises(ValidationError, match="must match"):
        DoctorReviewRequest.model_validate(
            _review_payload(orads="O-RADS 2", orads_score="O-RADS 5")
        )


def test_review_contract_compares_aliases_after_legacy_normalization():
    review = DoctorReviewRequest.model_validate(
        _review_payload(orads="2", orads_score="O-RADS 2")
    )
    assert review.orads == review.orads_score == "O-RADS 2"
