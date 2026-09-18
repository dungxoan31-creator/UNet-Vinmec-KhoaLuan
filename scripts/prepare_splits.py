"""
Script chuẩn hóa và trích xuất tập dữ liệu Train / Validation / Test theo Patient ID.
Nguồn dữ liệu: dataset/vinmec_ovarian/metadata/kltn_ground_truth_307.csv
Đầu ra: ai_training/splits/train.csv, val.csv, test.csv, de_cuong_split_manifest.json
Cam kết: Triệt tiêu 100% rò rỉ dữ liệu giữa các tập (Zero Data Leakage).
"""

import os
import sys
import json
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    print("=" * 70)
    print("   BƯỚC 1 & 2: THIẾT LẬP PHÂN CHIA TẬP DỮ LIỆU THEO PATIENT ID")
    print("=" * 70)

    meta_file = "dataset/vinmec_ovarian/metadata/kltn_ground_truth_307.csv"
    if not os.path.exists(meta_file):
        print(f"[ERROR] Không tìm thấy metadata: {meta_file}")
        sys.exit(1)

    df = pd.read_csv(meta_file)
    print(f"[1] Tổng số bản ghi Ground Truth nạp được: {len(df)}")
    print(f"[2] Số bệnh nhân duy nhất: {df['patient_id'].nunique()}")
    print(f"[3] Số ca Empty Mask (u nang/buồng trứng bình thường): {(df['is_empty_mask'] == True).sum()}")

    # Kiểm tra đường dẫn file thực tế
    missing_imgs = 0
    missing_masks = 0
    for _, row in df.iterrows():
        img_p = row['image_path'].replace('\\', '/')
        mask_p = row['mask_path'].replace('\\', '/')
        if not os.path.exists(img_p):
            missing_imgs += 1
        if not os.path.exists(mask_p):
            missing_masks += 1

    print(f"[4] Kiểm tra tính nguyên vẹn: Thiếu ảnh={missing_imgs}, Thiếu mask={missing_masks}")
    assert missing_imgs == 0 and missing_masks == 0, "Dữ liệu bị thiếu file trên đĩa!"

    # Tách train, val, test
    train_df = df[df['split'] == 'TRAIN'].copy()
    val_df = df[df['split'] == 'VAL'].copy()
    test_df = df[df['split'] == 'TEST'].copy()

    # Kiểm tra Zero Leakage
    train_patients = set(train_df['patient_id'].unique())
    val_patients = set(val_df['patient_id'].unique())
    test_patients = set(test_df['patient_id'].unique())

    leak_train_val = train_patients.intersection(val_patients)
    leak_train_test = train_patients.intersection(test_patients)
    leak_val_test = val_patients.intersection(test_patients)

    print("\n--- KIỂM ĐỊNH RÒ RỈ DỮ LIỆU (PATIENT LEAKAGE AUDIT) ---")
    print(f"Trùng Train <-> Val: {len(leak_train_val)} bệnh nhân")
    print(f"Trùng Train <-> Test: {len(leak_train_test)} bệnh nhân")
    print(f"Trùng Val <-> Test: {len(leak_val_test)} bệnh nhân")

    assert len(leak_train_val) == 0, "Phát hiện rò rỉ giữa Train và Val!"
    assert len(leak_train_test) == 0, "Phát hiện rò rỉ giữa Train và Test!"
    assert len(leak_val_test) == 0, "Phát hiện rò rỉ giữa Val và Test!"
    print("[XÁC NHẬN] ZERO DATA LEAKAGE: 100% bệnh nhân độc lập giữa 3 tập!")

    # Lưu các file CSV
    out_dir = "ai_training/splits"
    os.makedirs(out_dir, exist_ok=True)

    train_path = os.path.join(out_dir, "train.csv")
    val_path = os.path.join(out_dir, "val.csv")
    test_path = os.path.join(out_dir, "test.csv")
    gt_all_path = os.path.join(out_dir, "kltn_ground_truth_307.csv")

    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)
    test_df.to_csv(test_path, index=False)
    df.to_csv(gt_all_path, index=False)

    print(f"\n[XUẤT BẢN] Đã lưu {train_path}: {len(train_df)} ảnh ({len(train_patients)} bệnh nhân, {(train_df['is_empty_mask']==True).sum()} empty)")
    print(f"[XUẤT BẢN] Đã lưu {val_path}: {len(val_df)} ảnh ({len(val_patients)} bệnh nhân, {(val_df['is_empty_mask']==True).sum()} empty)")
    print(f"[XUẤT BẢN] Đã lưu {test_path}: {len(test_df)} ảnh ({len(test_patients)} bệnh nhân, {(test_df['is_empty_mask']==True).sum()} empty)")

    # Lưu manifest
    manifest_data = {
        "title": "KLTN Ovarian Ultrasound Dataset Splits (De Cuong So Bo)",
        "clinical_site": "Vinmec Times City International Hospital",
        "author": "Nguyen Huu Dung (MIS 65A - NEU)",
        "supervisor": "ThS. Tran Thanh Hai",
        "random_seed": 42,
        "table_1_metrics": {
            "total_images_collected": 1387,
            "images_with_initial_masks": 417,
            "ground_truth_images_verified": 307,
            "unique_patients_ground_truth": 185,
            "empty_masks_in_ground_truth": 35
        },
        "ground_truth_patient_split": {
            "train": {
                "patients": len(train_patients),
                "images": len(train_df),
                "empty_masks": int((train_df['is_empty_mask'] == True).sum()),
                "percentage_images": round(len(train_df) / len(df) * 100, 2),
                "file": "ai_training/splits/train.csv"
            },
            "validation": {
                "patients": len(val_patients),
                "images": len(val_df),
                "empty_masks": int((val_df['is_empty_mask'] == True).sum()),
                "percentage_images": round(len(val_df) / len(df) * 100, 2),
                "file": "ai_training/splits/val.csv"
            },
            "test": {
                "patients": len(test_patients),
                "images": len(test_df),
                "empty_masks": int((test_df['is_empty_mask'] == True).sum()),
                "percentage_images": round(len(test_df) / len(df) * 100, 2),
                "file": "ai_training/splits/test.csv"
            }
        },
        "zero_leakage_verified": True
    }

    manifest_file = os.path.join(out_dir, "de_cuong_split_manifest.json")
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)

    print(f"[XUẤT BẢN] Đã lưu manifest phân chia: {manifest_file}")
    print("=" * 70)
    print("   HOÀN THÀNH XUẤT SẮC BƯỚC 1 & 2: DỮ LIỆU ĐƯỢC NIÊM PHONG & CHIA SẠCH")
    print("=" * 70)

if __name__ == "__main__":
    main()
