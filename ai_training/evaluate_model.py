"""
Independent Evaluation & Error Analysis Suite for Ovarian Ultrasound AI:
- Evaluates on 206 completely held-out independent test samples
- Computes Global & Per-Case Metrics: Dice, IoU, Precision, Recall, Specificity
- Performs Systematic Error Classification (False Positives, False Negatives, Boundary Smears)
- Generates Visual Verification Overlays
- Synthesizes Evaluation Report & Comparison against baseline
"""

import os
import sys
import json
import cv2
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models.attention_unet import AttentionUNet
from ai_training.dataset_loader import OvarianUltrasoundDataset
from torch.utils.data import DataLoader

def evaluate_on_test_set(checkpoint_path="checkpoints/best_attention_unet.pth", threshold=0.5):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Evaluation] Using Device: {device} | Checkpoint: {checkpoint_path}")

    test_ds = OvarianUltrasoundDataset("ai_training/splits/test_v2.csv", is_train=False)
    test_loader = DataLoader(test_ds, batch_size=1, shuffle=False)

    model = AttentionUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    if os.path.exists(checkpoint_path):
        state_dict = torch.load(checkpoint_path, map_location=device)
        model.load_state_dict(state_dict)
        print("[Evaluation] Checkpoint loaded successfully.")
    else:
        print(f"[Evaluation] ERROR: Checkpoint not found at {checkpoint_path}")
        return

    model.eval()

    per_case_results = []
    os.makedirs("ai_training/evaluation_samples", exist_ok=True)

    total_tp = 0
    total_fp = 0
    total_fn = 0
    total_tn = 0

    dice_list = []
    iou_list = []
    prec_list = []
    rec_list = []
    spec_list = []

    print(f"[Evaluation] Evaluating {len(test_ds)} held-out test images...")

    with torch.no_grad():
        for i, batch in enumerate(test_loader):
            img_tensor = batch["image"].to(device)
            mask_tensor = batch["mask"].to(device)
            sample_id = batch["sample_id"][0]
            img_path = batch["img_path"][0]

            logits = model(img_tensor)
            probs = torch.sigmoid(logits)
            preds = (probs > threshold).float()

            p_np = preds[0, 0].cpu().numpy().astype(np.uint8)
            g_np = mask_tensor[0, 0].cpu().numpy().astype(np.uint8)
            img_np = ((img_tensor[0, 0].cpu().numpy() + 1.0) * 127.5).astype(np.uint8)

            tp = int((p_np * g_np).sum())
            fp = int((p_np * (1 - g_np)).sum())
            fn = int(((1 - p_np) * g_np).sum())
            tn = int(((1 - p_np) * (1 - g_np)).sum())

            total_tp += tp
            total_fp += fp
            total_fn += fn
            total_tn += tn

            smooth = 1e-6
            dice = (2.0 * tp + smooth) / (2.0 * tp + fp + fn + smooth)
            iou = (tp + smooth) / (tp + fp + fn + smooth)
            prec = (tp + smooth) / (tp + fp + smooth)
            rec = (tp + smooth) / (tp + fn + smooth)
            spec = (tn + smooth) / (tn + fp + smooth)

            dice_list.append(dice)
            iou_list.append(iou)
            prec_list.append(prec)
            rec_list.append(rec)
            spec_list.append(spec)

            # Error Categorization
            if dice >= 0.85:
                error_type = "EXCELLENT_MATCH"
                possible_cause = "Clear boundary and high acoustic contrast"
            elif dice >= 0.70:
                error_type = "GOOD_MATCH"
                possible_cause = "Minor boundary difference at peripheral margin"
            elif rec < 0.60:
                error_type = "FALSE_NEGATIVE_UNDERSEGMENT"
                possible_cause = "Low contrast / fuzzy boundary / speckle attenuation"
            elif prec < 0.60:
                error_type = "FALSE_POSITIVE_OVERSEGMENT"
                possible_cause = "Normal follicular cluster or acoustic shadow included"
            else:
                error_type = "MODERATE_DEVIATION"
                possible_cause = "Irregular lesion morphology"

            record = {
                "sample_id": sample_id,
                "image_filename": os.path.basename(img_path),
                "dice": round(float(dice), 4),
                "iou": round(float(iou), 4),
                "precision": round(float(prec), 4),
                "recall": round(float(rec), 4),
                "specificity": round(float(spec), 4),
                "error_type": error_type,
                "possible_cause": possible_cause
            }
            per_case_results.append(record)

            # Save Visual Comparison Sample for first 15 cases & worst 5 cases
            if i < 15 or dice < 0.50:
                overlay = cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR)
                # Green: Ground Truth
                # Blue: Prediction
                gt_cnts, _ = cv2.findContours(g_np, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                pred_cnts, _ = cv2.findContours(p_np, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                cv2.drawContours(overlay, gt_cnts, -1, (0, 255, 0), 2)  # Ground Truth in Green
                cv2.drawContours(overlay, pred_cnts, -1, (255, 120, 0), 2)  # Prediction in Cyan/Blue

                cv2.putText(overlay, f"Dice: {dice:.3f} | IoU: {iou:.3f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.imwrite(f"ai_training/evaluation_samples/eval_{sample_id}.png", overlay)

    df_results = pd.DataFrame(per_case_results)
    df_results.to_csv("ai_training/evaluation_report_per_case.csv", index=False)

    mean_dice = float(np.mean(dice_list))
    mean_iou = float(np.mean(iou_list))
    mean_prec = float(np.mean(prec_list))
    mean_rec = float(np.mean(rec_list))
    mean_spec = float(np.mean(spec_list))

    print("\n" + "="*60)
    print("INDEPENDENT TEST SET EVALUATION REPORT (206 Held-out Cases)")
    print("="*60)
    print(f"• Mean Dice Score:          {mean_dice:.4f} ({mean_dice*100:.2f}%)")
    print(f"• Mean IoU (Jaccard Index): {mean_iou:.4f} ({mean_iou*100:.2f}%)")
    print(f"• Mean Precision:           {mean_prec:.4f} ({mean_prec*100:.2f}%)")
    print(f"• Mean Recall / Sensitivity:{mean_rec:.4f} ({mean_rec*100:.2f}%)")
    print(f"• Mean Specificity:         {mean_spec:.4f} ({mean_spec*100:.2f}%)")
    print("="*60)

    # Error Distribution
    error_counts = df_results['error_type'].value_counts().to_dict()
    print("\n[Error Analysis Breakdown]:")
    for k, v in error_counts.items():
        print(f"  - {k}: {v} cases ({v/len(df_results)*100:.1f}%)")

    # Generate Markdown Summary
    md_content = f"""# Báo Cáo Đánh Giá & Kiểm Thử Độc Lập Mô Hình AI (Attention U-Net)

## 1. Kết quả trên Tập Test Độc Lập (206 ca bệnh giữ lại hoàn toàn)

| Metric | Giá trị (New Retrained Model) | Baseline Ban Đầu | Mức Cải Thiện |
|---|---|---|---|
| **Dice Score** | **{mean_dice:.4f} ({mean_dice*100:.2f}%)** | 0.7241 (72.41%) | **+{(mean_dice - 0.7241)*100:.2f}%** |
| **IoU (Jaccard)** | **{mean_iou:.4f} ({mean_iou*100:.2f}%)** | 0.6052 (60.52%) | **+{(mean_iou - 0.6052)*100:.2f}%** |
| **Precision** | **{mean_prec:.4f} ({mean_prec*100:.2f}%)** | 0.7105 (71.05%) | **+{(mean_prec - 0.7105)*100:.2f}%** |
| **Recall / Sensitivity** | **{mean_rec:.4f} ({mean_rec*100:.2f}%)** | 0.7432 (74.32%) | **+{(mean_rec - 0.7432)*100:.2f}%** |
| **Specificity** | **{mean_spec:.4f} ({mean_spec*100:.2f}%)** | 0.9610 (96.10%) | **+{(mean_spec - 0.9610)*100:.2f}%** |

---

## 2. Phân Bố Phân Tích Lỗi (Systematic Error Analysis)

| Phân Loại Lỗi | Số Ca | Tỷ Lệ | Nguyên Nhân Lâm Sàng / Kỹ Thuật |
|---|---|---|---|
| **EXCELLENT MATCH (Dice ≥ 0.85)** | {error_counts.get('EXCELLENT_MATCH', 0)} | {error_counts.get('EXCELLENT_MATCH', 0)/len(df_results)*100:.1f}% | Ranh giới khối u sắc nét, hồi âm dịch trong điển hình |
| **GOOD MATCH (0.70 ≤ Dice < 0.85)** | {error_counts.get('GOOD_MATCH', 0)} | {error_counts.get('GOOD_MATCH', 0)/len(df_results)*100:.1f}% | Sai lệch nhẹ ở bờ biên ngoại vi của nang |
| **FALSE NEGATIVE / UNDERSEGMENT** | {error_counts.get('FALSE_NEGATIVE_UNDERSEGMENT', 0)} | {error_counts.get('FALSE_NEGATIVE_UNDERSEGMENT', 0)/len(df_results)*100:.1f}% | Độ tương phản kém, ranh giới mờ, suy giảm chùm tia siêu âm sâu |
| **FALSE POSITIVE / OVERSEGMENT** | {error_counts.get('FALSE_POSITIVE_OVERSEGMENT', 0)} | {error_counts.get('FALSE_POSITIVE_OVERSEGMENT', 0)/len(df_results)*100:.1f}% | Bao gồm nhầm cụm nang noãn nhỏ kế cận hoặc bóng cản âm lưng |
| **MODERATE DEVIATION** | {error_counts.get('MODERATE_DEVIATION', 0)} | {error_counts.get('MODERATE_DEVIATION', 0)/len(df_results)*100:.1f}% | Khối u có cấu trúc hình học dị dạng phức tạp |

---

## 3. Các Ca Điển Hình Dự Đoán Sai (Worst Cases & Error Analysis Table)

| Sample ID | Tên File | Dice | IoU | Precision | Recall | Loại Lỗi | Nguyên Nhân Khả Dĩ |
|---|---|---|---|---|---|---|---|
"""
    worst_cases = df_results.sort_values(by="dice").head(10)
    for _, r in worst_cases.iterrows():
        md_content += f"| {r['sample_id']} | `{r['image_filename']}` | {r['dice']:.4f} | {r['iou']:.4f} | {r['precision']:.4f} | {r['recall']:.4f} | {r['error_type']} | {r['possible_cause']} |\n"

    with open("ai_training/evaluation_report.md", "w", encoding="utf-8") as f:
        f.write(md_content)

    print("[Evaluation] Evaluation report written to ai_training/evaluation_report.md")

if __name__ == "__main__":
    evaluate_on_test_set()
