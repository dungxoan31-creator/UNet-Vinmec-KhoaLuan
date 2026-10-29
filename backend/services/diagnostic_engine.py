"""
Diagnostic Reasoning Engine for Autonomous Ovarian Ultrasound Evaluation (Branch D).
- D1: 8-class MMOTU pathology mapping and malignancy risk assessment.
- D2: Autonomous estimation of O-RADS / IOTA ultrasound morphologic features.
- D3: PCOS morphology assessment (Rotterdam & Monash/ESHRE/ASRM criteria).
- D4: Probability calibration and fail-closed Abstain logic.
"""

import math
from typing import Any

import numpy as np

LESION_VI_MAP = {
    "simple_cyst": "Nang đơn giản",
    "chocolate_cyst": "Nang lạc nội mạc tử cung (Chocolate cyst)",
    "serous_cystadenoma": "U nang tuyến thanh dịch",
    "mucinous_cystadenoma": "U nang tuyến nhầy",
    "teratoma": "U quái (Dermoid cyst)",
    "theca_cell_tumor": "U tế bào vỏ (Thecoma)",
    "high_grade_serous_cystadenocarcinoma": "Ung thư biểu mô tuyến thanh dịch độ cao",
    "normal_ovary": "Buồng trứng bình thường",
}

ORADS_FEATURE_NAMES = (
    "locules",
    "solid_component",
    "papillary_projections",
    "acoustic_shadowing",
    "fluid_echogenicity",
    "color_score",
    "ascites",
)


