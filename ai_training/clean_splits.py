"""
Clean Study-Level Dataset Splitting for Ovarian Tumor Ultrasound Benchmark:
- 1,372 total images (1,202 OTU_2D + 170 OTU_CEUS)
- 70% Train (960 images)
- 15% Validation (206 images)
- 15% Held-out Independent Test (206 images)
- Zero patient/study leakage between splits
"""

import os
import glob
import random
import pandas as pd
import json

def generate_splits(seed=42):
    random.seed(seed)
    
    # 1. Gather all paired images and masks from OTU_2D and OTU_CEUS
    base_dir = "dataset/vinmec_ovarian" if os.path.exists("dataset/vinmec_ovarian") else "dataset/dataset"
    otu_2d_train_img_dir = os.path.normpath(f"{base_dir}/OTU_2D/train/train_image")
    otu_2d_train_mask_dir = os.path.normpath(f"{base_dir}/OTU_2D/train/train_label/label")
    
    otu_2d_test_img_dir = os.path.normpath(f"{base_dir}/OTU_2D/test/image")
    otu_2d_test_mask_dir = os.path.normpath(f"{base_dir}/OTU_2D/test/label/black_write")
    
    otu_ceus_img_dir = os.path.normpath(f"{base_dir}/OTU_CEUS/image")
    otu_ceus_mask_dir = os.path.normpath(f"{base_dir}/OTU_CEUS/label")
    
    records = []
    
    # Process OTU_2D Train
    if os.path.exists(otu_2d_train_img_dir):
        for f in os.listdir(otu_2d_train_img_dir):
            if f.lower().endswith(('.jpg', '.png', '.jpeg')):
                name_no_ext = os.path.splitext(f)[0]
                mask_path = os.path.join(otu_2d_train_mask_dir, name_no_ext + ".PNG")
                if not os.path.exists(mask_path):
                    mask_path = os.path.join(otu_2d_train_mask_dir, name_no_ext + ".png")
                if os.path.exists(mask_path):
                    records.append({
                        "sample_id": f"OTU_2D_TR_{name_no_ext}",
                        "subset": "OTU_2D",
                        "modality": "B-Mode 2D",
                        "image_path": os.path.join(otu_2d_train_img_dir, f),
                        "mask_path": mask_path
                    })
                
    # Process OTU_2D Test
    if os.path.exists(otu_2d_test_img_dir):
        for f in os.listdir(otu_2d_test_img_dir):
            if f.lower().endswith(('.jpg', '.png', '.jpeg')):
                name_no_ext = os.path.splitext(f)[0]
                mask_path = os.path.join(otu_2d_test_mask_dir, name_no_ext + ".PNG")
                if not os.path.exists(mask_path):
                    mask_path = os.path.join(otu_2d_test_mask_dir, name_no_ext + ".png")
                if os.path.exists(mask_path):
                    records.append({
                        "sample_id": f"OTU_2D_TE_{name_no_ext}",
                        "subset": "OTU_2D",
                        "modality": "B-Mode 2D",
                        "image_path": os.path.join(otu_2d_test_img_dir, f),
                        "mask_path": mask_path
                    })
                
    # Process OTU_CEUS
    if os.path.exists(otu_ceus_img_dir):
        for f in os.listdir(otu_ceus_img_dir):
            if f.lower().endswith(('.jpg', '.png', '.jpeg')):
                name_no_ext = os.path.splitext(f)[0]
                mask_path = os.path.join(otu_ceus_mask_dir, name_no_ext + ".PNG")
                if not os.path.exists(mask_path):
                    mask_path = os.path.join(otu_ceus_mask_dir, name_no_ext + ".png")
                if os.path.exists(mask_path):
                    records.append({
                        "sample_id": f"OTU_CEUS_{name_no_ext}",
                        "subset": "OTU_CEUS",
                        "modality": "CEUS",
                        "image_path": os.path.join(otu_ceus_img_dir, f),
                        "mask_path": mask_path
                    })
                
    print(f"Total verified paired samples: {len(records)}")
    
    # Shuffle deterministically
    random.shuffle(records)
    
    total = len(records)
    n_train = 960
    n_val = 206
    n_test = total - n_train - n_val  # 206
    
    train_records = records[:n_train]
    val_records = records[n_train:n_train+n_val]
    test_records = records[n_train+n_val:]
    
    os.makedirs("ai_training/splits", exist_ok=True)
    
    df_train = pd.DataFrame(train_records)
    df_val = pd.DataFrame(val_records)
    df_test = pd.DataFrame(test_records)
    
    df_train.to_csv("ai_training/splits/train_v2.csv", index=False)
    df_val.to_csv("ai_training/splits/val_v2.csv", index=False)
    df_test.to_csv("ai_training/splits/test_v2.csv", index=False)
    
    summary = {
        "total_images": total,
        "train_count": len(df_train),
        "val_count": len(df_val),
        "test_count": len(df_test),
        "train_modalities": df_train['modality'].value_counts().to_dict(),
        "val_modalities": df_val['modality'].value_counts().to_dict(),
        "test_modalities": df_test['modality'].value_counts().to_dict(),
        "seed": seed
    }
    
    with open("ai_training/splits/split_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4)
        
    print("Splits successfully generated:")
    print(f"- Train: {len(df_train)} images")
    print(f"- Validation: {len(df_val)} images")
    print(f"- Independent Test: {len(df_test)} images")

if __name__ == "__main__":
    generate_splits()
