"""
Independent Test Set Evaluation for Standard U-Net Baseline.
Evaluates on the 46 held-out test cases (Patient-Level Split, 28 patients, 5 empty masks).
Calculates Dice (DSC), IoU, Recall, Precision, and Specificity.
Exports visual grids: Best, Average, Worst case predictions.
"""

import os
import sys
import json
import cv2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import torch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models.unet import StandardUNet
from backend.services.preprocessor import UltrasoundPreprocessor
from ai_training.metrics_clinical import compute_sample_clinical_metrics, compute_dataset_clinical_summary


def cv2_imread_unicode(file_path, flags=cv2.IMREAD_GRAYSCALE):
    if not os.path.exists(file_path):
        return None
    with open(file_path, "rb") as f:
        bytes_data = f.read()
    arr = np.frombuffer(bytes_data, dtype=np.uint8)
    return cv2.imdecode(arr, flags)


def evaluate_test_set(
    checkpoint_path="checkpoints/baseline_unet_best.pth",
    test_csv="ai_training/splits/test.csv",
    output_metrics="evaluation/baseline_test_metrics.json",
    vis_dir="evaluation/baseline_visualizations"
):
    print("=" * 70)
    print("   BƯỚC 6: ĐÁNH GIÁ ĐỊNH LƯỢNG TRÊN TẬP TEST SET ĐỘC LẬP (46 CA)")
    print("=" * 70)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[THIẾT BỊ] Suy luận trên: {device}")

    # 1. Model Loading
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    if not os.path.exists(checkpoint_path):
        print(f"[ERROR] Không tìm thấy checkpoint: {checkpoint_path}")
        return False

    state_dict = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()
    print(f"[MÔ HÌNH] Đã nạp checkpoint: {checkpoint_path}")

    # 2. Test Manifest
    df = pd.read_csv(test_csv)
    print(f"[DỮ LIỆU] Tổng số ca Test độc lập: {len(df)} (Bệnh nhân: {df['patient_id'].nunique()}, Empty: {(df['is_empty_mask']==True).sum()})")

    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    sample_results = []
    case_predictions = []

    print("[TIẾN TRÌNH] Đang chạy suy luận và đo lường từng ca...")
    for idx, row in df.iterrows():
        case_id = str(row["case_id"])
        img_p = str(row["image_path"]).replace("\\", "/")
        mask_p = str(row["mask_path"]).replace("\\", "/")

        raw_img = cv2_imread_unicode(img_p, cv2.IMREAD_GRAYSCALE)
        raw_mask = cv2_imread_unicode(mask_p, cv2.IMREAD_GRAYSCALE)

        if raw_img is None:
            continue

        is_empty_flag = bool(row.get("is_empty_mask", False))
        if is_empty_flag or raw_mask is None:
            raw_mask_bin = np.zeros((raw_img.shape[0], raw_img.shape[1]), dtype=np.uint8)
        else:
            if raw_mask.shape != raw_img.shape:
                raw_mask = cv2.resize(raw_mask, (raw_img.shape[1], raw_img.shape[0]), interpolation=cv2.INTER_NEAREST)
            raw_mask_bin = (raw_mask > 127).astype(np.uint8)

        # Preprocessing
        pad_img, params = preprocessor.letterbox_resize(raw_img, is_mask=False)
        enh_img = preprocessor.clahe.apply(pad_img)
        tensor_img = torch.from_numpy(enh_img).unsqueeze(0).unsqueeze(0).float().to(device) / 255.0

        # Inference
        with torch.no_grad():
            logits = model(tensor_img)
            probs = torch.sigmoid(logits)
            pred_512 = (probs > 0.5).squeeze().cpu().numpy().astype(np.uint8)

        # Inverse Letterbox
        restored_mask = preprocessor.inverse_letterbox_mask(pred_512, params)

        # Metrics
        m = compute_sample_clinical_metrics(restored_mask, raw_mask_bin)
        m["case_id"] = case_id
        sample_results.append(m)

        case_predictions.append({
            "case_id": case_id,
            "raw_image": raw_img,
            "raw_mask": raw_mask_bin,
            "pred_mask": restored_mask,
            "dice": m["dice"],
            "iou": m["iou"],
            "recall": m["recall"],
            "is_empty": m["is_empty"]
        })

    # Summary Metrics
    summary = compute_dataset_clinical_summary(sample_results)
    os.makedirs(os.path.dirname(output_metrics), exist_ok=True)
    with open(output_metrics, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4)

    print("\n" + "=" * 50)
    print("      KẾT QUẢ ĐÁNH GIÁ ĐỊNH LƯỢNG TEST SET")
    print("=" * 50)
    print(f"Tổng số ca kiểm thử:       {summary['total_cases_evaluated']}")
    print(f"Số ca có tổn thương:       {summary['lesion_cases_count']}")
    print(f"Số ca nang/bt bình thường: {summary['normal_cases_count']}")
    print(f"Foreground Dice (Mean):    {summary['foreground_dice_mean']:.4f} ± {summary['foreground_dice_std']:.4f}")
    print(f"Foreground IoU (Mean):     {summary['foreground_iou_mean']:.4f} ± {summary['foreground_iou_std']:.4f}")
    print(f"Recall / Sensitivity:      {summary['recall_sensitivity_mean']:.4f}")
    print(f"Precision:                 {summary['precision_mean']:.4f}")
    print(f"Specificity (Tất cả ca):   {summary['specificity_all_cases']:.4f}")
    print(f"Specificity (Ca bình thường): {summary['specificity_normal_cases']:.4f}")
    print("=" * 50)
    print(f"[XUẤT BẢN] Đã lưu metrics: {output_metrics}")

    # Visualizations
    os.makedirs(vis_dir, exist_ok=True)
    lesion_preds = [c for c in case_predictions if not c["is_empty"]]
    lesion_preds.sort(key=lambda x: x["dice"], reverse=True)

    if len(lesion_preds) >= 9:
        best_cases = lesion_preds[:3]
        mid = len(lesion_preds) // 2
        avg_cases = lesion_preds[mid - 1 : mid + 2]
        worst_cases = lesion_preds[-3:]

        def save_grid(cases, filename, title_prefix):
            fig, axes = plt.subplots(len(cases), 3, figsize=(12, 4 * len(cases)))
            for i, c in enumerate(cases):
                # Raw
                axes[i, 0].imshow(c["raw_image"], cmap="gray")
                axes[i, 0].set_title(f"{c['case_id']}\nRaw Image")
                axes[i, 0].axis("off")

                # Ground Truth Overlay
                axes[i, 1].imshow(c["raw_image"], cmap="gray")
                gt_overlay = np.ma.masked_where(c["raw_mask"] == 0, c["raw_mask"])
                axes[i, 1].imshow(gt_overlay, cmap="autumn", alpha=0.5)
                axes[i, 1].set_title(f"Ground Truth Mask\n(Verified)")
                axes[i, 1].axis("off")

                # Pred Overlay
                axes[i, 2].imshow(c["raw_image"], cmap="gray")
                pred_overlay = np.ma.masked_where(c["pred_mask"] == 0, c["pred_mask"])
                axes[i, 2].imshow(pred_overlay, cmap="winter", alpha=0.5)
                axes[i, 2].set_title(f"AI Prediction\nDice: {c['dice']:.4f} | IoU: {c['iou']:.4f}")
                axes[i, 2].axis("off")

            plt.suptitle(f"{title_prefix} (Standard U-Net Baseline)", fontsize=14, fontweight="bold")
            plt.tight_layout()
            out_path = os.path.join(vis_dir, filename)
            plt.savefig(out_path, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"[XUẤT BẢN] Đã lưu ảnh trực quan: {out_path}")

        save_grid(best_cases, "best_matches.png", "Top 3 Best Cases")
        save_grid(avg_cases, "average_matches.png", "Median Performance Cases")
        save_grid(worst_cases, "worst_matches.png", "Difficult / Over-segmentation Cases")

    return True


if __name__ == "__main__":
    evaluate_test_set()
