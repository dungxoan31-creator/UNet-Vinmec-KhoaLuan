"""
Independent Test Set Evaluation & Visualization for Standard U-Net Baseline.
Evaluates model on the held-out 382 test cases of MMOTU Benchmark Protocol 1.
Generates Best, Average, and Worst case visual comparisons.
Author: Nguyen Huu Dung (MIS 65A - NEU)
"""

import os
import sys
import json
import cv2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import torch

# Ensure project root in sys.path
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


def evaluate_test_set(checkpoint_path="checkpoints/baseline_unet_best.pth", test_csv="ai_training/splits/test.csv"):
    print("=" * 70)
    print("       INDEPENDENT TEST SET EVALUATION (382 CASES HELD-OUT)       ")
    print("=" * 70)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[DEVICE] Evaluation Device: {device}")

    # 1. Load Model
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    if not os.path.exists(checkpoint_path):
        print(f"[ERROR] Checkpoint not found: {checkpoint_path}")
        return False

    state_dict = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(state_dict)
    model.eval()
    print(f"[MODEL] Loaded weights from: {checkpoint_path}")

    # 2. Load Test Manifest
    df = pd.read_csv(test_csv)
    print(f"[DATA] Total Held-out Test Cases: {len(df)}")

    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    sample_results = []
    case_predictions = []

    print("[EVAL] Running inference across all 382 test cases...")

    def _resolve_path(p):
        p_str = str(p).replace("\\", "/")
        idx = p_str.find("dataset/dataset/")
        if idx != -1:
            rel = p_str[idx:]
        else:
            rel = p_str
        return os.path.normpath(os.path.join(os.getcwd(), rel))

    with torch.no_grad():
        for idx, row in df.iterrows():
            img_path = _resolve_path(row["image_path"])
            mask_path = _resolve_path(row["mask_path"])
            case_id = row.get("case_id", f"test_case_{idx}")

            img_raw = cv2_imread_unicode(img_path)
            mask_raw = cv2_imread_unicode(mask_path)
            if img_raw is None or mask_raw is None:
                continue

            # Letterbox preprocess
            img_pad, params = preprocessor.letterbox_resize(img_raw, is_mask=False)
            mask_pad, _ = preprocessor.letterbox_resize(mask_raw, is_mask=True)

            img_clahe = preprocessor.clahe.apply(img_pad)
            img_tensor = torch.from_numpy(img_clahe).unsqueeze(0).unsqueeze(0).float() / 255.0
            img_tensor = img_tensor.to(device)

            # Model forward
            logits = model(img_tensor)
            probs = torch.sigmoid(logits)
            pred_mask = (probs > 0.5).squeeze().cpu().numpy().astype(np.uint8)

            # Metrics
            m = compute_sample_clinical_metrics(pred_mask, mask_pad)
            m["case_id"] = case_id
            m["image_path"] = img_path
            m["mask_path"] = mask_path
            sample_results.append(m)

            case_predictions.append({
                "case_id": case_id,
                "dice": m["dice"] if not np.isnan(m["dice"]) else -1.0,
                "iou": m["iou"] if not np.isnan(m["iou"]) else -1.0,
                "recall": m["recall"] if not np.isnan(m["recall"]) else -1.0,
                "img_clahe": img_clahe,
                "gt_mask": mask_pad,
                "pred_mask": pred_mask,
                "raw_shape": img_raw.shape
            })

    # Summary
    summary = compute_dataset_clinical_summary(sample_results)
    print("\n" + "=" * 50)
    print("       INDEPENDENT TEST BENCHMARK RESULTS (MICCAI)       ")
    print("=" * 50)
    print(f"Total Evaluated Cases:   {summary['total_cases_evaluated']}")
    print(f"Lesion Cases:            {summary['lesion_cases_count']}")
    print(f"Normal Cases:            {summary['normal_cases_count']}")
    print(f"Foreground Dice (Mean):  {summary['foreground_dice_mean']:.4f} ± {summary['foreground_dice_std']:.4f}")
    print(f"Foreground IoU (Mean):   {summary['foreground_iou_mean']:.4f} ± {summary['foreground_iou_std']:.4f}")
    print(f"Recall / Sensitivity:    {summary['recall_sensitivity_mean']:.4f}")
    print(f"Precision:               {summary['precision_mean']:.4f}")
    print(f"Specificity (Overall):   {summary['specificity_all_cases']:.4f}")
    print("=" * 50)

    # Save summary json
    os.makedirs("evaluation", exist_ok=True)
    summary_path = "evaluation/baseline_test_metrics.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4)
    print(f"[SAVE] Metrics summary saved to: {summary_path}")

    # Generate Visualizations (Best 4, Average 4, Worst 4)
    valid_lesion_cases = [c for c in case_predictions if c["dice"] >= 0]
    valid_lesion_cases.sort(key=lambda x: x["dice"], reverse=True)

    if len(valid_lesion_cases) >= 12:
        best_cases = valid_lesion_cases[:4]
        mid_idx = len(valid_lesion_cases) // 2
        avg_cases = valid_lesion_cases[mid_idx - 2 : mid_idx + 2]
        worst_cases = valid_lesion_cases[-4:]

        groups = [
            ("best_matches", "Best Match Cases (High Dice)", best_cases),
            ("average_matches", "Average Match Cases (Median Dice)", avg_cases),
            ("worst_matches", "Challenging / Low Contrast Cases", worst_cases)
        ]

        vis_dir = "evaluation/baseline_visualizations"
        os.makedirs(vis_dir, exist_ok=True)

        for group_key, title, cases in groups:
            fig, axes = plt.subplots(len(cases), 4, figsize=(16, 4 * len(cases)))
            for i, c in enumerate(cases):
                # 1. CLAHE Image
                axes[i, 0].imshow(c["img_clahe"], cmap="gray")
                axes[i, 0].set_title(f"{c['case_id']}\nPreprocessed Image", fontsize=10)
                axes[i, 0].axis("off")

                # 2. Ground Truth
                axes[i, 1].imshow(c["gt_mask"], cmap="gray")
                axes[i, 1].set_title("Ground Truth Mask", fontsize=10)
                axes[i, 1].axis("off")

                # 3. Model Prediction
                axes[i, 2].imshow(c["pred_mask"], cmap="gray")
                axes[i, 2].set_title(f"Baseline U-Net\nDice: {c['dice']:.4f} | IoU: {c['iou']:.4f}", fontsize=10)
                axes[i, 2].axis("off")

                # 4. Contour Overlay (GT = Green, Pred = Red)
                overlay = cv2.cvtColor(c["img_clahe"], cv2.COLOR_GRAY2RGB)
                gt_cnts, _ = cv2.findContours(c["gt_mask"], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                pred_cnts, _ = cv2.findContours(c["pred_mask"], cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(overlay, gt_cnts, -1, (0, 255, 0), 2)   # Green for Ground Truth
                cv2.drawContours(overlay, pred_cnts, -1, (255, 0, 0), 2) # Red for Prediction

                axes[i, 3].imshow(overlay)
                axes[i, 3].set_title("Contour Comparison\n(Green=GT, Red=Pred)", fontsize=10)
                axes[i, 3].axis("off")

            plt.suptitle(title, fontsize=14, y=1.01)
            plt.tight_layout()
            out_file = os.path.join(vis_dir, f"{group_key}.png")
            plt.savefig(out_file, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"[VIS] Saved visualization grid: {out_file}")

    print("=" * 70)
    return True


if __name__ == "__main__":
    evaluate_test_set()
