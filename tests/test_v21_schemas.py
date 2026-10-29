import pytest
from pydantic import ValidationError

from backend.schemas.schemas import (
    AIDiagnosisFindings,
    DoctorReviewRequest,
    FeatureEstimate,
    ManualCaliper,
    UnifiedCaseFindingsResponse,
)


def test_feature_estimate_validation():
    f = FeatureEstimate(value=1, source="ai_estimated", confidence=0.88)
    assert f.value == 1
    assert f.source == "ai_estimated"
    assert f.confidence == 0.88

    f_unavail = FeatureEstimate(value=None, source="unavailable", confidence=None)
    assert f_unavail.source == "unavailable"

    with pytest.raises(ValidationError):
        FeatureEstimate(value=1, source="invalid_source")


def test_ai_diagnosis_findings_schema():
    diag = AIDiagnosisFindings(
        lesion_type={"label": "serous_cystadenoma", "prob": 0.75},
        malignancy_risk={"label": "BENIGN", "prob_malignant": 0.02},
        features={
            "locules": FeatureEstimate(value=1, source="ai_estimated", confidence=0.85),
            "color_score": FeatureEstimate(value=None, source="unavailable"),
        },
        orads_suggested={"category": 2, "complete": False, "missing": ["color_score"]},
        abstain=False,
    )
    assert diag.abstain is False
    assert diag.lesion_type["label"] == "serous_cystadenoma"
    assert diag.features["locules"].confidence == 0.85


def test_unified_case_findings_response():
    resp = UnifiedCaseFindingsResponse(
        study_id="STUDY-123456",
        side="right",
        pixel_spacing_mm=0.15,
        ovary={"present": True, "area_px": 15000},
        follicles={"count": 8, "diameters_mm": [3.0, 4.5]},
        lesion={"present": True, "longest_diameter_mm": 25.4},
        ai_diagnosis=AIDiagnosisFindings(abstain=False),
        review_status="PENDING",
        clinician_overrides={},
    )
    assert resp.study_id == "STUDY-123456"
    assert resp.side == "right"
    assert resp.review_status == "PENDING"


def test_doctor_review_request_with_overrides():
    # Valid RLE 512x512
    valid_rle = {
        "shape": [512, 512],
        "counts": [512 * 512],
        "first_val": 0,
        "encoding": "standard_rle",
    }
    req = DoctorReviewRequest(
        image_id="img-001",
        prediction_id="pred-001",
        doctor_id="DOC-99",
        doctor_action="MODIFIED",
        verified_mask_rle=valid_rle,
        lesion_type="serous_cystadenoma",
        clinician_overrides={
            "lesion_type": "mucinous_cystadenoma",
            "locules": 3,
        },
    )
    assert req.clinician_overrides["lesion_type"] == "mucinous_cystadenoma"
    assert req.clinician_overrides["locules"] == 3


def test_manual_caliper_contract_is_bounded_and_uses_source_image_coordinates():
    valid = ManualCaliper(label="D1", points=[[1, 2], [31, 42]])
    assert valid.coordinate_space == "decoded-source-image"
    assert valid.points == [[1.0, 2.0], [31.0, 42.0]]

    for points in (
        [[1, 2], [1, 2]],
        [[-1, 2], [31, 42]],
        [[True, 2], [31, 42]],
        [[1, 2], [10**400, 42]],
        [[1, 2], [float("inf"), 42]],
        [[1, 2]],
    ):
        with pytest.raises(ValidationError):
            ManualCaliper(label="D1", points=points)

    rle = {"shape": [512, 512], "counts": [512 * 512], "first_val": 0}
    with pytest.raises(ValidationError):
        DoctorReviewRequest(
            image_id="img-001",
            prediction_id="pred-001",
            verified_mask_rle=rle,
            manual_calipers=[
                {"label": "D1", "points": [[1, 1], [10, 1]]},
                {"label": "D1", "points": [[1, 2], [10, 2]]},
            ],
        )
