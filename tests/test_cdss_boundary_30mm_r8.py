"""Test suite for R8 (P2): 30 mm boundary condition in CDSS and report/inference context."""

import numpy as np
import pytest
import torch

from backend.services.cdss_engine import CDSSReasoningEngine, PHYSIOLOGIC_FOLLICLE_POLICY
from backend.services.inference_engine import InferenceEngine
from backend.services.report_generator import build_structured_findings_report, MedicalReportGenerator


def _follicle_case(diameter_mm: float) -> dict:
    return {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_diameter_mm": diameter_mm,
        "locules_count": 1,
        "has_solid_component": False,
        "papillary_projections_count": 0,
        "fluid_echogenicity": "anechoic",
        "acoustic_shadowing": False,
        "wall_irregular": False,
        "color_score": 1,
        "has_ascites": False,
        "has_peritoneal_nodules": False,
        "physiologic_lesion_type": "follicle",
        "physiologic_morphology_confirmed": True,
    }


def _simple_cyst_case(diameter_mm: float) -> dict:
    return {
        "assessment_source": "clinician",
        "modality": "ultrasound_2d",
        "ultrasound_exam_complete": True,
        "max_diameter_mm": diameter_mm,
        "locules_count": 1,
        "has_solid_component": False,
        "papillary_projections_count": 0,
        "fluid_echogenicity": "anechoic",
        "acoustic_shadowing": False,
        "wall_irregular": False,
        "color_score": 1,
        "has_ascites": False,
        "has_peritoneal_nodules": False,
    }


def test_follicle_boundary_29_9mm_matches_orads_1():
    engine = CDSSReasoningEngine()
    result = engine.evaluate_case(_follicle_case(29.9), {"is_premenopausal": True})
    assert result["status"] == "RULE_MATCHED"
    assert result["orads_stratification"]["category"] == "O-RADS 1"


def test_follicle_boundary_30_0mm_is_unclassified():
    engine = CDSSReasoningEngine()
    result = engine.evaluate_case(_follicle_case(30.0), {"is_premenopausal": True})
    assert result["status"] == "UNSUPPORTED_PATTERN"
    assert result["orads_stratification"]["category"] is None
    assert result["implementation_policy"]["version"] == "project-follicle-lt30-v3"
    assert result["implementation_policy"]["diameter_rule_mm"] == "0 < diameter < 30"


def test_boundary_30_1mm_evaluates_simple_cyst_without_dead_zone():
    engine = CDSSReasoningEngine()
    # At 30.1 mm, simple cyst descriptors should match O-RADS 2
    result = engine.evaluate_case(_simple_cyst_case(30.1), {"is_premenopausal": True})
    assert result["status"] == "RULE_MATCHED"
    assert result["orads_stratification"]["category"] == "O-RADS 2"


def test_simple_cyst_at_exactly_30mm_is_unclassified_under_project_policy():
    engine = CDSSReasoningEngine()
    result = engine.evaluate_case(_simple_cyst_case(30.0), {"is_premenopausal": True})
    assert result["status"] == "UNSUPPORTED_PATTERN"
    assert result["orads_stratification"]["category"] is None


class _DummyModel(torch.nn.Module):
    def __init__(self, logits_val: float = 0.0):
        super().__init__()
        self.logits_val = logits_val

    def forward(self, x):
        return torch.full((x.shape[0], 1, 512, 512), self.logits_val, dtype=torch.float32, device=x.device)


def test_inference_engine_predict_output_includes_mask_confidence_semantics():
    engine = InferenceEngine(architecture="standard_unet", device="cpu")
    engine.model = _DummyModel(logits_val=2.0)
    engine.is_model_ready = True
    dummy_input = torch.zeros((1, 1, 512, 512), dtype=torch.float32)
    dummy_gray = np.zeros((512, 512), dtype=np.uint8)

    output = engine.predict(dummy_input, dummy_gray)
    assert "mask_pixel_confidence" in output
    assert "confidence_score" in output
    assert output["mask_pixel_confidence"] == output["confidence_score"]
    assert output.get("score_type") == "mean_mask_pixel_probability_uncalibrated"


def test_report_generator_contains_mask_confidence_clarification():
    # Verify structured report text includes the clarification
    report_text = build_structured_findings_report({})
    expected_clause = "Độ tin cậy U-Net đo chất lượng đường viền phân đoạn pixel; không phải xác suất ác tính (malignancy probability)."
    assert expected_clause in report_text

    # Verify PDF generator normalized data includes the clarification
    generator = MedicalReportGenerator()
    norm = generator._normalize_report_data({"patientId": "PID-TEST"})
    assert norm.get("cdss_explanation") == expected_clause
