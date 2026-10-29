import numpy as np
import pytest

from backend.services.diagnostic_engine import DiagnosticReasoningEngine


def test_fuse_and_evaluate_clear_benign():
    engine = DiagnosticReasoningEngine(min_top1_conf=0.60, min_margin=0.15)
    lesion_probs = {
        "serous_cystadenoma": 0.75,
        "simple_cyst": 0.15,
        "mucinous_cystadenoma": 0.05,
        "chocolate_cyst": 0.03,
        "teratoma": 0.01,
        "theca_cell_tumor": 0.005,
        "high_grade_serous_cystadenocarcinoma": 0.005,
        "normal_ovary": 0.0,
    }
    features = {
        "locules": {"value": 1, "source": "ai_estimated", "confidence": 0.85},
        "solid_component": {"value": False, "source": "ai_estimated", "confidence": 0.80},
        "color_score": {"value": None, "source": "unavailable", "confidence": None},
    }

    res = engine.fuse_and_evaluate(lesion_probs, features)
    assert res["abstain"] is False
    assert res["abstain_reason"] is None
    assert res["lesion_type"]["label"] == "serous_cystadenoma"
    assert res["lesion_type"]["prob"] == 0.75
    assert len(res["lesion_type"]["top3"]) == 3
    assert res["malignancy_risk"]["label"] == "UNAVAILABLE"
    assert res["malignancy_risk"]["prob_malignant"] is None
    assert res["malignancy_risk"]["reason"]
    assert res["orads_suggested"]["complete"] is False
    assert "color_score" in res["orads_suggested"]["missing"]


def test_fuse_and_evaluate_low_confidence_abstain():
    engine = DiagnosticReasoningEngine(min_top1_conf=0.60, min_margin=0.15)
    lesion_probs = {
        "serous_cystadenoma": 0.45,
        "simple_cyst": 0.25,
        "mucinous_cystadenoma": 0.15,
        "chocolate_cyst": 0.10,
        "teratoma": 0.02,
        "theca_cell_tumor": 0.01,
        "high_grade_serous_cystadenocarcinoma": 0.01,
        "normal_ovary": 0.01,
    }
    features = {}
    res = engine.fuse_and_evaluate(lesion_probs, features)
    assert res["abstain"] is True
    assert "thấp" in res["abstain_reason"].lower()


def test_fuse_and_evaluate_close_top2_abstain():
    engine = DiagnosticReasoningEngine(min_top1_conf=0.40, min_margin=0.15)
    lesion_probs = {
        "serous_cystadenoma": 0.42,
        "mucinous_cystadenoma": 0.38,
        "simple_cyst": 0.10,
        "chocolate_cyst": 0.05,
        "teratoma": 0.02,
        "theca_cell_tumor": 0.01,
        "high_grade_serous_cystadenocarcinoma": 0.01,
        "normal_ovary": 0.01,
    }
    features = {}
    res = engine.fuse_and_evaluate(lesion_probs, features)
    assert res["abstain"] is True
    assert "quá gần nhau" in res["abstain_reason"].lower()


def test_fuse_and_evaluate_ood_abstain():
    engine = DiagnosticReasoningEngine()
    lesion_probs = {
        "simple_cyst": 0.85,
        "serous_cystadenoma": 0.10,
        "normal_ovary": 0.05,
    }
    res = engine.fuse_and_evaluate(lesion_probs, {}, ood_score=1.5, ood_threshold=1.0)
    assert res["abstain"] is True
    assert "out-of-distribution" in res["abstain_reason"].lower()


@pytest.mark.parametrize("ood_score", [float("nan"), float("inf"), -0.1, "1.5"])
def test_invalid_ood_score_abstains_without_comparison_error(ood_score):
    probabilities = {"simple_cyst": 0.85, "serous_cystadenoma": 0.10, "normal_ovary": 0.05}
    result = DiagnosticReasoningEngine().fuse_and_evaluate(probabilities, {}, ood_score=ood_score)

    assert result["abstain"] is True
    assert result["malignancy_risk"] is None
    assert "không hợp lệ" in result["abstain_reason"]


