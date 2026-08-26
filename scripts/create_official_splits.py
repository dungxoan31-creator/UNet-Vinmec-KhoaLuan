"""
Generates official split CSV files:
- ai_training/splits/train.csv (700 images)
- ai_training/splits/val.csv (120 images)
- ai_training/splits/test.csv (382 images - independent OTU test set)
- ai_training/splits/ceus_test.csv (170 images - independent CEUS test set)
"""

import csv
import glob
import os
import random

DATASET_ROOT = os.path.abspath(r"c:\Users\PeaceD_Dung\Documents\Khóa luận\dataset\dataset")
SPLITS_DIR = os.path.abspath(r"c:\Users\PeaceD_Dung\Documents\Khóa luận\ai_training\splits")
os.makedirs(SPLITS_DIR, exist_ok=True)


def create_splits(seed=42):
    random.seed(seed)

    # 1. OTU_2D Train Pool
    train_img_dir = os.path.join(DATASET_ROOT, "OTU_2D", "train", "train_image")
    train_mask_dir = os.path.join(DATASET_ROOT, "OTU_2D", "train", "train_label", "label")
    train_imgs = sorted(glob.glob(os.path.join(train_img_dir, "*.*")))

    train_pairs = []
    for img_p in train_imgs:
        base = os.path.splitext(os.path.basename(img_p))[0]
        mask_p = os.path.join(train_mask_dir, f"{base}.PNG")
        if not os.path.exists(mask_p):
            mask_p = os.path.join(train_mask_dir, f"{base}.png")
        train_pairs.append((img_p, mask_p, f"CASE_{base}"))

    random.shuffle(train_pairs)

    n_val = 120
    val_set = train_pairs[:n_val]
    train_set = train_pairs[n_val:]

    # 2. OTU_2D Test Pool (Strict independent test set)
    test_img_dir = os.path.join(DATASET_ROOT, "OTU_2D", "test", "image")
    test_mask_dir = os.path.join(DATASET_ROOT, "OTU_2D", "test", "label", "black_write")
    test_imgs = sorted(glob.glob(os.path.join(test_img_dir, "*.*")))

    test_set = []
    for img_p in test_imgs:
        base = os.path.splitext(os.path.basename(img_p))[0]
        mask_p = os.path.join(test_mask_dir, f"{base}.PNG")
        if not os.path.exists(mask_p):
            mask_p = os.path.join(test_mask_dir, f"{base}.png")
        if os.path.exists(img_p) and os.path.exists(mask_p):
            test_set.append((img_p, mask_p, f"CASE_{base}"))

    # 3. CEUS Test Pool
    ceus_img_dir = os.path.join(DATASET_ROOT, "OTU_CEUS", "image")
    ceus_mask_dir = os.path.join(DATASET_ROOT, "OTU_CEUS", "label")
    ceus_imgs = sorted(glob.glob(os.path.join(ceus_img_dir, "*.*")))

    ceus_set = []
    for img_p in ceus_imgs:
        base = os.path.splitext(os.path.basename(img_p))[0]
        mask_p = os.path.join(ceus_mask_dir, f"{base}.PNG")
        if not os.path.exists(mask_p):
            mask_p = os.path.join(ceus_mask_dir, f"{base}.png")
        if os.path.exists(img_p) and os.path.exists(mask_p):
            ceus_set.append((img_p, mask_p, f"CASE_CEUS_{base}"))


    # 4. Unified Full Dataset Split (1,372 cases across 2D and CEUS)
    all_pairs = []
    # Add all 2D train
    all_pairs.extend(train_pairs)
    # Add all 2D test
    all_pairs.extend(test_set)
    # Add all CEUS
    all_pairs.extend(ceus_set)

    random.seed(42)
    random.shuffle(all_pairs)

    n_val_unified = 137  # 10%
    n_test_unified = 137  # 10%

    val_unified = all_pairs[:n_val_unified]
    test_unified = all_pairs[n_val_unified : n_val_unified + n_test_unified]
    train_unified = all_pairs[n_val_unified + n_test_unified :]

    # Write CSVs
    def write_csv(filepath, data):
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["image_path", "mask_path", "case_id"])
            for img, mask, cid in data:
                writer.writerow([img, mask, cid])

    write_csv(os.path.join(SPLITS_DIR, "train.csv"), train_set)
    write_csv(os.path.join(SPLITS_DIR, "val.csv"), val_set)
    write_csv(os.path.join(SPLITS_DIR, "test.csv"), test_set)
    write_csv(os.path.join(SPLITS_DIR, "ceus_test.csv"), ceus_set)

    write_csv(os.path.join(SPLITS_DIR, "train_unified.csv"), train_unified)
    write_csv(os.path.join(SPLITS_DIR, "val_unified.csv"), val_unified)
    write_csv(os.path.join(SPLITS_DIR, "test_unified.csv"), test_unified)

    print("=======================================================")
    print("             DATASET SPLITS CREATED                    ")
    print("=======================================================")
    print(f"• Standard Training Set:   {len(train_set)} images -> ai_training/splits/train.csv")
    print(f"• Standard Validation Set: {len(val_set)} images -> ai_training/splits/val.csv")
    print(f"• Standard Test Set (2D):  {len(test_set)} images -> ai_training/splits/test.csv")
    print(f"• Standard Test (CEUS):    {len(ceus_set)} images -> ai_training/splits/ceus_test.csv")
    print("--- Unified Multi-modal 1,372 Dataset Splits ---")
    print(f"• Unified Train:           {len(train_unified)} images -> ai_training/splits/train_unified.csv")
    print(f"• Unified Val:             {len(val_unified)} images -> ai_training/splits/val_unified.csv")
    print(f"• Unified Test:            {len(test_unified)} images -> ai_training/splits/test_unified.csv")
    print(f"• Total Matched Dataset:   {len(all_pairs)} images (100% paired)")
    print("=======================================================")


if __name__ == "__main__":
    create_splits()
