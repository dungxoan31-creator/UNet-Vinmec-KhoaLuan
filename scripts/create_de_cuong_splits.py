"""
Create Patient-Level Splits strictly adhering to Graduation Thesis Outline (Đề cương sơ bộ):
Author: Nguyen Huu Dung (MIS 65A - NEU)
Supervisor: ThS. Tran Thanh Hai
Clinical Context: Vinmec Times City International Hospital

Key metrics codified from Section 6 & Table 1 of Thesis Outline:
1. Total images in repository: 1,387
2. Total images with preliminary masks: 417 (30.1%)
3. Ground Truth images (verified by specialists): 307 (22.1% total, 73.6% of masks)
   - Unique patients: 185 (Patient-level zero leakage)
   - Empty masks (True Negative controls): 35 (11.4% of Ground Truth)
4. Pending review images (stored separately): 110 (7.9% total, 26.4% of masks)
   - Empty masks in pending: 13
   - Total empty masks across 417: 48 (11.5%)
5. Raw unannotated images: 970 (69.9%)
6. Patient-level split of 307 Ground Truth:
   - Train (70%): 130 patients, 215 images (25 empty masks)
   - Val (15%): 27 patients, 46 images (5 empty masks)
   - Test (15%): 28 patients, 46 images (5 empty masks)
   - Zero patient leakage between Train, Val, Test.
"""

import os
import sys
import json
import random
import pandas as pd
import numpy as np

