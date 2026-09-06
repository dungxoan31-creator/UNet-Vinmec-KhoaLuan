"""
Ultrasound Image Preprocessing & Quality Assessment Service:
- ROI Fan-beam Cropping
- Letterbox Resize with Aspect Ratio preservation
- CLAHE Contrast Enhancement & Speckle Denoising
- Image Quality Assessment (IQA)
"""

import cv2
import numpy as np
import torch


class UltrasoundPreprocessor:
    def __init__(self, target_size=(512, 512), clahe_clip_limit=2.0, clahe_grid_size=(8, 8)):
        self.target_size = target_size
        self.clahe = cv2.createCLAHE(clipLimit=clahe_clip_limit, tileGridSize=clahe_grid_size)

    def crop_fan_beam_roi(self, image_np):
        """
        Detects the ultrasound fan-beam / sector cone and crops out outer black borders & text metadata.
        """
        if len(image_np.shape) == 3:
            gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)
        else:
            gray = image_np.copy()

        # Threshold to find non-black ultrasound beam area
        _, thresh = cv2.threshold(gray, 15, 255, cv2.THRESH_BINARY)

        # Morphological close to bridge internal dark cyst areas
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        # Find largest contour (the fan beam)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return image_np, (0, 0, image_np.shape[1], image_np.shape[0])

        largest_cnt = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_cnt)

        # Ensure minimal bounding box sanity
        if w < 50 or h < 50:
            return image_np, (0, 0, image_np.shape[1], image_np.shape[0])

        cropped = image_np[y : y + h, x : x + w]
        return cropped, (x, y, w, h)

    def letterbox_resize(self, image_np, target_size=None, is_mask=False):
        """
        Resizes image or binary mask to target_size (default 512x512) preserving aspect ratio via black padding.
        Uses cv2.INTER_LINEAR (Bilinear) for images and cv2.INTER_NEAREST (Nearest Neighbor) for masks.
        Returns: padded_image, transform_params
        """
        if target_size is None:
            target_size = self.target_size

        target_w, target_h = target_size
        orig_h, orig_w = image_np.shape[:2]

        scale = min(target_w / orig_w, target_h / orig_h)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        interp = cv2.INTER_NEAREST if is_mask else cv2.INTER_LINEAR
        resized = cv2.resize(image_np, (new_w, new_h), interpolation=interp)

        # Create padded canvas
        pad_x = (target_w - new_w) // 2
        pad_y = (target_h - new_h) // 2

        if len(image_np.shape) == 3:
            padded = np.zeros((target_h, target_w, 3), dtype=image_np.dtype)
            padded[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized
        else:
            padded = np.zeros((target_h, target_w), dtype=image_np.dtype)
            padded[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized

        transform_params = {
            "scale": scale,
            "pad_x": pad_x,
            "pad_y": pad_y,
            "orig_w": orig_w,
            "orig_h": orig_h,
            "target_w": target_w,
            "target_h": target_h,
        }
        return padded, transform_params

    def inverse_letterbox_mask(self, mask_512: np.ndarray, transform_params: dict) -> np.ndarray:
        """
        Restores a 512x512 padded binary mask back to its original image dimensions
        using Nearest Neighbor interpolation (cv2.INTER_NEAREST) to preserve exact binary mask edges.
        """
        pad_x = transform_params["pad_x"]
        pad_y = transform_params["pad_y"]
        orig_w = transform_params["orig_w"]
        orig_h = transform_params["orig_h"]
        scale = transform_params["scale"]

        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        # Crop active unpadded region
        cropped_mask = mask_512[pad_y : pad_y + new_h, pad_x : pad_x + new_w]
        if cropped_mask.size == 0:
            return np.zeros((orig_h, orig_w), dtype=np.uint8)

        # Resize to original resolution with Nearest Neighbor
        orig_mask = cv2.resize(cropped_mask, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)
        return orig_mask

    def enhance_contrast_and_denoise(self, gray_np):
        """
        Applies Median filter for speckle noise suppression + CLAHE for local contrast enhancement.
        """
        # Mild median blur to suppress ultrasound speckle
        denoised = cv2.medianBlur(gray_np, 3)
        # Adaptive histogram equalization
        enhanced = self.clahe.apply(denoised)
        return enhanced

    def validate_ultrasound_suitability(self, image_np):
        """
        Comprehensive Clinical Image Suitability & Modality Validator.
        Detects:
        - Non-ultrasound natural/color images (selfies, outdoor photos, charts)
        - Blank/corrupted images (all white, all black, zero variance)
        - Extreme blur (out of focus, severe motion blur)
        - Extreme exposure (overexposed/underexposed)
        - Insufficient resolution or invalid aspect ratio
        """
        checklist = []
        is_suitable = True
        error_reasons = []

        if image_np is None or image_np.size == 0:
            return {
                "is_suitable": False,
                "is_acceptable": False,
                "iqa_score": 0.0,
                "error_code": "CORRUPTED_FILE",
                "error_message": "Không thể giải mã dữ liệu ảnh. File có thể bị hỏng.",
                "checklist": [{"name": "Giải mã file", "status": "FAIL", "desc": "File hỏng hoặc không có dữ liệu"}],
            }

        h, w = image_np.shape[:2]

        # 1. Check Dimensions & Resolution
        dim_pass = w >= 128 and h >= 128
        aspect_ratio = float(w / h)
        aspect_pass = 0.3 <= aspect_ratio <= 3.5

        if not dim_pass:
            is_suitable = False
            error_reasons.append(f"Độ phân giải quá nhỏ ({w}x{h} px, yêu cầu ≥ 128x128 px)")
            checklist.append(
                {
                    "step": "Kiểm tra độ phân giải",
                    "status": "FAIL",
                    "desc": f"Kích thước {w}x{h} px quá nhỏ để phân tích mô học.",
                }
            )
        elif not aspect_pass:
            is_suitable = False
            error_reasons.append(f"Tỷ lệ khung hình bất thường ({aspect_ratio:.2f})")
            checklist.append(
                {
                    "step": "Kiểm tra tỷ lệ khung hình",
                    "status": "FAIL",
                    "desc": f"Tỷ lệ {aspect_ratio:.2f} không phù hợp với chuẩn quét siêu âm.",
                }
            )
        else:
            checklist.append(
                {
                    "step": "Kiểm tra độ phân giải & tỷ lệ",
                    "status": "PASS",
                    "desc": f"Kích thước {w}x{h} px (Đạt chuẩn chuẩn đoán)",
                }
            )

        # 2. Check Modality & Color Saturation (Reject general non-ultrasound photos)
        if len(image_np.shape) == 3 and image_np.shape[2] == 3:
            hsv = cv2.cvtColor(image_np, cv2.COLOR_BGR2HSV)
            saturation = hsv[:, :, 1]
            mean_sat = float(np.mean(saturation))
            high_sat_ratio = float(np.sum(saturation > 60) / saturation.size)
            gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)

            # Ultrasound 2D is predominantly grayscale. High saturation over >15% of image indicates natural photo.
            if high_sat_ratio > 0.18 and mean_sat > 35.0:
                is_suitable = False
                error_reasons.append("Ảnh màu thông thường / Không phải định dạng ảnh siêu âm y tế")
                checklist.append(
                    {
                        "step": "Kiểm tra định dạng siêu âm",
                        "status": "FAIL",
                        "desc": f"Phát hiện ảnh chụp thông thường (Độ bão hòa màu {mean_sat:.1f} > 35.0)",
                    }
                )
            else:
                checklist.append(
                    {
                        "step": "Kiểm tra định dạng siêu âm",
                        "status": "PASS",
                        "desc": "Định dạng ảnh đơn sắc thang xám chuẩn siêu âm B-Mode",
                    }
                )
        else:
            gray = image_np.copy()
            checklist.append(
                {
                    "step": "Kiểm tra định dạng siêu âm",
                    "status": "PASS",
                    "desc": "Định dạng ảnh thang xám Grayscale chuẩn",
                }
            )

        # 3. Check Exposure & Brightness (Blank / All black / All white)
        mean_intensity = float(np.mean(gray))
        std_intensity = float(np.std(gray))

        if mean_intensity < 8.0 or std_intensity < 6.0:
            is_suitable = False
            error_reasons.append("Ảnh hoàn toàn tối / Mất tín hiệu chùm sóng âm")
            checklist.append(
                {
                    "step": "Kiểm tra độ sáng & tương phản",
                    "status": "FAIL",
                    "desc": f"Ảnh quá tối (Độ sáng trung bình {mean_intensity:.1f}/255)",
                }
            )
        elif mean_intensity > 242.0:
            is_suitable = False
            error_reasons.append("Ảnh bị lóa sáng hoàn toàn / Trắng toàn phần")
            checklist.append(
                {
                    "step": "Kiểm tra độ sáng & tương phản",
                    "status": "FAIL",
                    "desc": f"Ảnh bị chói lóa (Độ sáng trung bình {mean_intensity:.1f}/255)",
                }
            )
        elif std_intensity < 16.0:
            is_suitable = False
            error_reasons.append("Ảnh đồng nhất / Không có cấu trúc mô phân giải")
            checklist.append(
                {
                    "step": "Kiểm tra độ sáng & tương phản",
                    "status": "FAIL",
                    "desc": f"Độ tương phản quá thấp (Độ lệch chuẩn {std_intensity:.1f})",
                }
            )
        else:
            checklist.append(
                {
                    "step": "Kiểm tra độ sáng & tương phản",
                    "status": "PASS",
                    "desc": f"Cân bằng sáng tốt ({mean_intensity:.1f}/255, Tương phản: {std_intensity:.1f})",
                }
            )

        # 4. Check Sharpness & Focus (Laplacian Variance)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if lap_var < 18.0:
            is_suitable = False
            error_reasons.append("Ảnh bị mờ nghiêm trọng / Mất nét do rung lắc")
            checklist.append(
                {
                    "step": "Kiểm tra độ sắc nét (Focus)",
                    "status": "FAIL",
                    "desc": f"Độ nét Laplacian {lap_var:.1f} (Dưới ngưỡng tối thiểu 18.0)",
                }
            )
        elif lap_var < 45.0:
            checklist.append(
                {
                    "step": "Kiểm tra độ sắc nét (Focus)",
                    "status": "WARN",
                    "desc": f"Độ nét vừa phải ({lap_var:.1f}). Bác sĩ nên kiểm tra kỹ ranh giới.",
                }
            )
        else:
            checklist.append(
                {
                    "step": "Kiểm tra độ sắc nét (Focus)",
                    "status": "PASS",
                    "desc": f"Độ nét tốt (Điểm Laplacian {lap_var:.1f} ≥ 45.0)",
                }
            )

        # Calculate Overall IQA Score
        iqa_score = 1.0
        if not dim_pass or not aspect_pass:
            iqa_score -= 0.4
        if len(image_np.shape) == 3 and (mean_sat > 35.0 or high_sat_ratio > 0.18):
            iqa_score -= 0.5
        if mean_intensity < 15.0 or mean_intensity > 235.0:
            iqa_score -= 0.4
        if std_intensity < 20.0:
            iqa_score -= 0.3
        if lap_var < 35.0:
            iqa_score -= 0.35

        iqa_score = max(0.05, min(1.0, iqa_score))

        final_msg = (
            "Ảnh đạt chuẩn kỹ thuật để phân tích AI."
            if is_suitable
            else f"Ảnh không phù hợp: {'; '.join(error_reasons)}"
        )

        return {
            "is_suitable": is_suitable,
            "is_acceptable": is_suitable,
            "iqa_score": round(iqa_score, 2),
            "laplacian_variance": round(lap_var, 1),
            "mean_intensity": round(mean_intensity, 1),
            "contrast_std": round(std_intensity, 1),
            "error_reasons": error_reasons,
            "error_message": final_msg,
            "checklist": checklist,
        }

    def assess_image_quality(self, gray_np):
        """
        Legacy wrapper for backwards compatibility with validation pipeline.
        """
        suitability = self.validate_ultrasound_suitability(gray_np)
        return {
            "iqa_score": suitability["iqa_score"],
            "laplacian_variance": suitability["laplacian_variance"],
            "contrast_std": suitability["contrast_std"],
            "shadow_ratio": 0.0,
            "flags": suitability["error_reasons"],
            "is_acceptable": suitability["is_suitable"],
            "message": suitability["error_message"],
        }

    def compute_roi_mask(self, padded_gray, transform_params):
        """
        Generates a strict binary ROI mask isolating the ultrasound imaging cone
        and zeroing out all letterbox black margins and out-of-sector background.
        """
        target_h, target_w = self.target_size
        pad_x = transform_params["pad_x"]
        pad_y = transform_params["pad_y"]
        orig_w = transform_params["orig_w"]
        orig_h = transform_params["orig_h"]
        scale = transform_params["scale"]

        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        roi_mask = np.zeros((target_h, target_w), dtype=np.uint8)
        roi_mask[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = 1

        # Extract beam sector inside active area
        active_area = padded_gray[pad_y : pad_y + new_h, pad_x : pad_x + new_w]
        if active_area.size > 0:
            _, beam_thresh = cv2.threshold(active_area, 5, 255, cv2.THRESH_BINARY)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
            beam_closed = cv2.morphologyEx(beam_thresh, cv2.MORPH_CLOSE, kernel)

            # Find largest sector contour
            contours, _ = cv2.findContours(beam_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                largest_c = max(contours, key=cv2.contourArea)
                if cv2.contourArea(largest_c) > 0.15 * (new_w * new_h):
                    hull = cv2.convexHull(largest_c)
                    sector_mask = np.zeros_like(active_area)
                    cv2.drawContours(sector_mask, [hull], -1, 1, -1)
                    roi_mask[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = sector_mask

        return roi_mask

    def preprocess_for_inference(self, image_np):
        """
        Full end-to-end preprocessing pipeline for deep learning inference.
        Returns:
            - normalized_tensor: torch.Tensor of shape (1, 1, 512, 512), range [0, 1]
            - padded_gray: np.ndarray (512, 512)
            - transform_params: dict with scaling, padding offsets and strict ROI mask
            - iqa_report: dict with quality scores
        """
        if len(image_np.shape) == 3:
            gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)
        else:
            gray = image_np.copy()

        # 1. Assess image quality
        iqa_report = self.assess_image_quality(gray)

        # 2. Letterbox resize to 512x512
        padded_gray, transform_params = self.letterbox_resize(gray, self.target_size)

        # 3. Compute strict ultrasound field-of-view (FOV) ROI mask
        roi_mask = self.compute_roi_mask(padded_gray, transform_params)
        transform_params["roi_mask"] = roi_mask

        # 4. Contrast enhancement
        enhanced = self.enhance_contrast_and_denoise(padded_gray)

        # 5. Normalize to [0, 1] float tensor
        norm_float = enhanced.astype(np.float32) / 255.0
        tensor = torch.from_numpy(norm_float).unsqueeze(0).unsqueeze(0)  # (1, 1, H, W)

        return tensor, padded_gray, transform_params, iqa_report

