"""
Create Train / Validation / Test splits only from source-verified patient IDs.
Requires an identity manifest bound to the exact input CSV SHA-256.
Synthetic or unverified patient groups cannot establish patient-level independence.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SPLIT_NAMES = ("TRAIN", "VAL", "TEST")


def validate_patient_split_metadata(df, identity_manifest, source_metadata_sha256):
    """Require explicit source identity evidence and disjoint, complete groups."""
    if not isinstance(identity_manifest, dict) or any(
        identity_manifest.get(field) is not True
        for field in ("source_patient_identity_verified", "patient_ids_verified")
    ) or identity_manifest.get("identity_level") != "patient_verified":
        raise ValueError(
            "Training split creation requires source-verified patient identity evidence."
        )
    if identity_manifest.get("synthetic_patient_metadata") is True or identity_manifest.get(
        "clinical_metadata_is_synthetic"
    ) is True:
        raise ValueError("Synthetic patient metadata cannot establish patient-level independence.")
    if not str(identity_manifest.get("identity_source") or "").strip() or not str(
        identity_manifest.get("identity_evidence_reference") or ""
    ).strip():
        raise ValueError("Identity evidence must name its source and verification reference.")
    if identity_manifest.get("metadata_sha256") != source_metadata_sha256:
        raise ValueError("Identity manifest metadata SHA-256 does not match the input CSV.")

    required_columns = {
        "case_id", "patient_id", "split", "image_path", "mask_path", "is_empty_mask"
    }
    if not required_columns.issubset(df.columns):
        raise ValueError("Metadata is missing required case, patient, split or file columns.")
    if df.empty:
        raise ValueError("Metadata must contain at least one sample.")

    normalized = df.copy()
    case_ids = normalized["case_id"].astype("string").str.strip()
    patient_ids = normalized["patient_id"].astype("string").str.strip()
    splits = normalized["split"].astype("string").str.strip().str.upper()
    image_paths = normalized["image_path"].astype("string").str.strip()
    mask_paths = normalized["mask_path"].astype("string").str.strip()
    if case_ids.isna().any() or case_ids.eq("").any() or case_ids.duplicated().any():
        raise ValueError("case_id values must be present and unique.")
    if patient_ids.isna().any() or patient_ids.eq("").any():
        raise ValueError("Metadata contains an empty patient_id.")
    if image_paths.isna().any() or image_paths.eq("").any() or mask_paths.isna().any() or mask_paths.eq("").any():
        raise ValueError("Metadata contains an empty image_path or mask_path.")
    if normalized["is_empty_mask"].isna().any():
        raise ValueError("Metadata contains a missing is_empty_mask value.")
    unknown_splits = set(splits.dropna()) - set(SPLIT_NAMES)
    if splits.isna().any() or splits.eq("").any() or unknown_splits:
        raise ValueError("Metadata contains an unknown split value.")
    if set(splits) != set(SPLIT_NAMES):
        raise ValueError("Metadata must contain non-empty TRAIN, VAL and TEST partitions.")

    normalized["case_id"] = case_ids
    normalized["patient_id"] = patient_ids
    normalized["split"] = splits
    normalized["image_path"] = image_paths
    normalized["mask_path"] = mask_paths
    patient_split_counts = normalized.groupby("patient_id")["split"].nunique()
    if patient_split_counts.gt(1).any():
        raise ValueError("A patient_id crosses split boundaries.")

    evidence = {
        "identity_source": str(identity_manifest["identity_source"]).strip(),
        "identity_evidence_reference": str(
            identity_manifest["identity_evidence_reference"]
        ).strip(),
        "unique_patient_ids": int(patient_ids.nunique()),
        "split_counts": {
            split.lower(): int((splits == split).sum()) for split in SPLIT_NAMES
        },
    }
    return normalized, evidence


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_source_path(path, base_dir):
    resolved = Path(path).resolve()
    try:
        return Path(os.path.relpath(resolved, Path(base_dir).resolve())).as_posix()
    except ValueError:
        return str(resolved)


def main(identity_manifest_path: Path, output_dir: Path = ROOT / "ai_training/splits"):
    print("=" * 70)
    print("   BƯỚC 1 & 2: THIẾT LẬP PHÂN CHIA TẬP DỮ LIỆU THEO PATIENT ID")
    print("=" * 70)

    candidate_meta_files = [
        ROOT / "dataset/vinmec_ovarian/metadata/kltn_ground_truth_307.csv",
        ROOT / "metadata/kltn_ground_truth_307.csv",
        ROOT / "ai_training/splits/kltn_ground_truth_307.csv",
    ]
    meta_file = None
    for cand in candidate_meta_files:
        if cand.is_file():
            meta_file = cand
            break

    if not meta_file:
        print(f"[ERROR] Không tìm thấy metadata trong các đường dẫn: {candidate_meta_files}")
        sys.exit(1)

    df = pd.read_csv(meta_file)
    identity_manifest_path = Path(identity_manifest_path).resolve()
    identity_manifest = json.loads(identity_manifest_path.read_text(encoding="utf-8"))
    input_metadata_sha256 = _sha256_file(meta_file)
    df, identity_evidence = validate_patient_split_metadata(
        df, identity_manifest, input_metadata_sha256
    )
    print(f"[1] Tổng số bản ghi Ground Truth nạp được: {len(df)}")
    print(f"[2] Số ID bệnh nhân nguồn đã xác thực: {identity_evidence['unique_patient_ids']}")
    print(f"[3] Số ca Empty Mask (u nang/buồng trứng bình thường): {df['is_empty_mask'].eq(True).sum()}")

    # Kiểm tra đường dẫn file thực tế
    missing_imgs = 0
    missing_masks = 0
    for _, row in df.iterrows():
        img_p = Path(str(row['image_path']).replace('\\', '/'))
        mask_p = Path(str(row['mask_path']).replace('\\', '/'))
        if not img_p.is_absolute():
            img_p = ROOT / img_p
        if not mask_p.is_absolute():
            mask_p = ROOT / mask_p
        if not img_p.is_file():
            missing_imgs += 1
        if not mask_p.is_file():
            missing_masks += 1

    print(f"[4] Kiểm tra tính nguyên vẹn: Thiếu ảnh={missing_imgs}, Thiếu mask={missing_masks}")
    if missing_imgs or missing_masks:
        raise FileNotFoundError("Ground-truth source image/mask files are missing; no split files were written.")

    df["image_sha256"] = [
        _sha256_file(path if path.is_absolute() else ROOT / path)
        for path in (Path(value) for value in df["image_path"])
    ]
    df["mask_sha256"] = [
        _sha256_file(path if path.is_absolute() else ROOT / path)
        for path in (Path(value) for value in df["mask_path"])
    ]
    if df["image_sha256"].duplicated().any():
        raise ValueError("Duplicate source image SHA-256 found; split rows must be unique images.")

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
    print("[XÁC NHẬN] Không có patient ID nguồn giao giữa Train/Val/Test.")

    # Lưu các file CSV
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    train_path = out_dir / "train.csv"
    val_path = out_dir / "val.csv"
    test_path = out_dir / "test.csv"
    gt_all_path = out_dir / "all_samples_patient_split.csv"

    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)
    test_df.to_csv(test_path, index=False)
    df.to_csv(gt_all_path, index=False)

    print(f"\n[XUẤT BẢN] Đã lưu {train_path}: {len(train_df)} ảnh ({len(train_patients)} bệnh nhân, {train_df['is_empty_mask'].eq(True).sum()} empty)")
    print(f"[XUẤT BẢN] Đã lưu {val_path}: {len(val_df)} ảnh ({len(val_patients)} bệnh nhân, {val_df['is_empty_mask'].eq(True).sum()} empty)")
    print(f"[XUẤT BẢN] Đã lưu {test_path}: {len(test_df)} ảnh ({len(test_patients)} bệnh nhân, {test_df['is_empty_mask'].eq(True).sum()} empty)")

    # Lưu manifest
    manifest_data = {
        "title": "Source-verified ovarian ultrasound patient split",
        "source_patient_identity_verified": True,
        "patient_ids_verified": True,
        "identity_level": "patient_verified",
        "identity_source": identity_evidence["identity_source"],
        "identity_evidence_reference": identity_evidence["identity_evidence_reference"],
        "identity_manifest_path": _record_source_path(identity_manifest_path, out_dir),
        "identity_manifest_sha256": _sha256_file(identity_manifest_path),
        "source_metadata_path": _record_source_path(meta_file, out_dir),
        "input_metadata_sha256": input_metadata_sha256,
        "split_level": "patient-level",
        "split_counts": identity_evidence["split_counts"],
        "unique_patient_ids": identity_evidence["unique_patient_ids"],
        "empty_mask_rows": int(df['is_empty_mask'].eq(True).sum()),
        "zero_leakage_verified": True,
        "source_image_hashes_verified": True,
        "source_mask_hashes_recorded": True,
    }

    manifest_file = out_dir / "de_cuong_split_manifest.json"
    encoded_manifest = json.dumps(manifest_data, indent=2, ensure_ascii=False)
    manifest_file.write_text(encoded_manifest, encoding="utf-8")
    (out_dir / "manifest.json").write_text(encoded_manifest, encoding="utf-8")

    print(f"[XUẤT BẢN] Đã lưu manifest phân chia: {manifest_file}")
    print("=" * 70)
    print("   HOÀN THÀNH: PATIENT SPLIT ĐÃ DÙNG ID NGUỒN ĐƯỢC XÁC THỰC")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create splits from source-verified patient identity metadata.")
    parser.add_argument("--identity-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ai_training/splits")
    args = parser.parse_args()
    main(args.identity_manifest, args.output_dir)
