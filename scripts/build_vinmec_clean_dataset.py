"""Build clean deduplicated Vinmec dataset and comprehensive audit report.

Preserves exact image-mask pairs, zero pixel modification, read-only on sources.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
from collections import defaultdict
from pathlib import Path
from PIL import Image
import cv2
import numpy as np

ROOT = Path(".").resolve()
TARGET_CLEAN = ROOT / "dataset" / "Vinmec_clean"
REPORTS_DIR = ROOT / "reports"

SOURCES = [
    ("Vinmec_2d", ROOT / "dataset/Vinmec/Vinmec_2d/images", ROOT / "dataset/Vinmec/Vinmec_2d/annotations", "_binary.PNG", "2d"),
    ("Vinmec_3d", ROOT / "dataset/Vinmec/Vinmec_3d/images", ROOT / "dataset/Vinmec/Vinmec_3d/annotations", "_binary.PNG", "3d"),
    ("Vinmec_2D_train", ROOT / "dataset/Vinmec_2D/train/train_image", ROOT / "dataset/Vinmec_2D/train/train_label/label", ".PNG", "2d"),
    ("Vinmec_2D_test", ROOT / "dataset/Vinmec_2D/test/image", ROOT / "dataset/Vinmec_2D/test/label/black_write", ".PNG", "2d"),
    ("Vinmec_CEUS", ROOT / "dataset/Vinmec_CEUS/image", ROOT / "dataset/Vinmec_CEUS/label", ".PNG", "3d"),
]

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def compute_dhash(img: np.ndarray, hash_size: int = 8) -> np.ndarray:
    resized = cv2.resize(img, (hash_size + 1, hash_size))
    diff = resized[:, 1:] > resized[:, :-1]
    return diff.flatten()

def compute_phash(img: np.ndarray, hash_size: int = 8) -> np.ndarray:
    resized = cv2.resize(img, (32, 32))
    dct = cv2.dct(np.float32(resized))
    dct_low = dct[:hash_size, :hash_size]
    med = np.median(dct_low)
    return (dct_low > med).flatten()

def main():
    print("=== Step 1: Scanning all 3 source folders and all subsets ===")
    records = []
    unmatched_files = []
    
    for sname, img_dir, mask_dir, mask_suffix, modality in SOURCES:
        if not img_dir.is_dir() or not mask_dir.is_dir():
            print(f"Skipping {sname}, directories not found.")
            continue
        
        imgs = sorted(os.listdir(img_dir))
        masks_set = set(os.listdir(mask_dir))
        
        for f in imgs:
            if not f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
                continue
            img_path = img_dir / f
            stem = img_path.stem
            expected_mask_name = stem + mask_suffix
            
            if expected_mask_name not in masks_set:
                unmatched_files.append({
                    "source": sname,
                    "image": str(img_path.relative_to(ROOT)),
                    "expected_mask": expected_mask_name,
                    "reason": "Missing expected mask"
                })
                continue
                
            mask_path = mask_dir / expected_mask_name
            
            # Read image metadata
            img_sha = sha256_file(img_path)
            mask_sha = sha256_file(mask_path)
            
            with Image.open(img_path) as im:
                img_size = im.size  # (width, height)
            with Image.open(mask_path) as m:
                mask_size = m.size  # (width, height)
                
            records.append({
                "source_dataset": sname,
                "modality": modality,
                "image_file": f,
                "mask_file": expected_mask_name,
                "image_path": str(img_path.relative_to(ROOT)).replace("\\", "/"),
                "mask_path": str(mask_path.relative_to(ROOT)).replace("\\", "/"),
                "image_hash": img_sha,
                "mask_hash": mask_sha,
                "image_size": f"{img_size[0]}x{img_size[1]}",
                "mask_size": f"{mask_size[0]}x{mask_size[1]}",
                "size_match": (img_size == mask_size),
                "stem": stem,
            })

    print(f"Total scanned pairs: {len(records)}")
    print(f"Total unmatched files: {len(unmatched_files)}")

    # Check for size mismatches
    size_mismatches = [r for r in records if not r["size_match"]]
    print(f"Size mismatches: {len(size_mismatches)}")

    # Group by image SHA256 to identify duplicates
    print("\n=== Step 2: Deduplication by Image Content SHA-256 ===")
    hash_groups = defaultdict(list)
    for r in records:
        hash_groups[r["image_hash"]].append(r)

    print(f"Total unique image hashes: {len(hash_groups)}")
    duplicate_instances_count = sum(len(group) - 1 for group in hash_groups.values())
    print(f"Total duplicate instances to prune: {duplicate_instances_count}")

    # Prioritize canonical source: Vinmec_2d / Vinmec_3d > Vinmec_2D_train / test > Vinmec_CEUS
    source_priority = {
        "Vinmec_2d": 1,
        "Vinmec_3d": 1,
        "Vinmec_2D_train": 2,
        "Vinmec_2D_test": 3,
        "Vinmec_CEUS": 4,
    }

    canonical_records = []
    final_audit_rows = []

    for img_hash, group in sorted(hash_groups.items()):
        # Sort by priority
        group.sort(key=lambda x: source_priority.get(x["source_dataset"], 99))
        canonical = group[0]
        
        # Prepare destination paths for canonical
        modality = canonical["modality"]
        dest_img_rel = f"dataset/Vinmec_clean/{modality}/images/{canonical['stem']}.JPG"
        dest_mask_rel = f"dataset/Vinmec_clean/{modality}/masks/{canonical['stem']}.PNG"
        
        canonical["status"] = "VALID_PAIR"
        canonical["duplicate_of"] = ""
        canonical["destination_image"] = dest_img_rel
        canonical["destination_mask"] = dest_mask_rel
        canonical_records.append(canonical)
        final_audit_rows.append(canonical)
        
        for dup in group[1:]:
            dup["status"] = "DUPLICATE_PAIR"
            dup["duplicate_of"] = canonical["image_path"]
            dup["destination_image"] = ""
            dup["destination_mask"] = ""
            final_audit_rows.append(dup)

    print(f"Canonical pairs to keep: {len(canonical_records)}")
    print(f"Audit rows total: {len(final_audit_rows)}")

    # Step 3: Perceptual Hash on Canonical Records
    print("\n=== Step 3: Perceptual Hash Analysis for Near-Duplicates ===")
    phashes = []
    dhashes = []
    for r in canonical_records:
        gray = cv2.imread(str(ROOT / r["image_path"]), cv2.IMREAD_GRAYSCALE)
        ph = compute_phash(gray)
        dh = compute_dhash(gray)
        phashes.append(ph)
        dhashes.append(dh)

    phashes = np.stack(phashes)
    dhashes = np.stack(dhashes)
    n_can = len(canonical_records)
    
    possible_duplicates = []
    for i in range(n_can):
        diffs_p = np.count_nonzero(phashes[i] != phashes[i+1:], axis=1)
        diffs_d = np.count_nonzero(dhashes[i] != dhashes[i+1:], axis=1)
        match = np.where((diffs_p <= 2) | (diffs_d <= 2))[0]
        for m in match:
            j = i + 1 + m
            possible_duplicates.append({
                "sample_1_id": f"{canonical_records[i]['modality']}_{canonical_records[i]['stem']}",
                "sample_2_id": f"{canonical_records[j]['modality']}_{canonical_records[j]['stem']}",
                "image_1_path": canonical_records[i]["image_path"],
                "image_2_path": canonical_records[j]["image_path"],
                "mask_1_path": canonical_records[i]["mask_path"],
                "mask_2_path": canonical_records[j]["mask_path"],
                "phash_distance": int(diffs_p[m]),
                "dhash_distance": int(diffs_d[m]),
                "size_1": canonical_records[i]["image_size"],
                "size_2": canonical_records[j]["image_size"],
                "status": "POSSIBLE_DUPLICATE",
                "notes": "Near-duplicate perceptual hash (cine-loop / adjacent frame of same examination); kept in clean dataset pending manual review"
            })

    print(f"Detected possible near-duplicate pairs (pHash/dHash <= 2): {len(possible_duplicates)}")

    # Step 4: Execute Safe Copy to TARGET_CLEAN
    print("\n=== Step 4: Creating dataset/Vinmec_clean and copying data ===")
    for mod in ["2d", "3d"]:
        (TARGET_CLEAN / mod / "images").mkdir(parents=True, exist_ok=True)
        (TARGET_CLEAN / mod / "masks").mkdir(parents=True, exist_ok=True)

    copied_images = 0
    copied_masks = 0
    for r in canonical_records:
        src_img = ROOT / r["image_path"]
        src_mask = ROOT / r["mask_path"]
        dst_img = ROOT / r["destination_image"]
        dst_mask = ROOT / r["destination_mask"]
        
        shutil.copy2(src_img, dst_img)
        copied_images += 1
        shutil.copy2(src_mask, dst_mask)
        copied_masks += 1

    print(f"Successfully copied {copied_images} images and {copied_masks} masks to {TARGET_CLEAN.relative_to(ROOT)}")

    # Step 5: Post-Copy Integrity Verification
    print("\n=== Step 5: Rigorous Integrity Verification on Vinmec_clean ===")
    clean_2d_imgs = os.listdir(TARGET_CLEAN / "2d" / "images")
    clean_2d_masks = os.listdir(TARGET_CLEAN / "2d" / "masks")
    clean_3d_imgs = os.listdir(TARGET_CLEAN / "3d" / "images")
    clean_3d_masks = os.listdir(TARGET_CLEAN / "3d" / "masks")

    total_clean_imgs = len(clean_2d_imgs) + len(clean_3d_imgs)
    total_clean_masks = len(clean_2d_masks) + len(clean_3d_masks)

    print(f"Vinmec_clean 2D: {len(clean_2d_imgs)} images, {len(clean_2d_masks)} masks")
    print(f"Vinmec_clean 3D: {len(clean_3d_imgs)} images, {len(clean_3d_masks)} masks")
    print(f"Total clean images: {total_clean_imgs}")
    print(f"Total clean masks: {total_clean_masks}")

    assert total_clean_imgs == len(canonical_records), "Total clean images != canonical records"
    assert total_clean_masks == len(canonical_records), "Total clean masks != canonical records"
    assert total_clean_imgs == total_clean_masks, "Images count != masks count in clean folder"

    # Verify stem matching and 1-to-1 pair
    for mod, imgs_list, masks_list in [("2d", clean_2d_imgs, clean_2d_masks), ("3d", clean_3d_imgs, clean_3d_masks)]:
        img_stems = {os.path.splitext(f)[0] for f in imgs_list}
        mask_stems = {os.path.splitext(f)[0] for f in masks_list}
        assert img_stems == mask_stems, f"Mismatch in stems for {mod}"

    # Verify zero duplicate SHA-256 in clean folder
    clean_hashes = set()
    for mod, imgs_list in [("2d", clean_2d_imgs), ("3d", clean_3d_imgs)]:
        for f in imgs_list:
            p = TARGET_CLEAN / mod / "images" / f
            h = sha256_file(p)
            assert h not in clean_hashes, f"Duplicate hash found in clean: {f}"
            clean_hashes.add(h)

    print("Verification PASSED: 0 duplicates in clean dataset, 100% 1-to-1 image-mask mapping verified.")

    # Step 6: Export Audit Reports
    print("\n=== Step 6: Exporting CSV and JSON reports ===")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Full mapping report
    fieldnames = [
        "sample_id", "source_dataset", "modality", "image_path", "mask_path",
        "image_hash", "mask_hash", "image_size", "mask_size", "status",
        "duplicate_of", "destination_image", "destination_mask"
    ]
    
    for r in final_audit_rows:
        r["sample_id"] = f"{r['modality']}_{r['stem']}"

    report_csv_clean = TARGET_CLEAN / "deduplication_mapping.csv"
    report_csv_reports = REPORTS_DIR / "dataset_deduplication_report.csv"
    for target_path in [report_csv_clean, report_csv_reports]:
        with target_path.open("w", newline="", encoding="utf-8-sig") as fp:
            writer = csv.DictWriter(fp, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(final_audit_rows)

    # Possible duplicates report
    pos_dup_fields = [
        "sample_1_id", "sample_2_id", "image_1_path", "image_2_path",
        "mask_1_path", "mask_2_path", "phash_distance", "dhash_distance",
        "size_1", "size_2", "status", "notes"
    ]
    pos_dup_csv_clean = TARGET_CLEAN / "possible_duplicates.csv"
    pos_dup_csv_reports = REPORTS_DIR / "possible_duplicates_report.csv"
    for target_path in [pos_dup_csv_clean, pos_dup_csv_reports]:
        with target_path.open("w", newline="", encoding="utf-8-sig") as fp:
            writer = csv.DictWriter(fp, fieldnames=pos_dup_fields)
            writer.writeheader()
            writer.writerows(possible_duplicates)

    # Summary JSON
    summary_data = {
        "status": "COMPLETED",
        "clean_dataset_folder": str(TARGET_CLEAN),
        "source_folders_scanned": [str(ROOT / "dataset" / "Vinmec"), str(ROOT / "dataset" / "Vinmec_2D"), str(ROOT / "dataset" / "Vinmec_CEUS")],
        "total_initial_images": len(records),
        "total_initial_masks_paired": len(records),
        "total_duplicate_images_detected": duplicate_instances_count,
        "total_images_retained_in_clean": total_clean_imgs,
        "total_masks_retained_in_clean": total_clean_masks,
        "total_valid_pairs_in_clean": total_clean_imgs,
        "number_of_images_equals_number_of_masks": (total_clean_imgs == total_clean_masks == len(canonical_records)),
        "duplicate_pairs_removed": duplicate_instances_count,
        "unmatched_files_count": len(unmatched_files),
        "size_mismatch_count": len(size_mismatches),
        "possible_duplicates_candidate_pairs": len(possible_duplicates),
        "possible_duplicates_unique_images": len({p["sample_1_id"] for p in possible_duplicates} | {p["sample_2_id"] for p in possible_duplicates}),
        "clean_breakdown": {
            "2d_images": len(clean_2d_imgs),
            "2d_masks": len(clean_2d_masks),
            "3d_images": len(clean_3d_imgs),
            "3d_masks": len(clean_3d_masks),
        },
        "reports": {
            "full_mapping_csv": str(report_csv_reports),
            "possible_duplicates_csv": str(pos_dup_csv_reports),
            "clean_mapping_csv": str(report_csv_clean),
        }
    }

    summary_json_clean = TARGET_CLEAN / "summary.json"
    summary_json_reports = REPORTS_DIR / "dataset_deduplication_summary.json"
    for target_path in [summary_json_clean, summary_json_reports]:
        target_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nSummary statistics:")
    print(json.dumps(summary_data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
