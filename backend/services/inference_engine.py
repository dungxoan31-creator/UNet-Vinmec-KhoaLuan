"""
RUO inference and measurement service for research review:
- Manifest-selected PyTorch segmentation inference
- Uncertainty and out-of-distribution estimates
- Connected-component analysis and caliper measurements
- Lossless Run-Length Encoding (RLE)
- Model provenance metadata (SHA-256 checkpoint checksum)
- No autonomous clinical diagnosis
"""

import base64
import hashlib
import math
import os
import tempfile
import threading
import time

import cv2
import numpy as np
import segmentation_models_pytorch as smp
import torch

from backend.core.calibration import normalize_pixel_spacing
from backend.core.image_utils import MAX_DECODED_IMAGE_PIXELS
from backend.models.attention_unet import AttentionUNet
from backend.models.unet import StandardUNet


def _build_model(model_kind, device, decoder_attention_type=None):
    if model_kind in ("unetplusplus", "unetplusplus_scse"):
        model = smp.UnetPlusPlus(
            encoder_name="resnet34",
            encoder_weights=None,
            in_channels=1,
            classes=1,
            activation=None,
            decoder_attention_type=decoder_attention_type,
        )
    elif model_kind == "standard":
        model = StandardUNet(in_channels=1, num_classes=1, base_filters=32)
    else:
        model = AttentionUNet(in_channels=1, num_classes=1, base_filters=32)
    return model.to(device)


def _is_cuda_runtime_failure(error):
    cuda_oom = getattr(torch.cuda, "OutOfMemoryError", None)
    if cuda_oom is not None and isinstance(error, cuda_oom):
        return True
    if not isinstance(error, RuntimeError):
        return False
    message = str(error).lower()
    return any(marker in message for marker in ("cuda", "cudnn", "cublas", "out of memory", "gpu driver"))


def _load_verified_checkpoint(path, device, expected_checksum=None):
    """Hash a stable checkpoint snapshot and deserialize those exact bytes."""
    hasher = hashlib.sha256()
    with tempfile.SpooledTemporaryFile(max_size=64 * 1024 * 1024, mode="w+b") as snapshot:
        with open(path, "rb") as source:
            while chunk := source.read(8 * 1024 * 1024):
                hasher.update(chunk)
                snapshot.write(chunk)

        checksum = hasher.hexdigest()
        if expected_checksum is not None and checksum != expected_checksum:
            raise ValueError("Checkpoint SHA-256 does not match the selected model manifest.")

        snapshot.seek(0)
        state_dict = torch.load(snapshot, map_location=device, weights_only=True)
    return checksum, state_dict


