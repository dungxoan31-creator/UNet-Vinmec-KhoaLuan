"""
End-to-end Autonomous Ultrasound Pipeline:
Image Ingestion -> Lesion Segmentation (Mask) -> 8-Class Disease Pathology Classification.

Usage:
    python scripts/predict_image_mask_disease.py --image path/to/image.png [--mask path/to/mask.png]
                                                 [--output-json report.json] [--output-vis result.png]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import cv2
import numpy as np

from backend.core.calibration import normalize_pixel_spacing
from backend.core.image_utils import cv2_imread_unicode, cv2_imwrite_unicode
from backend.services.disease_classifier import DiseaseClassifierService
from backend.services.image_service import decode_ultrasound_image
from backend.services.inference_engine import InferenceEngine
from backend.services.preprocessor import UltrasoundPreprocessor
from backend.services.source_measurements import measure_source_mask

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("predict_image_mask_disease")


def load_image(image_path: Path) -> np.ndarray:
    if not image_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file ảnh: {image_path}")
    image = decode_ultrasound_image(str(image_path))
    if image is None:
        raise ValueError(f"Không thể giải mã file ảnh: {image_path}")
    return image


def load_or_generate_mask(
    image: np.ndarray,
    mask_path: Path | None,
    preprocessor: UltrasoundPreprocessor,
    inference_engine: InferenceEngine,
    pixel_spacing_mm: float | None,
) -> tuple[np.ndarray, dict]:
    """Returns (mask_512x512, segmentation_measurements)."""
    if mask_path:
        if not mask_path.is_file():
            raise FileNotFoundError(f"Không tìm thấy mask: {mask_path}")
        logger.info(f"Đọc mask có sẵn từ: {mask_path}")
        if mask_path.suffix.lower() == ".npy":
            mask_raw = np.load(str(mask_path))
        else:
            mask_raw = cv2_imread_unicode(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if (mask_raw is None or mask_raw.ndim != 2 or mask_raw.shape != image.shape[:2]
                or not np.isfinite(mask_raw).all()):
            raise ValueError("Provided mask must match source image dimensions.")
        mask_binary, _ = preprocessor.letterbox_resize((mask_raw > 0).astype(np.uint8), is_mask=True)
        measurements = measure_source_mask(
            image, InferenceEngine.mask_to_rle(mask_binary), preprocessor, inference_engine,
            {"pixel_spacing_mm": pixel_spacing_mm, "calibrated": pixel_spacing_mm is not None,
             "calibration_source": "MANUAL" if pixel_spacing_mm is not None else "NONE"},
        )
        return mask_binary, measurements

    logger.info("Chạy mô hình phân đoạn U-Net để sinh Mask tự động...")
    if not inference_engine.is_model_ready:
        raise RuntimeError("A verified segmentation checkpoint is required to generate a mask.")
    tensor_512, padded_gray, params, iqa = preprocessor.preprocess_for_inference(image, enable_caliper_removal=False)
    seg_result = inference_engine.predict(tensor_512, padded_gray, pixel_spacing_mm=pixel_spacing_mm,
                                          scale=params["scale"], generate_overlay=False)
    mask_binary = seg_result.get("binary_mask_np")
    if mask_binary is None:
        mask_binary = np.zeros((512, 512), dtype=np.uint8)
    measurements = measure_source_mask(
        image, InferenceEngine.mask_to_rle(mask_binary), preprocessor, inference_engine,
        {"pixel_spacing_mm": pixel_spacing_mm, "calibrated": pixel_spacing_mm is not None,
         "calibration_source": "MANUAL" if pixel_spacing_mm is not None else "NONE"},
    )
    return mask_binary, measurements


def render_visualization(
    image: np.ndarray,
    mask_512: np.ndarray,
    diagnosis: dict,
    output_path: Path,
):
    """Generates a 3-panel clinical visualization image."""
    # 1. Base image (Letterboxed to 512x512)
    panel_orig, _ = UltrasoundPreprocessor().letterbox_resize(image)

    # 2. Overlay panel
    panel_overlay = panel_orig.copy()
    contours, _ = cv2.findContours(mask_512, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(panel_overlay, contours, -1, (0, 255, 255), 2)  # Yellow contour
    # Add cyan fill
    fill_mask = np.zeros_like(panel_orig)
    fill_mask[mask_512 > 0] = (255, 128, 0)
    panel_overlay = cv2.addWeighted(panel_overlay, 0.75, fill_mask, 0.25, 0)

    # 3. Chart/Info panel
    panel_info = np.full((512, 560, 3), 24, dtype=np.uint8)

    # Title
    cv2.putText(panel_orig, "ANH SIEU AM GOC", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(panel_overlay, "PHAN DOAN MASK (U-NET)", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    cv2.putText(panel_info, "PHAN LOAI BENH HOC (AI - RUO)", (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 255, 150), 2)

    # Diagnostics text
    label_en = diagnosis.get("suggested_label", "Unknown")
    label_vi = diagnosis.get("suggested_label_vi", label_en)
    conf = diagnosis.get("confidence", 0.0)
    category = diagnosis.get("pathology_category", "N/A")
    status = diagnosis.get("status", "PREDICTED")

    y = 80
    status_color = (0, 255, 0) if status == "PREDICTED" else (0, 165, 255)
    cv2.putText(panel_info, f"Trang thai: {status}", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, status_color, 2)
    y += 35
    cv2.putText(panel_info, "Benh du doan (Top 1):", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    y += 28
    cv2.putText(panel_info, f"{label_vi}", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    y += 25
    cv2.putText(panel_info, f"({label_en}) - Do tin cay: {conf * 100:.1f}%", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 255), 1)

    y += 35
    cv2.putText(panel_info, f"Phan nhom: {category}", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 255), 1)

    # Top 3 probability bars
    y += 45
    cv2.putText(panel_info, "TOP 3 XAC SUAT:", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 100), 2)
    y += 15

    top3 = diagnosis.get("top3", [])
    bar_max_w = 260
    for item in top3:
        _, class_vi, p = item[0], item[1], item[2]
        y += 28
        short_name = class_vi[:25]
        cv2.putText(panel_info, f"{short_name}: {p * 100:.1f}%", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)
        y += 8
        bar_w = int(bar_max_w * min(1.0, max(0.0, p)))
        cv2.rectangle(panel_info, (20, y), (20 + bar_max_w, y + 10), (50, 50, 50), -1)
        cv2.rectangle(panel_info, (20, y), (20 + bar_w, y + 10), (0, 200, 255), -1)
        y += 10

    # Measurements
    meas = diagnosis.get("mask_measurements", {})
    y += 35
    cv2.putText(panel_info, "SO DO MASK:", (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 255), 2)
    y += 25
    d_mm = meas.get("max_diameter_mm")
    area_cm2 = meas.get("area_cm2")
    meas_str = f"Duong kinh: {d_mm} mm | Dien tich: {area_cm2} cm2" if d_mm else f"Dien tich: {meas.get('area_px', 0)} px"
    cv2.putText(panel_info, meas_str, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 255, 180), 1)

    # RUO disclaimer footer
    cv2.putText(panel_info, "RUO: Ket qua nghien cuu, khong thay the bac si.", (20, 495), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 120, 120), 1)

    # Stitch 3 panels horizontally
    composite = np.hstack([panel_orig, panel_overlay, panel_info])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2_imwrite_unicode(str(output_path), composite)
    logger.info(f"Đã lưu ảnh trực quan hóa: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Pipeline đọc ảnh, mask và phân loại bệnh học buồng trứng (RUO).")
    parser.add_argument("--image", required=True, type=Path, help="Đường dẫn file ảnh siêu âm (PNG, JPG, DICOM).")
    parser.add_argument("--mask", type=Path, default=None, help="Đường dẫn file mask có sẵn (tùy chọn).")
    parser.add_argument("--pixel-spacing", type=float, default=None, help="Tỉ lệ mm/pixel đã hiệu chuẩn; bỏ trống để chỉ đo pixel.")
    parser.add_argument("--output-json", type=Path, default=None, help="Đường dẫn lưu file JSON kết quả.")
    parser.add_argument("--output-vis", type=Path, default=None, help="Đường dẫn lưu ảnh minh họa trực quan 3 khung.")
    args = parser.parse_args()
    if args.pixel_spacing is not None and normalize_pixel_spacing(args.pixel_spacing) is None:
        parser.error("--pixel-spacing must be positive and finite.")

    # 1. Ingest image
    logger.info(f"Đang đọc ảnh: {args.image}")
    image = load_image(args.image)

    # 2. Get or generate segmentation mask
    from backend.app.config import model_registry
    preprocessor = UltrasoundPreprocessor()
    inference_engine = model_registry.get_primary_adapter().engine
    mask_512, measurements = load_or_generate_mask(image, args.mask, preprocessor, inference_engine, args.pixel_spacing)

    # 3. Classify disease pathology
    logger.info("Chạy mô hình phân loại bệnh học 8 nhóm MMOTU...")
    classifier = DiseaseClassifierService()
    _, transform = preprocessor.letterbox_resize(image)
    source_mask = preprocessor.inverse_letterbox_mask(mask_512, transform)
    diagnosis = classifier.predict_disease(image, mask=source_mask, pixel_spacing_mm=args.pixel_spacing)

    # Display results
    print("\n" + "=" * 65)
    print("      KẾT QUẢ PHÂN LOẠI BỆNH HỌC SIÊU ÂM BUỒNG TRỨNG (RUO)")
    print("=" * 65)
    print(f"Ảnh đầu vào        : {args.image}")
    print(f"Trạng thái         : {diagnosis['status']}")
    if diagnosis["abstain"]:
        print(f"Lý do Abstain      : {diagnosis['abstain_reason']}")
    print(f"Bệnh dự đoán (Top1): {diagnosis['suggested_label_vi']}")
    print(f"Tên khoa học       : {diagnosis['suggested_label']}")
    print(f"Độ tin cậy         : {diagnosis['confidence'] * 100:.2f}%")
    print(f"Phân loại bệnh học : {diagnosis['pathology_category']}")
    print("-" * 65)
    print("BẢNG XẾP HẠNG TOP 3 BỆNH NGHI NGỜ NHẤT:")
    for idx, (code, name_vi, p) in enumerate(diagnosis.get("top3", []), start=1):
        print(f"  {idx}. {name_vi: <35} ({code}): {p * 100:.2f}%")
    print("-" * 65)
    meas = diagnosis.get("mask_measurements", {})
    if meas.get("lesion_detected"):
        print(f"Tổn thương phát hiện : CÓ (Diện tích: {meas.get('area_cm2', 'N/A')} cm2, ĐK: {meas.get('max_diameter_mm', 'N/A')} mm)")
    else:
        print("Tổn thương phát hiện : KHÔNG PHÁT HIỆN HOẶC MASK RỖNG")
    print("=" * 65)
    print("KHUYẾN CÁO: Kết quả chỉ phục vụ nghiên cứu (RUO), không thay thế bác sĩ.\n")

    # Save outputs if requested
    full_output = {
        "image": str(args.image),
        "mask_provided": bool(args.mask),
        "pixel_spacing_mm": args.pixel_spacing,
        "diagnosis": diagnosis,
        "segmentation_measurements": measurements,
    }

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(full_output, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"Đã lưu kết quả JSON: {args.output_json}")

    if args.output_vis:
        render_visualization(image, mask_512, diagnosis, args.output_vis)


if __name__ == "__main__":
    main()