class DiagnosticReasoningEngine:
    def __init__(self, min_top1_conf: float = 0.60, min_margin: float = 0.15):
        self.min_top1_conf = min_top1_conf
        self.min_margin = min_margin

    def fuse_and_evaluate(
        self,
        lesion_probs: dict[str, float],
        estimated_features: dict[str, dict[str, Any]],
        ood_score: float | None = None,
        ood_threshold: float = 1.0,
        pcos_suggestion: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Synthesizes 8-class probabilities, morphological features, and Abstain criteria.
        """
        estimated_features = estimated_features if isinstance(estimated_features, dict) else {}
        if not isinstance(lesion_probs, dict) or not lesion_probs:
            return {
                "lesion_type": None,
                "malignancy_risk": None,
                "features": estimated_features,
                "orads_suggested": {
                    "category": None,
                    "complete": False,
                    "missing": list(ORADS_FEATURE_NAMES),
                },
                "pcos_suggestion": pcos_suggestion,
                "abstain": True,
                "abstain_reason": "Không có dữ liệu xác suất tổn thương",
            }

        total_probability = 0.0
        probabilities_valid = True
        for label, probability in lesion_probs.items():
            if label not in LESION_VI_MAP or isinstance(probability, bool) or not isinstance(probability, (int, float)):
                probabilities_valid = False
                break
            value = float(probability)
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                probabilities_valid = False
                break
            total_probability += value
        probabilities_valid = probabilities_valid and math.isclose(
            total_probability, 1.0, rel_tol=1e-3, abs_tol=1e-3
        )
        ood_valid = ood_score is None
        if ood_score is not None and not isinstance(ood_score, bool):
            try:
                if not isinstance(ood_score, (int, float, np.number)):
                    raise TypeError("OOD score must be numeric")
                normalized_ood = float(ood_score)
                ood_valid = math.isfinite(normalized_ood) and normalized_ood >= 0.0
                if ood_valid:
                    ood_score = normalized_ood
            except (TypeError, ValueError, OverflowError):
                ood_valid = False
        if not probabilities_valid or not ood_valid:
            invalid_reason = (
                "Xác suất đầu vào không hợp lệ hoặc dữ liệu bị lỗi (NaN/ngoài miền)"
                if not probabilities_valid
                else "Điểm ngoài miền đầu vào không hợp lệ hoặc dữ liệu bị lỗi (NaN/ngoài miền)"
            )
            return {
                "lesion_type": None,
                "malignancy_risk": None,
                "features": estimated_features,
                "orads_suggested": {"category": None, "complete": False, "missing": list(ORADS_FEATURE_NAMES)},
                "pcos_suggestion": pcos_suggestion,
                "abstain": True,
                "abstain_reason": invalid_reason,
            }

        ranked = sorted(lesion_probs.items(), key=lambda kv: kv[1], reverse=True)
        top_label, p1 = ranked[0]
        p2 = ranked[1][1] if len(ranked) > 1 else 0.0

        abstain = False
        abstain_reason = None

        if p1 < self.min_top1_conf:
            abstain = True
            abstain_reason = "Độ tin cậy phân loại của AI thấp (< 60%)"
        elif (p1 - p2) < self.min_margin:
            abstain = True
            abstain_reason = "Hai chẩn đoán có xác suất quá gần nhau, AI không thể phân định"
        elif ood_score is not None and ood_score > ood_threshold:
            abstain = True
            abstain_reason = "Ảnh có đặc trưng khác lạ so với dữ liệu huấn luyện (Out-of-Distribution)"

        missing_features = [
            feat_name
            for feat_name in ORADS_FEATURE_NAMES
            if feat_name not in estimated_features
            or estimated_features[feat_name].get("source") in {"unavailable", "not_applicable"}
            or estimated_features[feat_name].get("value") is None
        ]

        top3 = [
            [k, LESION_VI_MAP.get(k, k), round(float(p), 3)]
            for k, p in ranked[:3]
        ]

        return {
            "lesion_type": {
                "label": top_label,
                "label_vi": LESION_VI_MAP.get(top_label, top_label),
                "prob": round(float(p1), 3),
                "top3": top3,
            },
            "malignancy_risk": {
                "label": "UNAVAILABLE",
                "prob_malignant": None,
                "reason": "Chưa có bộ phân loại và ngưỡng nguy cơ ác tính được xác thực độc lập.",
            },
            "features": estimated_features,
            "orads_suggested": {
                "category": None,
                "complete": len(missing_features) == 0,
                "missing": missing_features,
            },
            "pcos_suggestion": pcos_suggestion,
            "abstain": abstain,
            "abstain_reason": abstain_reason,
        }

    def evaluate_pcos(
        self,
        follicle_count_in_range: int | None,
        ovarian_volume_ml: float | None = None,
        criterion: str = "eshre_asrm_2018_2023",
    ) -> dict[str, Any]:
        """
        Evaluates polycystic ovary morphology based on international clinical thresholds.
        """
        count_valid = type(follicle_count_in_range) is int and follicle_count_in_range >= 0
        normalized_volume = None
        volume_valid = False
        if ovarian_volume_ml is not None and not isinstance(ovarian_volume_ml, bool):
            if isinstance(ovarian_volume_ml, (int, float, np.number)):
                try:
                    candidate_volume = float(ovarian_volume_ml)
                    volume_valid = math.isfinite(candidate_volume) and candidate_volume >= 0.0
                    if volume_valid:
                        normalized_volume = candidate_volume
                except (TypeError, ValueError, OverflowError):
                    volume_valid = False
        if criterion == "rotterdam_2003":
            # Rotterdam: >= 12 follicles (2-9mm) or ovarian volume > 10 ml
            threshold = 12
            volume_positive = volume_valid and normalized_volume > 10.0
        else:
            # ESHRE/ASRM/Monash: >= 20 follicles (2-9mm) or volume >= 10 ml
            threshold = 20
            volume_positive = volume_valid and normalized_volume >= 10.0

        count_positive = count_valid and follicle_count_in_range >= threshold
        if count_positive or volume_positive:
            is_suggested = True
        elif count_valid and volume_valid:
            is_suggested = False
        else:
            is_suggested = None

        safe_count = follicle_count_in_range if count_valid else None
        safe_volume = normalized_volume if volume_valid else None

        return {
            "suggested": is_suggested,
            "label": (
                "PCOM_THRESHOLD_MET" if is_suggested is True
                else "PCOM_THRESHOLD_NOT_MET" if is_suggested is False
                else "INCOMPLETE_DATA"
            ),
            "criterion": criterion,
            "follicle_threshold": threshold,
            "count_in_range": safe_count,
            "ovarian_volume_ml": safe_volume,
        }

    def estimate_orads_features(
        self,
        img_gray: np.ndarray,
        binary_mask: np.ndarray,
        pixel_spacing_mm: float | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Heuristically extracts key O-RADS descriptors from ultrasound image and lesion mask.
        Marks Doppler and ascites as 'unavailable' on 2D B-mode images.
        """
        mask = (binary_mask > 0).astype(np.uint8)
        if mask.sum() == 0:
            return {
                "locules": {"value": None, "source": "not_applicable", "confidence": None},
                "solid_component": {"value": None, "source": "not_applicable", "confidence": None},
                "papillary_projections": {"value": None, "source": "not_applicable", "confidence": None},
                "acoustic_shadowing": {"value": None, "source": "not_applicable", "confidence": None},
                "fluid_echogenicity": {"value": None, "source": "not_applicable", "confidence": None},
                "color_score": {"value": None, "source": "unavailable", "confidence": None},
                "ascites": {"value": None, "source": "unavailable", "confidence": None},
            }

        # Grayscale intensity and a segmentation mask cannot validate O-RADS
        # descriptors such as solid tissue, ground-glass, shadowing, or locules.
        return {
            "locules": {"value": None, "source": "unavailable", "confidence": None},
            "solid_component": {"value": None, "source": "unavailable", "confidence": None},
            "papillary_projections": {"value": None, "source": "unavailable", "confidence": None},
            "acoustic_shadowing": {"value": None, "source": "unavailable", "confidence": None},
            "fluid_echogenicity": {"value": None, "source": "unavailable", "confidence": None},
            "color_score": {"value": None, "source": "unavailable", "confidence": None},
            "ascites": {"value": None, "source": "unavailable", "confidence": None},
        }
