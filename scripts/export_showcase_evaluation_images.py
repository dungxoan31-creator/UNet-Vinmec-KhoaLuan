"""
Export all 24 multi-panel visual comparison artifacts + standalone 4 showcase files into evaluation/
"""

import os
import sys
import numpy as np
import pandas as pd
import cv2
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models.attention_unet import AttentionUNet
from backend.services.preprocessor import UltrasoundPreprocessor


def cv2_imread_unicode(filename, flags=cv2.IMREAD_GRAYSCALE):
    try:
        with open(filename, "rb") as f:
            bytes_data = np.frombuffer(f.read(), dtype=np.uint8)
        return cv2.imdecode(bytes_data, flags)
    except Exception:
        return None


def cv2_imwrite_unicode(filename, img):
    is_success, buf = cv2.imencode(".png", img)
    if is_success:
        with open(filename, "wb") as f:
            f.write(buf)
    return is_success


def export_all():
    eval_dir = os.path.abspath("evaluation")
    os.makedirs(eval_dir, exist_ok=True)

    weights_path = os.path.abspath("ai_training/production_model/model.pth")
    if not os.path.exists(weights_path):
        weights_path = os.path.abspath("checkpoints/best_attention_unet.pth")

    model = AttentionUNet(in_channels=1, num_classes=1, base_filters=32)
    model.load_state_dict(torch.load(weights_path, map_location="cpu"))
    model.eval()

    preprocessor = UltrasoundPreprocessor(target_size=(256, 256))
    df = pd.read_csv("ai_training/evaluation_report_per_case.csv")

    best_df = df.sort_values(by="dice", ascending=False).head(8)
    mid_idx = len(df) // 2
    avg_df = df.sort_values(by="dice", ascending=False).iloc[mid_idx - 4 : mid_idx + 4]
    worst_df = df.sort_values(by="dice", ascending=True).head(8)

    # Also load split csv to get image paths
    split_csv = "ai_training/splits/test_v2.csv"
    df_split = pd.read_csv(split_csv).set_index("case_id")

    def process_and_save(sub_df, prefix):
        for idx, (_, row) in enumerate(sub_df.iterrows()):
            case_id = row["case_id"]
            if case_id not in df_split.index:
                continue
            s_row = df_split.loc[case_id]
            img_path = s_row["image_path"]
            mask_path = s_row["mask_path"]

            img_raw = cv2_imread_unicode(img_path, cv2.IMREAD_GRAYSCALE)
            mask_raw = cv2_imread_unicode(mask_path, cv2.IMREAD_GRAYSCALE) if os.path.exists(mask_path) else np.zeros_like(img_raw)
            if img_raw is None:
                continue
            if mask_raw is None:
                mask_raw = np.zeros_like(img_raw)

            orig_h, orig_w = img_raw.shape[:2]
            mask_bin = (mask_raw > 127).astype(np.uint8)

            padded_img, params = preprocessor.letterbox_resize(img_raw, (256, 256))
            scale = params["scale"]
            pad_x = params["pad_x"]
            pad_y = params["pad_y"]
            new_w = int(orig_w * scale)
            new_h = int(orig_h * scale)

            resized_mask = cv2.resize(mask_bin, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
            target = np.zeros((256, 256), dtype=np.uint8)
            target[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized_mask

            enhanced_img = preprocessor.enhance_contrast_and_denoise(padded_img)
            norm_img = enhanced_img.astype(np.float32) / 255.0
            tensor_img = torch.from_numpy(norm_img).unsqueeze(0).unsqueeze(0)

            with torch.no_grad():
                l_orig = model(tensor_img)
                l_flip = torch.flip(model(torch.flip(tensor_img, dims=[3])), dims=[3])
                p_np = (0.5 * (torch.sigmoid(l_orig) + torch.sigmoid(l_flip))).numpy()[0, 0]

            pred_bin = (p_np >= 0.5).astype(np.uint8)

            raw_img_u8 = (norm_img * 255.0).astype(np.uint8)
            gt_mask_u8 = (target * 255).astype(np.uint8)
            pred_mask_u8 = (pred_bin * 255).astype(np.uint8)

            color_base = cv2.cvtColor(raw_img_u8, cv2.COLOR_GRAY2BGR)
            overlay = color_base.copy()

            pred_bool = pred_bin == 1
            if pred_bool.any():
                overlay[pred_bool] = cv2.addWeighted(
                    color_base[pred_bool], 0.4, np.full_like(color_base[pred_bool], (235, 140, 20)), 0.6, 0
                )

            gt_cnts, _ = cv2.findContours(target.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if gt_cnts:
                cv2.drawContours(overlay, gt_cnts, -1, (0, 255, 0), 2)

            pred_cnts, _ = cv2.findContours(pred_bin.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if pred_cnts:
                cv2.drawContours(overlay, pred_cnts, -1, (0, 255, 255), 2)

            disp_size = (384, 384)
            p1 = cv2.resize(color_base, disp_size)
            p2 = cv2.resize(cv2.cvtColor(gt_mask_u8, cv2.COLOR_GRAY2BGR), disp_size)
            p3 = cv2.resize(cv2.cvtColor(pred_mask_u8, cv2.COLOR_GRAY2BGR), disp_size)
            p4 = cv2.resize(overlay, disp_size)

            dice_val = row["dice"]
            cv2.putText(p1, f"01 ORIGINAL: {case_id}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
            cv2.putText(p2, "02 GROUND TRUTH", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
            cv2.putText(p3, "03 AI PREDICTION", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
            cv2.putText(p4, f"04 OVERLAY (Dice: {dice_val:.3f})", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

            panel = np.hstack([p1, p2, p3, p4])
            fn = os.path.join(eval_dir, f"{prefix}_{idx + 1:02d}_{case_id}_dice_{dice_val:.3f}.png")
            cv2_imwrite_unicode(fn, panel)

            if idx == 0 and prefix == "best_match":
                cv2_imwrite_unicode(os.path.join(eval_dir, "01_original.png"), p1)
                cv2_imwrite_unicode(os.path.join(eval_dir, "02_ground_truth_mask.png"), p2)
                cv2_imwrite_unicode(os.path.join(eval_dir, "03_predicted_mask.png"), p3)
                cv2_imwrite_unicode(os.path.join(eval_dir, "04_overlay.png"), p4)

    process_and_save(best_df, "best_match")
    process_and_save(avg_df, "average_match")
    process_and_save(worst_df, "worst_match")
    print(f"Artifacts exported to {eval_dir}")


if __name__ == "__main__":
    export_all()