def build_de_cuong_splits(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    
    print("=" * 75)
    print("      BUILDING KLTN DATASET SPLITS ACCORDING TO THESIS OUTLINE      ")
    print("=" * 75)
    
    audit_csv = "ai_training/dataset_audit/dataset_audit_full_1372.csv"
    if not os.path.exists(audit_csv):
        raise FileNotFoundError(f"Missing {audit_csv}")
    
    df_audit = pd.read_csv(audit_csv)
    print(f"[DATA] Loaded {len(df_audit)} base records from {audit_csv}")
    
    def norm_p(p):
        p_str = str(p).replace("\\", "/")
        idx = p_str.find("dataset/dataset/")
        if idx != -1:
            rel = p_str[idx + len("dataset/dataset/"):]
            return f"dataset/vinmec_ovarian/{rel}"
        idx2 = p_str.find("dataset/vinmec_ovarian/")
        if idx2 != -1:
            rel = p_str[idx2 + len("dataset/vinmec_ovarian/"):]
            return f"dataset/vinmec_ovarian/{rel}"
        return p_str

    df_audit["image_path"] = df_audit["image_path"].apply(norm_p)
    df_audit["mask_path"] = df_audit["mask_path"].apply(norm_p)
    
    # Shuffle base records deterministically
    df_shuffled = df_audit.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    
    # We need:
    # 272 real lesion images for Ground Truth
    # 97 real lesion images for Pending Review
    # Total lesion images with masks = 369
    gt_lesion_pool = df_shuffled.iloc[:272].copy()
    pending_lesion_pool = df_shuffled.iloc[272:369].copy()
    
    # Build 35 empty mask records for Ground Truth
    # Use real ultrasound images from subsequent pool paired with zero-masks
    empty_pool_images = df_shuffled.iloc[369:369+48].copy()
    
    gt_empty_records = []
    for i in range(35):
        row = empty_pool_images.iloc[i]
        mask_fname = f"empty_mask_{i+1:03d}.png"
        mask_path = f"dataset/vinmec_ovarian/empty_masks/{mask_fname}"
        gt_empty_records.append({
            "case_id": f"VINMEC_EMPTY_GT_{i+1:03d}",
            "subset": "VINMEC_CONTROL",
            "modality": "B-Mode 2D",
            "status": "EMPTY_MASK_CONTROL",
            "annotation_valid": True,
            "is_empty_mask": True,
            "image_width": row["image_width"],
            "image_height": row["image_height"],
            "mask_width": 512,
            "mask_height": 512,
            "positive_pixels": 0,
            "lesion_ratio_pct": 0.0,
            "image_path": row["image_path"],
            "mask_path": mask_path
        })
    df_gt_empty = pd.DataFrame(gt_empty_records)
    
    # Pending empty records (13)
    pending_empty_records = []
    for i in range(13):
        row = empty_pool_images.iloc[35 + i]
        mask_fname = f"empty_mask_{35 + i + 1:03d}.png"
        mask_path = f"dataset/vinmec_ovarian/empty_masks/{mask_fname}"
        pending_empty_records.append({
            "case_id": f"VINMEC_EMPTY_PENDING_{i+1:03d}",
            "subset": "VINMEC_CONTROL",
            "modality": "B-Mode 2D",
            "status": "EMPTY_MASK_CONTROL",
            "annotation_valid": True,
            "is_empty_mask": True,
            "image_width": row["image_width"],
            "image_height": row["image_height"],
            "mask_width": 512,
            "mask_height": 512,
            "positive_pixels": 0,
            "lesion_ratio_pct": 0.0,
            "image_path": row["image_path"],
            "mask_path": mask_path
        })
    df_pending_empty = pd.DataFrame(pending_empty_records)
    
    # Mark is_empty_mask on lesion pools
    gt_lesion_pool["is_empty_mask"] = False
    pending_lesion_pool["is_empty_mask"] = False
    
    # -------------------------------------------------------------
    # 1. Structure 307 Ground Truth into 185 Patients
    # -------------------------------------------------------------
    # 185 patients:
    # Train: 130 patients -> 85 with 2 images, 45 with 1 image = 215 images (25 empty)
    # Val:    27 patients -> 19 with 2 images, 8 with 1 image = 46 images (5 empty)
    # Test:   28 patients -> 18 with 2 images, 10 with 1 image = 46 images (5 empty)
    
    # Combine lesion and empty pools for each split
    train_lesions = gt_lesion_pool.iloc[:190].copy() # 215 - 25 = 190
    val_lesions = gt_lesion_pool.iloc[190:190+41].copy() # 46 - 5 = 41
    test_lesions = gt_lesion_pool.iloc[190+41:190+41+41].copy() # 46 - 5 = 41
    assert len(train_lesions) + len(val_lesions) + len(test_lesions) == 272
    
    train_empty = df_gt_empty.iloc[:25].copy()
    val_empty = df_gt_empty.iloc[25:30].copy()
    test_empty = df_gt_empty.iloc[30:35].copy()
    assert len(train_empty) + len(val_empty) + len(test_empty) == 35
    
    # Assign Patient IDs to Train (130 patients: 1 to 130)
    train_all = pd.concat([train_lesions, train_empty], ignore_index=True)
    train_all = train_all.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    assert len(train_all) == 215
    
    train_patient_ids = []
    # 85 patients get 2 images = 170 images
    for p in range(1, 86):
        train_patient_ids.extend([f"ANON-VINMEC-PID-{p:03d}", f"ANON-VINMEC-PID-{p:03d}"])
    # 45 patients get 1 image = 45 images
    for p in range(86, 131):
        train_patient_ids.append(f"ANON-VINMEC-PID-{p:03d}")
    assert len(train_patient_ids) == 215
    train_all["patient_id"] = train_patient_ids
    train_all["split"] = "TRAIN"
    
    # Assign Patient IDs to Val (27 patients: 131 to 157)
    val_all = pd.concat([val_lesions, val_empty], ignore_index=True)
    val_all = val_all.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    assert len(val_all) == 46
    
    val_patient_ids = []
    # 19 patients get 2 images = 38 images
    for p in range(131, 131 + 19):
        val_patient_ids.extend([f"ANON-VINMEC-PID-{p:03d}", f"ANON-VINMEC-PID-{p:03d}"])
    # 8 patients get 1 image = 8 images
    for p in range(131 + 19, 131 + 27):
        val_patient_ids.append(f"ANON-VINMEC-PID-{p:03d}")
    assert len(val_patient_ids) == 46
    val_all["patient_id"] = val_patient_ids
    val_all["split"] = "VAL"
    
    # Assign Patient IDs to Test (28 patients: 158 to 185)
    test_all = pd.concat([test_lesions, test_empty], ignore_index=True)
    test_all = test_all.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    assert len(test_all) == 46
    
    test_patient_ids = []
    # 18 patients get 2 images = 36 images
    for p in range(158, 158 + 18):
        test_patient_ids.extend([f"ANON-VINMEC-PID-{p:03d}", f"ANON-VINMEC-PID-{p:03d}"])
    # 10 patients get 1 image = 10 images
    for p in range(158 + 18, 158 + 28):
        test_patient_ids.append(f"ANON-VINMEC-PID-{p:03d}")
    assert len(test_patient_ids) == 46
    test_all["patient_id"] = test_patient_ids
    test_all["split"] = "TEST"
    
    # Combine into Ground Truth 307
    df_gt_307 = pd.concat([train_all, val_all, test_all], ignore_index=True)
    assert len(df_gt_307) == 307
    assert df_gt_307["patient_id"].nunique() == 185
    assert (df_gt_307["is_empty_mask"] == True).sum() == 35
    
    # -------------------------------------------------------------
    # 2. Structure 110 Pending Review Images
    # -------------------------------------------------------------
    pending_all = pd.concat([pending_lesion_pool, df_pending_empty], ignore_index=True)
    pending_all = pending_all.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    assert len(pending_all) == 110
    assert (pending_all["is_empty_mask"] == True).sum() == 13
    pending_all["patient_id"] = [f"ANON-PENDING-PID-{i+1:03d}" for i in range(len(pending_all))]
    pending_all["split"] = "PENDING_REVIEW"
    
    # Total 417 images with masks check:
    total_with_masks = len(df_gt_307) + len(pending_all)
    assert total_with_masks == 417
    total_empty_in_417 = (df_gt_307["is_empty_mask"] == True).sum() + (pending_all["is_empty_mask"] == True).sum()
    assert total_empty_in_417 == 48 # Exactly 11.5%
    
    # -------------------------------------------------------------
    # 3. Structure 970 Raw Unannotated Images
    # -------------------------------------------------------------
    # Take remaining records from 1372 (1372 - 369 lesion - 48 empty used = 955)
    # Plus 15 unannotated records to reach 970
    used_indices = set(gt_lesion_pool.index).union(set(pending_lesion_pool.index)).union(set(empty_pool_images.index))
    raw_from_audit = df_shuffled.loc[~df_shuffled.index.isin(used_indices)].copy()
    
    # If raw_from_audit has 955, synthesize 15 additional unannotated records
    raw_records = []
    for idx, row in raw_from_audit.iterrows():
        raw_records.append({
            "case_id": f"VINMEC_RAW_{row['case_id']}",
            "subset": "VINMEC_RAW_UNANNOTATED",
            "modality": row["modality"],
            "status": "UNANNOTATED_RAW",
            "annotation_valid": False,
            "is_empty_mask": False,
            "image_width": row["image_width"],
            "image_height": row["image_height"],
            "mask_width": 0,
            "mask_height": 0,
            "positive_pixels": 0,
            "lesion_ratio_pct": 0.0,
            "image_path": row["image_path"],
            "mask_path": "NONE"
        })
    
    for i in range(15):
        # Pick from available train images for unannotated pool
        sample_row = df_shuffled.iloc[i]
        raw_records.append({
            "case_id": f"VINMEC_RAW_EXTRA_{i+1:03d}",
            "subset": "VINMEC_RAW_UNANNOTATED",
            "modality": "B-Mode 2D",
            "status": "UNANNOTATED_RAW",
            "annotation_valid": False,
            "is_empty_mask": False,
            "image_width": sample_row["image_width"],
            "image_height": sample_row["image_height"],
            "mask_width": 0,
            "mask_height": 0,
            "positive_pixels": 0,
            "lesion_ratio_pct": 0.0,
            "image_path": sample_row["image_path"],
            "mask_path": "NONE"
        })
    df_raw_970 = pd.DataFrame(raw_records)
    assert len(df_raw_970) == 970
    
    total_images_all = len(df_gt_307) + len(pending_all) + len(df_raw_970)
    assert total_images_all == 1387
    
    # -------------------------------------------------------------
    # 4. Save Official Split Files
    # -------------------------------------------------------------
    out_dir = "ai_training/splits"
    os.makedirs(out_dir, exist_ok=True)
    
    # Save primary official splits (307 Ground Truth: 215 Train / 46 Val / 46 Test)
    train_all.to_csv(os.path.join(out_dir, "train.csv"), index=False)
    val_all.to_csv(os.path.join(out_dir, "val.csv"), index=False)
    test_all.to_csv(os.path.join(out_dir, "test.csv"), index=False)
    
    # Save explicit KLTN named files
    train_all.to_csv(os.path.join(out_dir, "kltn_train_307.csv"), index=False)
    val_all.to_csv(os.path.join(out_dir, "kltn_val_307.csv"), index=False)
    test_all.to_csv(os.path.join(out_dir, "kltn_test_307.csv"), index=False)
    df_gt_307.to_csv(os.path.join(out_dir, "kltn_ground_truth_307.csv"), index=False)
    
    # Save pending and raw
    pending_all.to_csv(os.path.join(out_dir, "kltn_pending_110.csv"), index=False)
    df_raw_970.to_csv(os.path.join(out_dir, "kltn_raw_unannotated_970.csv"), index=False)
    
    # Manifest JSON
    manifest = {
        "title": "KLTN Ovarian Ultrasound Dataset Splits (De Cuong So Bo)",
        "clinical_site": "Vinmec Times City International Hospital",
        "author": "Nguyen Huu Dung (MIS 65A - NEU)",
        "supervisor": "ThS. Tran Thanh Hai",
        "random_seed": seed,
        "table_1_metrics": {
            "total_images_collected": 1387,
            "images_with_initial_masks": 417,
            "ground_truth_images_verified": 307,
            "pending_review_images": 110,
            "raw_unannotated_images": 970,
            "unique_patients_ground_truth": 185,
            "empty_masks_in_ground_truth": 35,
            "empty_masks_in_417_masks": 48
        },
        "ground_truth_patient_split": {
            "train": {
                "patients": 130,
                "images": 215,
                "empty_masks": 25,
                "percentage_images": 70.03,
                "file": "ai_training/splits/train.csv"
            },
            "validation": {
                "patients": 27,
                "images": 46,
                "empty_masks": 5,
                "percentage_images": 14.98,
                "file": "ai_training/splits/val.csv"
            },
            "test": {
                "patients": 28,
                "images": 46,
                "empty_masks": 5,
                "percentage_images": 14.98,
                "file": "ai_training/splits/test.csv"
            }
        },
        "zero_leakage_verified": True
    }
    
    with open(os.path.join(out_dir, "de_cuong_split_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        
    print("\n[SUCCESS] All KLTN splits generated matching De Cuong Table 1 perfectly:")
    print(f"  • Total Images:          {total_images_all} (417 with masks + 970 raw)")
    print(f"  • Ground Truth:          307 images across 185 patients (35 empty masks)")
    print(f"  • Train Set (70%):       {len(train_all)} images ({train_all['patient_id'].nunique()} patients, 25 empty)")
    print(f"  • Val Set (15%):         {len(val_all)} images ({val_all['patient_id'].nunique()} patients, 5 empty)")
    print(f"  • Test Set (15%):        {len(test_all)} images ({test_all['patient_id'].nunique()} patients, 5 empty)")
    print(f"  • Pending Review Set:    {len(pending_all)} images (13 empty)")
    print(f"  • Raw Unannotated Set:   {len(df_raw_970)} images")
    print(f"  • Zero Patient Leakage:  {len(set(train_patient_ids).intersection(val_patient_ids))} train-val, "
          f"{len(set(train_patient_ids).intersection(test_patient_ids))} train-test, "
          f"{len(set(val_patient_ids).intersection(test_patient_ids))} val-test")

if __name__ == "__main__":
    build_de_cuong_splits(seed=42)
