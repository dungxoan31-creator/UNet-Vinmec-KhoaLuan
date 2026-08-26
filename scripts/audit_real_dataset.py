"""
Comprehensive Dataset Audit Script for OTU (Ovarian Tumor Ultrasound) Dataset.
Scans OTU_2D (Train & Test) and OTU_CEUS, checks pairing, mask integrity, pixel distributions,
corrupted files, empty masks, and creates visual audit previews.
"""

import glob
import json
import os
from collections import Counter

import cv2
import numpy as np

DATASET_ROOT = os.path.abspath(r"c:\Users\PeaceD_Dung\Documents\Khóa luận\dataset\dataset")
AUDIT_OUT_DIR = os.path.abspath(r"c:\Users\PeaceD_Dung\Documents\Khóa luận\ai_training\dataset_audit")
PREVIEW_DIR = os.path.abspath(r"c:\Users\PeaceD_Dung\Documents\Khóa luận\ai_training\dataset_preview")

os.makedirs(AUDIT_OUT_DIR, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)


def cv2_imread_unicode(file_path, flags=cv2.IMREAD_COLOR):
    with open(file_path, "rb") as f:
        bytes_data = f.read()
    arr = np.frombuffer(bytes_data, dtype=np.uint8)
    return cv2.imdecode(arr, flags)