class InferenceEngine:
    """
    Research-use inference engine for ovarian ultrasound segmentation.
    """

    MODEL_NAME = "Unspecified segmentation model"
    MODEL_VERSION = "unspecified"
    PREPROCESSOR_VERSION = "UltrasoundPreprocessor-v1.2"

    @staticmethod
    def encode_uncertainty_heatmap_png(probabilities: np.ndarray) -> bytes | None:
        """Encode uncalibrated binary entropy as an orange, alpha-blended RUO layer."""
        probability_map = np.asarray(probabilities)
        if probability_map.shape != (512, 512) or not np.isfinite(probability_map).all():
            return None

        p = np.clip(probability_map.astype(np.float32, copy=False), 1e-7, 1.0 - 1e-7)
        entropy = -(p * np.log2(p) + (1.0 - p) * np.log2(1.0 - p))
        alpha = np.rint(entropy * 255.0).astype(np.uint8)

        bgra = np.zeros((512, 512, 4), dtype=np.uint8)
        bgra[:, :, 1] = 128
        bgra[:, :, 2] = 255
        bgra[:, :, 3] = alpha
        try:
            success, buffer = cv2.imencode(".png", bgra)
        except cv2.error:
            return None
        return buffer.tobytes() if success and buffer is not None else None

    def __init__(
        self,
        model_weights_path=None,
        device=None,
        threshold=0.5,
        uncertainty_entropy_threshold=0.75,
        architecture="auto",
        input_normalization=None,
        horizontal_flip_tta=False,
        min_area_px=0,
        apply_morphology=False,
        expected_checkpoint_sha256=None,
        model_version=None,
        decoder_attention_type=None,
    ):
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        self.threshold = float(threshold)
        self.uncertainty_entropy_threshold = float(uncertainty_entropy_threshold)
        self.model_weights_path = model_weights_path
        self.expected_checkpoint_sha256 = expected_checkpoint_sha256
        self.min_area_px = int(min_area_px)
        self.apply_morphology = bool(apply_morphology)
        if model_version is not None and (not isinstance(model_version, str) or not model_version.strip()):
            raise ValueError("model_version must be a non-empty string when provided")
        self.model_version = model_version or self.MODEL_VERSION
        self.model_checksum = None
        self.is_model_ready = False
        self.device_fallback_reason = None
        self._device_condition = threading.Condition()
        self._active_cuda_inferences = 0
        self._device_transition = False
        self.architecture_name = architecture
        input_normalization = input_normalization or {}
        self.input_mean = float(input_normalization.get("mean", 0.0))
        self.input_std = float(input_normalization.get("std", 1.0))
        self.horizontal_flip_tta = bool(horizontal_flip_tta)
        if self.input_std <= 0:
            raise ValueError("input_normalization.std must be greater than zero")
        # Auto-detect architecture from path if not explicitly standard_unet or attention_unet
        is_standard = False
        is_unetplusplus = architecture in {
            "unetplusplus",
            "unetplusplus_resnet34",
            "unetplusplus_resnet34_scse",
            "unetplusplus_scse",
        }
        if architecture == "standard_unet":
            is_standard = True
        elif is_unetplusplus or architecture == "attention_unet":
            pass
        elif model_weights_path:
            lower_base = os.path.basename(model_weights_path).lower()
            if "unetplusplus" in lower_base or "resnet34" in lower_base:
                is_unetplusplus = True
            elif "baseline" in lower_base or "unet_best" in lower_base:
                is_standard = True

        self.decoder_attention_type = decoder_attention_type or (
            "scse" if "scse" in str(architecture).lower() else None
        )
        self.model_kind = "unetplusplus" if is_unetplusplus else ("standard" if is_standard else "attention")
        self.model = self._build_on_selected_device(self.model_kind, self.decoder_attention_type)
        self._set_model_identity(self.model_kind, self.decoder_attention_type)
        self.model.eval()

        if model_weights_path and os.path.exists(model_weights_path):
            try:
                self.model_checksum, state_dict = _load_verified_checkpoint(
                    model_weights_path,
                    device="cpu",
                    expected_checksum=self.expected_checkpoint_sha256,
                )
                if is_unetplusplus:
                    has_scse = any("attention.cSE" in k or "attention.sSE" in k for k in state_dict.keys())
                    target_attn = "scse" if has_scse else None
                    if target_attn != self.decoder_attention_type:
                        self.decoder_attention_type = target_attn
                        self.model = self._build_on_selected_device(self.model_kind, self.decoder_attention_type)
                        self._set_model_identity(self.model_kind, self.decoder_attention_type)
                        self.model.eval()
                try:
                    self.model.load_state_dict(state_dict, strict=True)
                except Exception as load_error:
                    if _is_cuda_runtime_failure(load_error) and self._is_cuda_device():
                        self._record_cpu_fallback(load_error)
                        try:
                            self.model = _build_model(self.model_kind, "cpu", decoder_attention_type=self.decoder_attention_type)
                        except TypeError:
                            self.model = _build_model(self.model_kind, "cpu")
                        try:
                            self.model.load_state_dict(state_dict, strict=True)
                            load_error = None
                        except Exception as cpu_load_error:
                            load_error = cpu_load_error

                    if load_error is not None and is_unetplusplus:
                        raise load_error

                    if load_error is not None:
                    # Fallback to alternate model if weights format corresponds to other architecture
                        alt_kind = "standard" if not is_standard else "attention"
                        alt_model = self._build_on_selected_device(alt_kind)
                        alt_model.load_state_dict(state_dict)
                        self.model = alt_model
                        self.model_kind = alt_kind
                        self._set_model_identity(alt_kind)
                    self.model.eval()

                self.is_model_ready = True
                print(f"[InferenceEngine] Successfully loaded {self.architecture_name} weights (SHA256: {self.model_checksum[:12]}...)")
            except Exception as e:
                print(f"[InferenceEngine] Warning: Could not load weights from {model_weights_path}: {e}")
                self.is_model_ready = False
        else:
            print(f"[InferenceEngine] Notice: Initialized {self.architecture_name} without pre-trained weights file.")

    def _is_cuda_device(self):
        return torch.device(self.device).type == "cuda"

    def _record_cpu_fallback(self, reason):
        self.device_fallback_reason = str(reason)
        self.device = "cpu"
        print(f"[InferenceEngine] CUDA failed; continuing on CPU: {self.device_fallback_reason}")

    def _build_on_selected_device(self, model_kind, decoder_attention_type=None):
        try:
            if decoder_attention_type is not None:
                return _build_model(model_kind, self.device, decoder_attention_type=decoder_attention_type)
            return _build_model(model_kind, self.device)
        except TypeError:
            return _build_model(model_kind, self.device)
        except Exception as exc:
            if not self._is_cuda_device():
                raise
            self._record_cpu_fallback(exc)
            if decoder_attention_type is not None:
                try:
                    return _build_model(model_kind, "cpu", decoder_attention_type=decoder_attention_type)
                except TypeError:
                    return _build_model(model_kind, "cpu")
            return _build_model(model_kind, "cpu")

    def _set_model_identity(self, model_kind, decoder_attention_type=None):
        if model_kind in ("unetplusplus", "unetplusplus_scse"):
            if decoder_attention_type == "scse":
                self.architecture_name = "U-Net++ (ResNet34 ImageNet + scSE Attention)"
                self.model_name = "U-Net++ + ResNet34 ImageNet encoder + scSE attention"
            else:
                self.architecture_name = "U-Net++ (ResNet34 ImageNet)"
                self.model_name = "U-Net++ + ResNet34 ImageNet encoder"
        elif model_kind == "standard":
            self.architecture_name = "Standard U-Net (Baseline)"
            self.model_name = "Standard U-Net (Baseline)"
        else:
            self.architecture_name = "Attention U-Net (Comparative Variant)"
            self.model_name = self.MODEL_NAME

    def _begin_forward(self):
        condition = getattr(self, "_device_condition", None)
        if condition is None:
            if self._is_cuda_device():
                raise RuntimeError("CUDA inference coordination is not initialized")
            if getattr(self, "is_model_ready", None) is False:
                raise RuntimeError("Inference engine model is not ready or unloaded")
            return False

        with condition:
            while self._device_transition:
                condition.wait()
            if not self.is_model_ready:
                raise RuntimeError("Inference engine model is not ready or unloaded")
            use_cuda = self._is_cuda_device()
            if use_cuda:
                self._active_cuda_inferences += 1
            return use_cuda

    def _end_cuda_forward(self):
        with self._device_condition:
            self._active_cuda_inferences -= 1
            if self._active_cuda_inferences == 0:
                self._device_condition.notify_all()

    def _switch_to_cpu_after_cuda_error(self, reason):
        with self._device_condition:
            while self._device_transition:
                self._device_condition.wait()
            if not self._is_cuda_device():
                return

            self._device_transition = True
            try:
                while self._active_cuda_inferences:
                    self._device_condition.wait()
                try:
                    self.model = self.model.to("cpu")
                except Exception:
                    self.is_model_ready = False
                    raise
                self._record_cpu_fallback(reason)
                try:
                    torch.cuda.empty_cache()
                except Exception:
                    pass
            finally:
                self._device_transition = False
                self._device_condition.notify_all()

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
        Validate and decode a bounded 2D binary RLE mask.
        """
        if not isinstance(rle_dict, dict):
            raise ValueError("RLE mask must be an object.")
        shape = rle_dict.get("shape")
        counts = rle_dict.get("counts")
        first_val = rle_dict.get("first_val", 0)
        encoding = rle_dict.get("encoding")
        if (
            not isinstance(shape, (list, tuple))
            or len(shape) != 2
            or any(type(dimension) is not int or dimension < 0 for dimension in shape)
            or type(first_val) is not int
            or first_val not in (0, 1)
            or ("encoding" in rle_dict and encoding != "standard_rle")
        ):
            raise ValueError("RLE mask header is invalid.")

        height, width = shape
        if max(height, width) > MAX_DECODED_IMAGE_PIXELS:
            raise ValueError("RLE mask dimension exceeds the decoded pixel limit.")
        pixel_count = height * width
        if pixel_count > MAX_DECODED_IMAGE_PIXELS:
            raise ValueError("RLE mask exceeds the decoded pixel limit.")
        if pixel_count == 0:
            if counts != [] or first_val != 0:
                raise ValueError("Empty RLE mask encoding is invalid.")
            return np.zeros((height, width), dtype=np.uint8)
        if (
            not isinstance(counts, list)
            or not counts
            or len(counts) > pixel_count
            or any(type(count) is not int or count <= 0 for count in counts)
            or sum(counts) != pixel_count
        ):
            raise ValueError("RLE counts must be positive and cover the full mask.")

        flat = np.empty(pixel_count, dtype=np.uint8)
        idx = 0
        val = first_val
        for c in counts:
            end = idx + c
            flat[idx:end] = val
            idx = end
            val = 1 - val
        return flat.reshape(shape)

    def post_process_mask(
        self,
        prob_map_np: np.ndarray,
        min_area_px: int | None = None,
        apply_morphology: bool | None = None,
        morph_kernel_size: int = 3,
    ) -> np.ndarray:
        """
        Apply the selected model's locked threshold.
        Optionally removes spurious noise speckles (< min_area_px) and closes micro-holes.
        Preserves clinical safety: If all components fall below min_area_px,
        retains the largest component so faint lesions are never lost.
        """
        min_area = getattr(self, "min_area_px", 0) if min_area_px is None else int(min_area_px)
        do_morph = getattr(self, "apply_morphology", False) if apply_morphology is None else bool(apply_morphology)

        binary = (prob_map_np >= self.threshold).astype(np.uint8)
        if binary.sum() == 0:
            return binary

        if do_morph and min(binary.shape) >= morph_kernel_size:
            kernel = getattr(self, f'_morph_kernel_{morph_kernel_size}', None)
            if kernel is None:
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (morph_kernel_size, morph_kernel_size))
                setattr(self, f'_morph_kernel_{morph_kernel_size}', kernel)
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        if min_area > 0 and binary.sum() > 0:
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
            if num_labels > 1:
                keep = np.zeros(num_labels, dtype=np.uint8)
                valid_mask = stats[1:, cv2.CC_STAT_AREA] >= min_area
                if np.any(valid_mask):
                    keep[1:][valid_mask] = 1
                else:
                    largest_idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
                    keep[largest_idx] = 1
                binary = keep[labels]

        return binary

    def prepare_model_input(self, tensor_512: torch.Tensor) -> torch.Tensor:
        """Apply the normalization recorded for the selected checkpoint."""
        tensor_gpu = tensor_512.to(self.device)
        input_mean = getattr(self, "input_mean", 0.0)
        input_std = getattr(self, "input_std", 1.0)
        if input_mean == 0.0 and input_std == 1.0:
            return tensor_gpu
        return (tensor_gpu - input_mean) / input_std

    def forward_probabilities(self, tensor_512: torch.Tensor) -> np.ndarray:
        """Return probabilities, optionally averaging native and horizontal-flip predictions."""
        use_cuda = self._begin_forward()
        try:
            try:
                return self._forward_probabilities_on_current_device(tensor_512)
            except Exception as exc:
                if not use_cuda or not _is_cuda_runtime_failure(exc):
                    raise
                self._end_cuda_forward()
                use_cuda = False
                self._switch_to_cpu_after_cuda_error(exc)
                return self._forward_probabilities_on_current_device(tensor_512)
        finally:
            if use_cuda:
                self._end_cuda_forward()
                if torch.cuda.is_available() and self._is_cuda_device():
                    try:
                        torch.cuda.empty_cache()
                    except Exception:
                        pass

    def _forward_probabilities_on_current_device(self, tensor_512: torch.Tensor) -> np.ndarray:
        tensor_gpu = self.prepare_model_input(tensor_512)
        if torch.cuda.is_available() and self._is_cuda_device():
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        with torch.inference_mode():
            if getattr(self, "horizontal_flip_tta", False):
                device_type = torch.device(self.device).type
                with torch.amp.autocast(device_type="cuda", enabled=device_type == "cuda"):
                    native_logits = self.model(tensor_gpu)
                    flipped_logits = self.model(torch.flip(tensor_gpu, dims=(-1,)))
                    native = self._sigmoid_finite_logits(native_logits)
                    flipped = self._sigmoid_finite_logits(flipped_logits)
                probs = ((native + torch.flip(flipped, dims=(-1,))) / 2).squeeze().cpu().numpy()
            else:
                logits = self.model(tensor_gpu)
                probs = self._sigmoid_finite_logits(logits).squeeze().cpu().numpy()
                del logits
        del tensor_gpu
        if torch.cuda.is_available() and self._is_cuda_device():
            torch.cuda.synchronize()
        t1 = time.perf_counter()
        self.last_forward_ms = (t1 - t0) * 1000.0
        if probs.size == 0:
            raise RuntimeError("Model inference produced an empty probability map.")
        if not np.isfinite(probs).all():
            raise RuntimeError("Model inference produced non-finite probabilities.")
        return probs

    @staticmethod
    def _sigmoid_finite_logits(logits: torch.Tensor) -> torch.Tensor:
        if logits.numel() == 0 or not torch.isfinite(logits).all().item():
            raise RuntimeError("Model inference produced empty or non-finite logits.")
        return torch.sigmoid(logits).float()

    def predict_binary(
        self,
        tensor_512: torch.Tensor,
        post_process: bool = False,
        min_area_px: int = 0,
        apply_morphology: bool = False,
    ) -> np.ndarray:
        """Shared binary mask inference helper for evaluation and serving."""
        probs = self.forward_probabilities(tensor_512)
        if post_process:
            return self.post_process_mask(
                probs,
                min_area_px=min_area_px,
                apply_morphology=apply_morphology,
            )
        return (probs >= self.threshold).astype(np.uint8)

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

    @staticmethod
    def _normalize_pixel_spacing(pixel_spacing_mm: float | None) -> float | None:
        return normalize_pixel_spacing(pixel_spacing_mm)

    def extract_calipers_and_measurements(self, binary_mask: np.ndarray, pixel_spacing_mm: float = None) -> dict:
        """
        Extracts clinical calipers (Dmax, Dorth, Area, Perimeter, Center) and measurement endpoints.
        """
        pixel_spacing_mm = self._normalize_pixel_spacing(pixel_spacing_mm)
        calibrated = pixel_spacing_mm is not None

        contours, hierarchy = cv2.findContours(binary_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        if not contours or hierarchy is None:
            return {
                "has_lesion": False,
                "total_lesions": 0,
                "lesions": [],
                "follicles": {
                    "count": 0,
                    "count_in_range": 0 if calibrated else None,
                    "diameters_px": [],
                    "diameters_mm": None,
                    "analysis_status": "SUCCEEDED",
                    "region_semantics": "UNCONFIRMED",
                    "diameter_method": "equivalent_area_diameter",
                },
                "max_diameter_mm": None,
                "ortho_diameter_mm": None,
                "d3_mm": None,
                "total_volume_cm3": None,
                "total_area_cm2": None,
                "max_diameter_px": 0.0,
                "ortho_diameter_px": 0.0,
                "total_area_px": 0.0,
                "calibrated": calibrated,
            }

        # Identify outer contours (parent == -1) and subtract inner erased holes
        outer_candidates = []
        for i, cnt in enumerate(contours):
            if hierarchy[0][i][3] == -1:  # outer contour
                outer_area = float(cv2.contourArea(cnt))
                hole_area = 0.0
                child_idx = hierarchy[0][i][2]
                while child_idx != -1:
                    hole_area += float(cv2.contourArea(contours[child_idx]))
                    child_idx = hierarchy[0][child_idx][0]  # next sibling hole
                net_area = max(0.0, outer_area - hole_area)
                outer_candidates.append((cnt, net_area))

        outer_candidates.sort(key=lambda x: x[1], reverse=True)
        lesions = []
        filtered_components = []
        total_area_px = 0.0

        for idx, (cnt, area_px) in enumerate(outer_candidates):
            perimeter_px = float(cv2.arcLength(cnt, True))

            # Minimum Area Bounding Box for true oriented diameters
            rect = cv2.minAreaRect(cnt)
            (cx, cy), (dim1_px, dim2_px), _angle = rect

            # Identify max diameter and orthogonal diameter
            d_max_px = float(max(dim1_px, dim2_px))
            d_orth_px = float(min(dim1_px, dim2_px))

            d_max_mm = float(d_max_px * pixel_spacing_mm) if calibrated else None
            d_orth_mm = float(d_orth_px * pixel_spacing_mm) if calibrated else None
            area_cm2 = float((area_px * (pixel_spacing_mm**2)) / 100.0) if calibrated else None

            # Compute oriented caliper endpoints for drawing crosshairs
            box_points = cv2.boxPoints(rect)  # 4 vertices
            p0, p1, p2, p3 = box_points

            # Center-points of opposite edges with pure python floats
            mid_01 = [float((p0[0] + p1[0]) / 2), float((p0[1] + p1[1]) / 2)]
            mid_23 = [float((p2[0] + p3[0]) / 2), float((p2[1] + p3[1]) / 2)]
            mid_12 = [float((p1[0] + p2[0]) / 2), float((p1[1] + p2[1]) / 2)]
            mid_30 = [float((p3[0] + p0[0]) / 2), float((p3[1] + p0[1]) / 2)]

            # Ensure caliper_dmax is strictly the longer axis and caliper_dorth is the orthogonal shorter axis
            d_01_23 = math.dist(mid_01, mid_23)
            d_12_30 = math.dist(mid_12, mid_30)
            if d_12_30 >= d_01_23:
                caliper_dmax = [mid_12, mid_30]
                caliper_dorth = [mid_01, mid_23]
            else:
                caliper_dmax = [mid_01, mid_23]
                caliper_dorth = [mid_12, mid_30]

            # Convert contour points to simple polygon list of ints
            polygon = [[int(pt[0]), int(pt[1])] for pt in cnt.reshape(-1, 2)]

            endpoints_outside = False
            h_mask, w_mask = binary_mask.shape[:2]
            for pt in caliper_dmax + caliper_dorth:
                px_x = int(round(pt[0]))
                px_y = int(round(pt[1]))
                if px_x < 0 or px_x >= w_mask or px_y < 0 or px_y >= h_mask or binary_mask[px_y, px_x] == 0:
                    endpoints_outside = True
                    break

            lesion_entry = {
                "lesion_id": int(idx + 1),
                "center": [round(float(cx), 1), round(float(cy), 1)],
                "max_diameter_mm": round(d_max_mm, 2) if d_max_mm is not None else None,
                "ortho_diameter_mm": round(d_orth_mm, 2) if d_orth_mm is not None else None,
                "max_diameter_px": round(d_max_px, 2),
                "ortho_diameter_px": round(d_orth_px, 2),
                "area_px": round(area_px, 2),
                "perimeter_px": round(perimeter_px, 2),
                "d3_mm": None,
                "volume_cm3": None,
                "area_cm2": round(area_cm2, 3) if area_cm2 is not None else None,
                "perimeter_mm": round(perimeter_px * pixel_spacing_mm, 2) if calibrated else None,
                "caliper_dmax_points": caliper_dmax,
                "caliper_dorth_points": caliper_dorth,
                "polygon": polygon,
                "measurement_method": "external_contour_min_area_rectangle",
                "proxy_type": "oriented_bounding_box",
                "endpoints_outside_mask": endpoints_outside,
            }

            if area_px < 50:
                lesion_entry["exclusion_reason"] = f"Diện tích ({round(area_px, 1)} px²) dưới ngưỡng lọc (50 px²)"
                filtered_components.append(lesion_entry)
                continue

            total_area_px += area_px
            lesions.append(lesion_entry)

        warning = None
        exclusion_reason = None
        if lesions:
            dominant = lesions[0]
            max_d_overall = dominant["max_diameter_mm"]
            ortho_d_overall = dominant["ortho_diameter_mm"]
            total_area_cm2 = float(sum(lesion["area_cm2"] for lesion in lesions)) if calibrated else None
            max_d_overall_px = dominant["max_diameter_px"]
            ortho_d_overall_px = dominant["ortho_diameter_px"]
            has_lesion = True
            if filtered_components:
                warning = (
                    f"Mask có {len(filtered_components)} vùng dưới ngưỡng lọc diện tích (50 px²); "
                    "tổng diện tích không bao gồm các vùng này. Cần bác sĩ rà soát từng vùng."
                )
                exclusion_reason = "some_components_below_min_area"
        elif filtered_components:
            dominant = filtered_components[0]
            max_d_overall = dominant["max_diameter_mm"]
            ortho_d_overall = dominant["ortho_diameter_mm"]
            total_area_cm2 = float(sum(comp["area_cm2"] for comp in filtered_components)) if calibrated else None
            max_d_overall_px = dominant["max_diameter_px"]
            ortho_d_overall_px = dominant["ortho_diameter_px"]
            has_lesion = True
            warning = (
                f"Mặt nạ có {len(filtered_components)} vùng tổn thương dưới ngưỡng lọc diện tích (50 px²). "
                "Số đo được giữ lại kèm cảnh báo để bác sĩ rà soát lâm sàng."
            )
            exclusion_reason = "all_components_below_min_area"
        else:
            max_d_overall = None
            ortho_d_overall = None
            total_area_cm2 = None
            max_d_overall_px = 0.0
            ortho_d_overall_px = 0.0
            has_lesion = False

        follicles_data = {
            "count": 0,
            "count_in_range": 0 if calibrated else None,
            "diameters_px": [],
            "diameters_mm": None,
            "analysis_status": "SUCCEEDED",
            "region_semantics": "UNCONFIRMED",
            "diameter_method": "equivalent_area_diameter",
        }
        if binary_mask.sum() > 0:
            try:
                from backend.services.morphology_extractor import separate_and_count_follicles
                follicles_data = separate_and_count_follicles(
                    binary_mask,
                    pixel_spacing_mm=pixel_spacing_mm if calibrated else None,
                )
            except Exception:
                import logging
                logging.getLogger(__name__).exception("Mask region separation failed")
                follicles_data = {
                    "count": None,
                    "count_in_range": None,
                    "diameters_px": None,
                    "diameters_mm": None,
                    "analysis_status": "FAILED",
                    "error_code": "REGION_SEPARATION_FAILED",
                    "region_semantics": "UNCONFIRMED",
                    "diameter_method": "equivalent_area_diameter",
                }

        return {
            "has_lesion": has_lesion,
            "total_lesions": len(lesions) if lesions else len(filtered_components),
            "lesions": lesions,
            "filtered_components": filtered_components,
            "follicles": follicles_data,
            "exclusion_reason": exclusion_reason,
            "warning": warning,
            "max_diameter_mm": round(max_d_overall, 2) if max_d_overall is not None else None,
            "ortho_diameter_mm": round(ortho_d_overall, 2) if ortho_d_overall is not None else None,
            "max_diameter_px": round(max_d_overall_px, 2),
            "ortho_diameter_px": round(ortho_d_overall_px, 2),
            "total_area_px": round(total_area_px, 2),
            "d3_mm": None,
            "total_volume_cm3": None,
            "total_area_cm2": round(total_area_cm2, 3) if total_area_cm2 is not None else None,
            "calibrated": calibrated,
            "measurement_method": "external_contour_min_area_rectangle",
            "proxy_type": "oriented_bounding_box",
            "clinical_disclaimer": (
                "Automated 2D bounding proxy. Measurement represents in-plane oriented bounding box axes (minAreaRect), "
                "not full 3D clinical diameter. Caliper endpoints may extend outside concave lesion contours."
            ),
        }

    @staticmethod
    def generate_overlay_base64(
        gray_512: np.ndarray, binary_mask: np.ndarray, measurements: dict, alpha: float = 0.35
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
        scale: float = 1.0,
        generate_overlay: bool = True,
    ) -> dict:
        """
        Executes full medical inference pipeline:
        Tensor -> one model forward pass -> sigmoid -> locked threshold -> RLE.
        """
        probs = self.forward_probabilities(tensor_512)

        # Clean binary mask via morphological filtering
        clean_mask = self.post_process_mask(probs)

        # Average confidence inside lesion area or whole image
        if clean_mask.sum() > 0:
            confidence = float(np.mean(probs[clean_mask > 0]))
        else:
            confidence = float(1.0 - np.mean(probs))  # Confidence for normal empty mask

        # Calculate Uncertainty & OOD Metric
        uncertainty = self.calculate_uncertainty(probs, clean_mask)

        # Uncalibrated heuristic; never treat this as a clinical safety gate.
        is_quality_valid = bool(
            confidence >= 0.70
            and not uncertainty.get("is_uncertain", False)
            and uncertainty.get("uncertainty_level") != "HIGH"
        )

        quality_gate = {
            "passed": is_quality_valid,
            "validated": False,
            "score_type": "mean_mask_pixel_probability_uncalibrated",
            "min_confidence_required": 0.70,
            "actual_confidence": round(float(confidence), 3),
            "uncertainty_level": uncertainty.get("uncertainty_level", "LOW"),
            "status": "HEURISTIC_PASS" if is_quality_valid else "HEURISTIC_REVIEW_FLAG",
            "alert": (
                "Điểm pixel vượt ngưỡng heuristic; vẫn cần người rà soát mask."
                if is_quality_valid
                else "Điểm pixel hoặc độ bất định kích hoạt cảnh báo heuristic chưa kiểm định. "
                "Cần đối chiếu ảnh gốc và chỉnh mask khi cần."
            ),
        }

        # Extract clinical measurements and calipers (scale-adjusted spacing for 512x512 mask)
        calibrated_spacing = self._normalize_pixel_spacing(pixel_spacing_mm)
        effective_spacing = (
            calibrated_spacing / scale
            if calibrated_spacing is not None and scale and scale > 0
            else calibrated_spacing
        )
        measurements = self.extract_calipers_and_measurements(clean_mask, pixel_spacing_mm=effective_spacing)
        if not is_quality_valid:
            measurements["quality_alert"] = quality_gate["alert"]
        calibrated = calibrated_spacing is not None
        measurements["calibrated"] = calibrated
        if not calibrated:
            for key in (
                "max_diameter_mm",
                "ortho_diameter_mm",
                "d3_mm",
                "total_volume_cm3",
                "total_area_cm2",
            ):
                measurements[key] = None
            for collection in ("lesions", "filtered_components"):
                for lesion in measurements.get(collection, []):
                    for key in (
                        "max_diameter_mm",
                        "ortho_diameter_mm",
                        "d3_mm",
                        "volume_cm3",
                        "area_cm2",
                        "perimeter_mm",
                    ):
                        lesion[key] = None

        # Mask geometry alone cannot establish IOTA or O-RADS categories.
        morph_analysis = {}
        cdss = {}

        # Encode RLE and Overlay
        rle = self.mask_to_rle(clean_mask)
        overlay_base64 = (
            self.generate_overlay_base64(padded_gray, clean_mask, measurements)
            if (generate_overlay and getattr(self, "default_generate_overlay", True))
            else None
        )

        # Provenance metadata
        provenance = {
            "model_name": getattr(self, "model_name", self.MODEL_NAME),
            "model_version": getattr(self, "model_version", self.MODEL_VERSION),
            "model_checksum": self.model_checksum,
            "preprocessor_version": self.PREPROCESSOR_VERSION,
            "device": self.device,
            "threshold": self.threshold,
            "pixel_spacing_mm": pixel_spacing_mm,
        }

        return {
            "rle_mask": rle,
            "confidence_score": round(float(confidence), 3),
            "mask_pixel_confidence": round(float(confidence), 3),
            "score_type": "mean_mask_pixel_probability_uncalibrated",
            "uncertainty": uncertainty,
            "quality_gate": quality_gate,
            "measurements": measurements,
            "acoustic_profile": morph_analysis,
            "cdss_classification": cdss,
            "overlay_base64": overlay_base64,
            "uncertainty_map_png": self.encode_uncertainty_heatmap_png(probs),
            "binary_mask_np": clean_mask,
            "provenance": provenance,
            "timings": {
                "model_forward_ms": round(float(getattr(self, "last_forward_ms", 0.0)), 2),
            },
        }


    predict = run_inference



def synthesize_multibranch_findings(
    study_id: str,
    side: str,
    pixel_spacing_mm: float | None = None,
    lesion_measurements: dict | None = None,
    ovary_measurements: dict | None = None,
    follicle_measurements: dict | None = None,
    lesion_probs: dict | None = None,
    img_gray = None,
    binary_mask = None,
    ood_score: float | None = None,
    patient_context: dict | None = None,
    clinician_findings: dict | None = None,
) -> dict:
    from backend.services.cdss_engine import CDSSReasoningEngine
    from backend.services.diagnostic_engine import DiagnosticReasoningEngine

    diag_engine = DiagnosticReasoningEngine()
    cdss_engine = CDSSReasoningEngine()

    lm = lesion_measurements or {}
    om = ovary_measurements
    fm = follicle_measurements

    # 1. Estimate features if image and mask are available
    if img_gray is not None and binary_mask is not None:
        estimated_features = diag_engine.estimate_orads_features(
            img_gray=img_gray,
            binary_mask=binary_mask,
            pixel_spacing_mm=pixel_spacing_mm,
        )
    else:
        estimated_features = {}

    # A mask-derived count for one image is not a validated whole-ovary FNPO.
    # Keep PCOM assessment unavailable until a clinician confirms the complete
    # acquisition and the measured follicle set.
    pcos_res = None

    # 3. Fuse 8-class probabilities + features + abstain logic
    ai_diag = diag_engine.fuse_and_evaluate(
        lesion_probs=lesion_probs,
        estimated_features=estimated_features,
        ood_score=ood_score,
        pcos_suggestion=pcos_res,
    )

    # 4. Integrate into CDSS Reasoning Engine
    cdss_result = None
    if clinician_findings is not None:
        try:
            cdss_result = cdss_engine.evaluate_case(
                vision_findings=clinician_findings,
                patient_context=patient_context,
            )
            ai_diag["cdss_raw"] = cdss_result
            category = (cdss_result.get("orads_stratification") or {}).get("category")
            if cdss_result.get("status") == "RULE_MATCHED" and category is not None:
                ai_diag["orads_suggested"]["category"] = category
        except Exception:
            cdss_result = None

    return {
        "study_id": study_id,
        "side": side,
        "pixel_spacing_mm": pixel_spacing_mm,
        "ovary": om,
        "follicles": fm,
        "lesion": lm,
        "ai_diagnosis": ai_diag,
        "review_status": "PENDING",
        "clinician_overrides": {},
    }