def test_fuse_and_evaluate_malignancy_flag():
    engine = DiagnosticReasoningEngine()
    lesion_probs = {
        "high_grade_serous_cystadenocarcinoma": 0.65,
        "serous_cystadenoma": 0.20,
        "mucinous_cystadenoma": 0.15,
    }
    res = engine.fuse_and_evaluate(lesion_probs, {})
    assert res["malignancy_risk"]["label"] == "UNAVAILABLE"
    assert res["malignancy_risk"]["prob_malignant"] is None


@pytest.mark.parametrize("probabilities", [
    {"simple_cyst": float("nan")},
    {"simple_cyst": float("inf")},
    {"simple_cyst": -0.01, "normal_ovary": 1.01},
    {"unrecognized_pathology": 1.0},
    {"simple_cyst": 0.8},
])
def test_invalid_probability_vectors_abstain_without_benign_label(probabilities):
    result = DiagnosticReasoningEngine().fuse_and_evaluate(probabilities, {})

    assert result["abstain"] is True
    assert result["abstain_reason"] == "Xác suất đầu vào không hợp lệ hoặc dữ liệu bị lỗi (NaN/ngoài miền)"
    assert result["lesion_type"] is None
    assert result["malignancy_risk"] is None


def test_missing_follicle_data_does_not_create_negative_pcos_result():
    from backend.services.inference_engine import synthesize_multibranch_findings

    result = synthesize_multibranch_findings("study", "left")

    assert result["follicles"] is None
    assert result["ai_diagnosis"]["pcos_suggestion"] is None


def test_empty_mask_does_not_estimate_lesion_descriptors_or_confidence():
    engine = DiagnosticReasoningEngine()
    features = engine.estimate_orads_features(
        np.zeros((32, 32), dtype=np.uint8), np.zeros((32, 32), dtype=np.uint8)
    )

    for name in ("locules", "solid_component", "papillary_projections", "acoustic_shadowing", "fluid_echogenicity"):
        assert features[name]["value"] is None
        assert features[name]["source"] == "not_applicable"
        assert features[name]["confidence"] is None


def test_evaluate_pcos_rules():
    engine = DiagnosticReasoningEngine()
    # Rotterdam threshold >= 12
    res_rot = engine.evaluate_pcos(follicle_count_in_range=14, criterion="rotterdam_2003")
    assert res_rot["suggested"] is True
    assert res_rot["criterion"] == "rotterdam_2003"

    # ESHRE threshold >= 20
    res_eshre_below = engine.evaluate_pcos(follicle_count_in_range=14, criterion="eshre_asrm_2018_2023")
    assert res_eshre_below["suggested"] is None
    assert res_eshre_below["label"] == "INCOMPLETE_DATA"

    res_eshre_confirmed_below = engine.evaluate_pcos(
        follicle_count_in_range=14,
        ovarian_volume_ml=8.0,
        criterion="eshre_asrm_2018_2023",
    )
    assert res_eshre_confirmed_below["suggested"] is False

    res_eshre_above = engine.evaluate_pcos(follicle_count_in_range=22, criterion="eshre_asrm_2018_2023")
    assert res_eshre_above["suggested"] is True


def test_invalid_or_missing_pcos_measurements_do_not_become_negative():
    engine = DiagnosticReasoningEngine()

    invalid_count = engine.evaluate_pcos(follicle_count_in_range=-1, ovarian_volume_ml=5.0)
    invalid_volume = engine.evaluate_pcos(follicle_count_in_range=10, ovarian_volume_ml=float("nan"))

    assert invalid_count["suggested"] is None
    assert invalid_count["count_in_range"] is None
    assert invalid_volume["suggested"] is None
    assert invalid_volume["ovarian_volume_ml"] is None


def test_estimate_orads_features_grayscale_synthetic():
    engine = DiagnosticReasoningEngine()
    img = np.full((512, 512), 40, dtype=np.uint8)
    mask = np.zeros((512, 512), dtype=np.uint8)
    # Cystic area (dark, near 0)
    img[200:300, 200:300] = 5
    mask[200:300, 200:300] = 1

    features = engine.estimate_orads_features(img, mask)
    for name in ("locules", "solid_component", "papillary_projections", "acoustic_shadowing", "fluid_echogenicity"):
        assert features[name]["value"] is None
        assert features[name]["source"] == "unavailable"
    assert features["color_score"]["source"] == "unavailable"
    assert features["ascites"]["source"] == "unavailable"