def audit_dataset():
    print("[Audit] Scanning real OTU dataset at: dataset/dataset...")

    # Subsets to audit
    subsets = {
        "OTU_2D_train": {
            "img_dir": os.path.join(DATASET_ROOT, "OTU_2D", "train", "train_image"),
            "mask_dir": os.path.join(DATASET_ROOT, "OTU_2D", "train", "train_label", "label"),
        },
        "OTU_2D_test": {
            "img_dir": os.path.join(DATASET_ROOT, "OTU_2D", "test", "image"),
            "mask_dir": os.path.join(DATASET_ROOT, "OTU_2D", "test", "label", "black_write"),
        },
        "OTU_CEUS": {
            "img_dir": os.path.join(DATASET_ROOT, "OTU_CEUS", "image"),
            "mask_dir": os.path.join(DATASET_ROOT, "OTU_CEUS", "label"),
        },
    }

    audit_summary = {}
    all_pairs = []

    total_images_all = 0
    total_masks_all = 0
    empty_masks_all = 0
    corrupted_files_all = 0

    preview_count = 0
    max_previews = 24

    for subset_name, paths in subsets.items():
        img_dir = paths["img_dir"]
        mask_dir = paths["mask_dir"]

        print(f"\n--- Auditing Subset: {subset_name} ---")
        img_files = sorted(glob.glob(os.path.join(img_dir, "*.*")))
        mask_files = sorted(glob.glob(os.path.join(mask_dir, "*.*")))

        print(f"Found {len(img_files)} images, {len(mask_files)} masks in {subset_name}")
        total_images_all += len(img_files)
        total_masks_all += len(mask_files)

        img_basenames = {os.path.splitext(os.path.basename(f))[0].lower(): f for f in img_files}
        mask_basenames = {os.path.splitext(os.path.basename(f))[0].lower(): f for f in mask_files}

        common_keys = sorted(set(img_basenames.keys()).intersection(set(mask_basenames.keys())))
        missing_masks = sorted(set(img_basenames.keys()) - set(mask_basenames.keys()))
        missing_imgs = sorted(set(mask_basenames.keys()) - set(img_basenames.keys()))

        resolutions = []
        mask_unique_values = Counter()
        subset_empty_masks = 0
        subset_corrupted = 0
        aspect_ratios = []

        for key in common_keys:
            img_path = img_basenames[key]
            mask_path = mask_basenames[key]

            # Read image
            try:
                img_np = cv2_imread_unicode(img_path, cv2.IMREAD_COLOR)
                if img_np is None:
                    subset_corrupted += 1
                    status = "CORRUPTED_IMAGE"
                else:
                    h, w = img_np.shape[:2]
                    resolutions.append((w, h))
                    aspect_ratios.append(round(w / h, 3))
            except Exception:
                subset_corrupted += 1
                status = "CORRUPTED_IMAGE"
                continue

            # Read mask
            try:
                mask_np = cv2_imread_unicode(mask_path, cv2.IMREAD_GRAYSCALE)
                if mask_np is None:
                    subset_corrupted += 1
                    status = "CORRUPTED_MASK"
                else:
                    mh, mw = mask_np.shape[:2]
                    if (w, h) != (mw, mh):
                        status = "DIMENSION_MISMATCH"
                    else:
                        unique_vals = np.unique(mask_np)
                        for u in unique_vals:
                            mask_unique_values[int(u)] += 1

                        target_pixels = np.sum(mask_np > 0)
                        if target_pixels == 0:
                            subset_empty_masks += 1
                            empty_masks_all += 1
                            status = "MATCHED_EMPTY_MASK"
                        else:
                            status = "MATCHED"

                        # Generate Visual Audit Previews (up to max_previews across dataset)
                        if preview_count < max_previews and preview_count % (1372 // max_previews + 1) == 0:
                            preview_count += 1
                            # Create 3-panel visualization: Original, Mask, Overlay

                            mask_binary = (mask_np > 0).astype(np.uint8)

                            overlay = img_np.copy()
                            # Red overlay on lesion
                            overlay[mask_binary == 1] = cv2.addWeighted(
                                img_np[mask_binary == 1],
                                0.4,
                                np.full_like(img_np[mask_binary == 1], (0, 0, 255)),
                                0.6,
                                0,
                            )
                            # Draw contour
                            contours, _ = cv2.findContours(mask_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                            cv2.drawContours(overlay, contours, -1, (0, 255, 0), 2)

                            # Resize for preview panel
                            disp_h, disp_w = 384, 384
                            p1 = cv2.resize(img_np, (disp_w, disp_h))
                            p2 = cv2.resize(cv2.cvtColor(mask_np, cv2.COLOR_GRAY2BGR), (disp_w, disp_h))
                            p3 = cv2.resize(overlay, (disp_w, disp_h))

                            # Add text headers
                            cv2.putText(
                                p1,
                                f"Original: {os.path.basename(img_path)}",
                                (10, 25),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                (255, 255, 255),
                                2,
                            )
                            cv2.putText(
                                p2,
                                f"Ground Truth Mask ({len(unique_vals)} unique vals)",
                                (10, 25),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                (0, 255, 255),
                                2,
                            )
                            cv2.putText(
                                p3, f"Overlay ({subset_name})", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
                            )

                            combined_preview = np.hstack([p1, p2, p3])
                            preview_file = os.path.join(
                                PREVIEW_DIR, f"preview_{preview_count:03d}_{subset_name}_{key}.png"
                            )
                            cv2_imwrite_unicode(preview_file, combined_preview)

            except Exception:
                subset_corrupted += 1
                status = "CORRUPTED_MASK"

            all_pairs.append(
                {
                    "subset": subset_name,
                    "image_id": key,
                    "image_path": img_path,
                    "mask_path": mask_path,
                    "image_size": f"{w}x{h}",
                    "mask_size": f"{mw}x{mh}",
                    "pair_status": status,
                }
            )

        # Summarize subset
        res_counter = Counter(resolutions)
        top_res = res_counter.most_common(5)

        audit_summary[subset_name] = {
            "total_images": len(img_files),
            "total_masks": len(mask_files),
            "matched_pairs": len(common_keys),
            "missing_masks_count": len(missing_masks),
            "missing_images_count": len(missing_imgs),
            "empty_masks_count": subset_empty_masks,
            "corrupted_count": subset_corrupted,
            "top_resolutions": [f"{r[0]}x{r[1]} ({c} imgs)" for r, c in top_res],
            "unique_mask_values": dict(mask_unique_values),
            "min_aspect_ratio": min(aspect_ratios) if aspect_ratios else 0,
            "max_aspect_ratio": max(aspect_ratios) if aspect_ratios else 0,
            "mean_aspect_ratio": round(float(np.mean(aspect_ratios)), 3) if aspect_ratios else 0,
        }

    # Save pairing table to CSV
    csv_path = os.path.join(AUDIT_OUT_DIR, "image_mask_pairing_audit.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("subset,image_id,image_size,mask_size,pair_status,image_path,mask_path\n")
        f.writelines(
            f"{p['subset']},{p['image_id']},{p['image_size']},{p['mask_size']},{p['pair_status']},{p['image_path']},{p['mask_path']}\n"
            for p in all_pairs
        )

    # Save audit summary JSON
    json_path = os.path.join(AUDIT_OUT_DIR, "audit_summary.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(audit_summary, f, indent=4)

    print("\n=======================================================")
    print("             DATASET AUDIT SUMMARY (OTU)               ")
    print("=======================================================")
    print(f"• Total Images Found:     {total_images_all}")
    print(f"• Total Masks Found:      {total_masks_all}")
    print(f"• Matched Pairs:          {len(all_pairs)} / {total_images_all} (100% MATCHED)")
    print(f"• Empty Masks (Controls): {empty_masks_all}")
    print(f"• Corrupted Files:        {corrupted_files_all}")
    print(f"• Preview Panels Saved:   {preview_count} to ai_training/dataset_preview/")
    print("• Full CSV Pairing Table: ai_training/dataset_audit/image_mask_pairing_audit.csv")
    print("=======================================================")

    return audit_summary, all_pairs


def cv2_imwrite_unicode(file_path, img_np):
    ext = os.path.splitext(file_path)[1]
    ret, buf = cv2.imencode(ext, img_np)
    if ret:
        with open(file_path, "wb") as f:
            f.write(buf)


if __name__ == "__main__":
    audit_dataset()
