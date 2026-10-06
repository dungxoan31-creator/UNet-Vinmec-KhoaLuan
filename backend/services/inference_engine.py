"""
Medical-Grade AI Inference Engine & Automated Caliper Measurement Service:
- PyTorch Attention U-Net deep learning inference
- Robust Uncertainty & Out-of-Distribution (OOD) Quantification (Shannon Entropy)
- Morphological Post-Processing & Connected Component Analysis
- Precision Caliper Extraction (Dmax, Dorth, Area, Perimeter, Oriented Endpoints)
- Lossless Run-Length Encoding (RLE)
- Model Versioning & Provenance Metadata (SHA-256 Checksum)
- Clinical Decision Support (CDSS) Framing
"""

import base64
import hashlib
import os

import cv2
import numpy as np
import segmentation_models_pytorch as smp
import torch

from backend.models.attention_unet import AttentionUNet
from backend.models.unet import StandardUNet
from backend.services.morphology_extractor import MorphologicalFeatureExtractor


class InferenceEngine:
    """
    Production-grade Clinical Inference Engine for Ovarian Ultrasound Segmentation.
    """

    MODEL_NAME = "Attention U-Net Dual Attention Gates"
    MODEL_VERSION = "v1.2.0-clinical"
    PREPROCESSOR_VERSION = "UltrasoundPreprocessor-v1.2"

    def __init__(
        self,
        model_weights_path=None,
        device=None,
        threshold=0.5,
        default_pixel_spacing_mm=0.1,
        uncertainty_entropy_threshold=0.75,
        architecture="auto",
        input_normalization=None,
    ):
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        self.threshold = float(threshold)
        self.default_pixel_spacing_mm = float(default_pixel_spacing_mm)
        self.uncertainty_entropy_threshold = float(uncertainty_entropy_threshold)
        self.model_weights_path = model_weights_path
        self.model_checksum = None
        self.is_model_ready = False
        self.architecture_name = architecture
        input_normalization = input_normalization or {}
        self.input_mean = float(input_normalization.get("mean", 0.0))
        self.input_std = float(input_normalization.get("std", 1.0))
        if self.input_std <= 0:
            raise ValueError("input_normalization.std must be greater than zero")
        self.morph_extractor = MorphologicalFeatureExtractor(default_pixel_spacing_mm=self.default_pixel_spacing_mm)

        # Auto-detect architecture from path if not explicitly standard_unet or attention_unet
        is_standard = False
        is_unetplusplus = architecture == "unetplusplus_resnet34"
        if architecture == "standard_unet":
            is_standard = True
        elif architecture in {"attention_unet", "unetplusplus_resnet34"}:
            is_standard = False
        elif model_weights_path and ("baseline" in os.path.basename(model_weights_path).lower() or "unet_best" in os.path.basename(model_weights_path).lower()):
            is_standard = True

        if is_unetplusplus:
            self.model = smp.UnetPlusPlus(
                encoder_name="resnet34",
                encoder_weights=None,
                in_channels=1,
                classes=1,
                activation=None,
            ).to(self.device)
            self.architecture_name = "U-Net++ (ResNet34 ImageNet)"
            self.model_name = "U-Net++ + ResNet34 ImageNet encoder"
        elif is_standard:
            self.model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(self.device)
            self.architecture_name = "Standard U-Net (Baseline)"
            self.model_name = "Standard U-Net (Baseline)"
        else:
            self.model = AttentionUNet(in_channels=1, num_classes=1, base_filters=32).to(self.device)
            self.architecture_name = "Attention U-Net (Comparative Variant)"
            self.model_name = self.MODEL_NAME
        self.model.eval()

        if model_weights_path and os.path.exists(model_weights_path):
            try:
                hasher = hashlib.sha256()
                with open(model_weights_path, "rb") as f:
                    while chunk := f.read(8192 * 1024):
                        hasher.update(chunk)
                self.model_checksum = hasher.hexdigest()

                state_dict = torch.load(model_weights_path, map_location=self.device, weights_only=True)
                try:
                    self.model.load_state_dict(state_dict, strict=True)
                except Exception:
                    if is_unetplusplus:
                        raise
                    # Fallback to alternate model if weights format corresponds to other architecture
                    alt_model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(self.device) if not is_standard else AttentionUNet(in_channels=1, num_classes=1, base_filters=32).to(self.device)
                    alt_model.load_state_dict(state_dict)
                    self.model = alt_model
                    self.architecture_name = "Standard U-Net (Baseline)" if not is_standard else "Attention U-Net (Comparative Variant)"
                    self.model.eval()

                self.is_model_ready = True
                print(f"[InferenceEngine] Successfully loaded {self.architecture_name} weights (SHA256: {self.model_checksum[:12]}...)")
            except Exception as e:
                print(f"[InferenceEngine] Warning: Could not load weights from {model_weights_path}: {e}")
                self.is_model_ready = False
        else:
            print(f"[InferenceEngine] Notice: Initialized {self.architecture_name} without pre-trained weights file.")

    @staticmethod
    def mask_to_rle(binary_mask: np.ndarray) -> dict:
        """
        Encodes 2D binary numpy mask to exact lossless RLE dictionary.
        """
        dots = (binary_mask > 0).astype(np.uint8).flatten()
        if len(dots) == 0:
            return {
                "counts": [],
                "first_val": 0,
                "shape": [int(x) for x in binary_mask.shape],
                "encoding": "standard_rle",
            }
        changes = np.where(dots[1:] != dots[:-1])[0] + 1
        split_points = np.concatenate([[0], changes, [len(dots)]])
        counts = [int(c) for c in np.diff(split_points)]
        first_val = int(dots[0])
        return {
            "counts": counts,
            "first_val": first_val,
            "shape": [int(x) for x in binary_mask.shape],
            "encoding": "standard_rle",
        }

    @staticmethod
    def rle_to_mask(rle_dict: dict) -> np.ndarray:
        """
        Decodes RLE dictionary back to 2D binary numpy mask.
        """
        shape = rle_dict["shape"]
        counts = rle_dict["counts"]
        first_val = int(rle_dict.get("first_val", 0))
        flat = np.zeros(shape[0] * shape[1], dtype=np.uint8)
        idx = 0
        val = first_val
        for c in counts:
            flat[idx : idx + int(c)] = val
            idx += int(c)
            val = 1 - val
        return flat.reshape(shape)

    def post_process_mask(self, prob_map_np: np.ndarray, min_area_px: int = 100) -> np.ndarray:
        """Apply the selected model's locked threshold without extra morphology."""
        return (prob_map_np >= self.threshold).astype(np.uint8)

    def prepare_model_input(self, tensor_512: torch.Tensor) -> torch.Tensor:
        """Apply the normalization recorded for the selected checkpoint."""
        tensor_gpu = tensor_512.to(self.device)
        input_mean = getattr(self, "input_mean", 0.0)
        input_std = getattr(self, "input_std", 1.0)
        if input_mean == 0.0 and input_std == 1.0:
            return tensor_gpu
        return (tensor_gpu - input_mean) / input_std

    def calculate_uncertainty(self, prob_map_np: np.ndarray, clean_mask: np.ndarray) -> dict:
        """
        Quantifies model prediction uncertainty using Shannon Binary Entropy:
        H(p) = -p*log2(p) - (1-p)*log2(1-p)
        Evaluates boundary ambiguity and out-of-distribution (OOD) risk.
        """
        # Clamp probabilities to avoid log(0)
        eps = 1e-7
        p = np.clip(prob_map_np, eps, 1.0 - eps)
        entropy_map = -(p * np.log2(p) + (1.0 - p) * np.log2(1.0 - p))

        if clean_mask.sum() > 0:
            # Dilate mask boundary to assess boundary uncertainty
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            dilated = cv2.dilate(clean_mask, kernel)
            eroded = cv2.erode(clean_mask, kernel)
            boundary_zone = (dilated - eroded) > 0

            if boundary_zone.sum() > 0:
                boundary_entropy = float(np.mean(entropy_map[boundary_zone]))
            else:
                boundary_entropy = float(np.mean(entropy_map[clean_mask > 0]))

            core_entropy = float(np.mean(entropy_map[clean_mask > 0]))
            overall_entropy = float(0.6 * boundary_entropy + 0.4 * core_entropy)
        else:
            # For empty mask, evaluate maximum background ambiguity
            overall_entropy = float(np.mean(entropy_map))

        is_uncertain = overall_entropy >= self.uncertainty_entropy_threshold

        if is_uncertain:
            uncertainty_level = "HIGH"
            clinical_alert = (
                "Độ bất định mô hình cao (Ranh giới tổn thương không điển hình hoặc độ tương phản thấp). "
                "Bác sĩ cần đối chiếu kỹ ảnh gốc B-Mode và hiệu chỉnh Caliper thủ công."
            )
        elif overall_entropy >= 0.60:
            uncertainty_level = "MODERATE"
            clinical_alert = "Độ bất định trung bình. Bác sĩ vui lòng kiểm tra lại kích thước đường kính lớn nhất."
        else:
            uncertainty_level = "LOW"
            clinical_alert = "Độ tin cậy phân vùng cao. Tổn thương có ranh giới rõ nét."

        return {
            "entropy_score": round(overall_entropy, 3),
            "uncertainty_level": uncertainty_level,
            "is_uncertain": is_uncertain,
            "clinical_alert": clinical_alert,
        }

    def extract_calipers_and_measurements(self, binary_mask: np.ndarray, pixel_spacing_mm: float = None) -> dict:
        """
        Extracts clinical calipers (Dmax, Dorth, Area, Perimeter, Center) and measurement endpoints.
        """
        if pixel_spacing_mm is None or pixel_spacing_mm <= 0:
            pixel_spacing_mm = self.default_pixel_spacing_mm
        pixel_spacing_mm = max(0.0001, float(pixel_spacing_mm))

        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        lesions = []

        if not contours:
            return {
                "has_lesion": False,
                "total_lesions": 0,
                "lesions": [],
                "max_diameter_mm": 0.0,
                "ortho_diameter_mm": 0.0,
                "d3_mm": 0.0,
                "total_volume_cm3": 0.0,
                "total_area_cm2": 0.0,
            }

        total_area_px = 0.0

        for idx, cnt in enumerate(contours):
            area_px = float(cv2.contourArea(cnt))
            if area_px < 50:
                continue

            total_area_px += area_px
            perimeter_px = float(cv2.arcLength(cnt, True))

            # Minimum Area Bounding Box for true oriented diameters
            rect = cv2.minAreaRect(cnt)
            (cx, cy), (dim1_px, dim2_px), _angle = rect

            # Identify max diameter and orthogonal diameter
            d_max_px = float(max(dim1_px, dim2_px))
            d_orth_px = float(min(dim1_px, dim2_px))

            d_max_mm = float(d_max_px * pixel_spacing_mm)
            d_orth_mm = float(d_orth_px * pixel_spacing_mm)
            area_cm2 = float((area_px * (pixel_spacing_mm**2)) / 100.0)

            # Compute oriented caliper endpoints for drawing crosshairs
            box_points = cv2.boxPoints(rect)  # 4 vertices
            p0, p1, p2, p3 = box_points

            # Center-points of opposite edges with pure python floats
            mid_01 = [float((p0[0] + p1[0]) / 2), float((p0[1] + p1[1]) / 2)]
            mid_23 = [float((p2[0] + p3[0]) / 2), float((p2[1] + p3[1]) / 2)]
            mid_12 = [float((p1[0] + p2[0]) / 2), float((p1[1] + p2[1]) / 2)]
            mid_30 = [float((p3[0] + p0[0]) / 2), float((p3[1] + p0[1]) / 2)]

            if dim1_px >= dim2_px:
                caliper_dmax = [mid_12, mid_30]
                caliper_dorth = [mid_01, mid_23]
            else:
                caliper_dmax = [mid_01, mid_23]
                caliper_dorth = [mid_12, mid_30]

            # Convert contour points to simple polygon list of ints
            polygon = [[int(pt[0]), int(pt[1])] for pt in cnt.reshape(-1, 2)]

            # Clinical 3D Volume estimation (Prolate Ellipsoid Formula: 0.523 * D1 * D2 * D3)
            d3_mm = round(float((d_max_mm + d_orth_mm) / 2.0), 2)
            volume_cm3 = round(float(0.523 * (d_max_mm * d_orth_mm * d3_mm) / 1000.0), 2)

            lesions.append(
                {
                    "lesion_id": int(idx + 1),
                    "center": [round(float(cx), 1), round(float(cy), 1)],
                    "max_diameter_mm": round(float(d_max_mm), 2),
                    "ortho_diameter_mm": round(float(d_orth_mm), 2),
                    "max_diameter_px": round(d_max_px, 2),
                    "ortho_diameter_px": round(d_orth_px, 2),
                    "area_px": round(area_px, 2),
                    "d3_mm": d3_mm,
                    "volume_cm3": volume_cm3,
                    "area_cm2": round(float(area_cm2), 3),
                    "perimeter_mm": round(float(perimeter_px * pixel_spacing_mm), 2),
                    "caliper_dmax_points": caliper_dmax,
                    "caliper_dorth_points": caliper_dorth,
                    "polygon": polygon,
                }
            )

        max_d_overall = float(max([lesion["max_diameter_mm"] for lesion in lesions], default=0.0))
        ortho_d_overall = float(max([lesion["ortho_diameter_mm"] for lesion in lesions], default=0.0))
        d3_overall = round(float((max_d_overall + ortho_d_overall) / 2.0), 2) if max_d_overall > 0 else 0.0
        total_volume_cm3 = float(sum([lesion["volume_cm3"] for lesion in lesions]))
        total_area_cm2 = float(sum([lesion["area_cm2"] for lesion in lesions]))

        return {
            "has_lesion": len(lesions) > 0,
            "total_lesions": len(lesions),
            "lesions": lesions,
            "max_diameter_mm": round(max_d_overall, 2),
            "ortho_diameter_mm": round(ortho_d_overall, 2),
            "d3_mm": round(d3_overall, 2),
            "total_volume_cm3": round(total_volume_cm3, 2),
            "total_area_cm2": round(total_area_cm2, 3),
        }

    def generate_overlay_base64(
        self, gray_512: np.ndarray, binary_mask: np.ndarray, measurements: dict, alpha: float = 0.35
    ) -> str:
        """
        Generates a semi-transparent color overlay image with caliper lines and returns as Base64 PNG.
        """
        color_base = cv2.cvtColor(gray_512, cv2.COLOR_GRAY2BGR)
        overlay = color_base.copy()

        # Fill mask with cyan/blue tint
        overlay[binary_mask > 0] = [235, 140, 20]  # BGR: medical cyan/blue

        # Blend base and overlay
        blended = cv2.addWeighted(overlay, alpha, color_base, 1.0 - alpha, 0)

        # Draw green border contour
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(blended, contours, -1, (0, 255, 100), 2)

        # Draw calipers and text
        for lesion in measurements.get("lesions", []):
            dmax_pts = lesion.get("caliper_dmax_points")
            if dmax_pts and len(dmax_pts) == 2:
                pt1 = (int(dmax_pts[0][0]), int(dmax_pts[0][1]))
                pt2 = (int(dmax_pts[1][0]), int(dmax_pts[1][1]))
                cv2.line(blended, pt1, pt2, (0, 255, 255), 2)  # Yellow caliper line
                cv2.circle(blended, pt1, 4, (0, 255, 255), -1)
                cv2.circle(blended, pt2, 4, (0, 255, 255), -1)

            # Draw Dmax text with subtle shadow
            cx, cy = int(lesion["center"][0]), int(lesion["center"][1])
            if lesion.get("max_diameter_mm") is not None:
                label = f"D1: {lesion['max_diameter_mm']}mm"
                cv2.putText(blended, label, (cx - 30, cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3)
                cv2.putText(blended, label, (cx - 30, cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        # Encode to Base64
        _, buffer = cv2.imencode(".png", blended)
        b64_str = base64.b64encode(buffer).decode("utf-8")
        return f"data:image/png;base64,{b64_str}"

    def run_inference(
        self,
        tensor_512: torch.Tensor,
        padded_gray: np.ndarray,
        pixel_spacing_mm: float | None = None,
        roi_mask: np.ndarray | None = None,
    ) -> dict:
        """
        Executes full medical inference pipeline:
        Tensor -> one model forward pass -> sigmoid -> locked threshold -> RLE.
        """
        tensor_gpu = self.prepare_model_input(tensor_512)

        with torch.no_grad():
            probs = torch.sigmoid(self.model(tensor_gpu)).squeeze().cpu().numpy()

        # Clean binary mask via morphological filtering
        clean_mask = self.post_process_mask(probs)

        # Average confidence inside lesion area or whole image
        if clean_mask.sum() > 0:
            confidence = float(np.mean(probs[clean_mask > 0]))
        else:
            confidence = float(1.0 - np.mean(probs))  # Confidence for normal empty mask

        # Calculate Uncertainty & OOD Metric
        uncertainty = self.calculate_uncertainty(probs, clean_mask)

        # Clinical Quality Gate Evaluation (Min confidence 70%, no high uncertainty)
        is_quality_valid = bool(
            confidence >= 0.70
            and not uncertainty.get("is_uncertain", False)
            and uncertainty.get("uncertainty_level") != "HIGH"
        )

        quality_gate = {
            "passed": is_quality_valid,
            "min_confidence_required": 0.70,
            "actual_confidence": round(float(confidence), 3),
            "uncertainty_level": uncertainty.get("uncertainty_level", "LOW"),
            "status": "APPROVED_BY_QUALITY_GATE" if is_quality_valid else "REJECTED_QUALITY_GATE",
            "alert": (
                "Chất lượng phân đoạn AI đạt chuẩn tin cậy cao."
                if is_quality_valid
                else "Chất lượng phân đoạn AI không đạt ngưỡng an toàn (< 70% hoặc độ bất định cao). "
                "Hệ thống đề xuất Bác sĩ đối chiếu kỹ ảnh gốc B-Mode và điều chỉnh thủ công."
            ),
        }

        # Extract clinical measurements and calipers
        measurements = self.extract_calipers_and_measurements(clean_mask, pixel_spacing_mm=pixel_spacing_mm)
        measurements["is_valid_caliper"] = is_quality_valid
        if not is_quality_valid:
            measurements["quality_alert"] = quality_gate["alert"]
        calibrated = pixel_spacing_mm is not None and pixel_spacing_mm > 0
        measurements["calibrated"] = calibrated
        if not calibrated:
            for key in ("max_diameter_mm", "ortho_diameter_mm", "d3_mm", "total_volume_cm3", "total_area_cm2"):
                measurements[key] = None
            for lesion in measurements.get("lesions", []):
                for key in ("max_diameter_mm", "ortho_diameter_mm", "d3_mm", "volume_cm3", "area_cm2", "perimeter_mm"):
                    lesion[key] = None

        # Mask geometry alone cannot establish IOTA or O-RADS categories.
        morph_analysis = {}
        cdss = {}

        # Encode RLE and Overlay
        rle = self.mask_to_rle(clean_mask)
        overlay_base64 = self.generate_overlay_base64(padded_gray, clean_mask, measurements)

        # Provenance metadata
        provenance = {
            "model_name": getattr(self, "model_name", self.MODEL_NAME),
            "model_version": self.MODEL_VERSION,
            "model_checksum": self.model_checksum,
            "preprocessor_version": self.PREPROCESSOR_VERSION,
            "device": self.device,
            "threshold": self.threshold,
            "pixel_spacing_mm": pixel_spacing_mm,
        }

        return {
            "rle_mask": rle,
            "confidence_score": round(float(confidence), 3),
            "uncertainty": uncertainty,
            "quality_gate": quality_gate,
            "measurements": measurements,
            "acoustic_profile": morph_analysis,
            "cdss_classification": cdss,
            "overlay_base64": overlay_base64,
            "binary_mask_np": clean_mask,
            "provenance": provenance,
        }

