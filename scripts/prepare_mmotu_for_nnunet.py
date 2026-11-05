"""Prepare MMOTU 2D Ultrasound dataset for nnU-Net v2 benchmark.

Transforms verified MMOTU 2D image-level splits into the canonical
nnU-Net v2 dataset structure:
    nnUNet_raw/DatasetXXX_MMOTU/
    ├── dataset.json
    ├── imagesTr/
    │   ├── mmotu_2d_1_0000.png
    │   └── ...
    ├── labelsTr/
    │   ├── mmotu_2d_1.png
    │   └── ...
    ├── imagesTs/ (optional if val-mode == 'test')
    ├── labelsTs/ (optional if val-mode == 'test')
    ├── splits_final.json (5-fold custom split with fold 0 = official MMOTU split)
    └── manifest.json

Medical and Benchmark Disclosures:
- Image-level split strictly preserved from official MMOTU lists.
- Patient-level independence is UNVERIFIED; metrics reflect image-level performance.
- Single-channel grayscale ultrasound modality ('US') normalized as 1-channel PNG.
- Binary segmentation: 0 = background, 1 = ovarian lesion.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def sha256_file(path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_split_records(csv_path: Path) -> List[Dict[str, str]]:
    """Load case records from a split CSV file."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Split CSV not found: {csv_path}")
    records = []
    with csv_path.open("r", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            records.append(dict(row))
    return records


def convert_single_case(
    case_id: str,
    src_image_path: Path,
    src_mask_path: Path,
    dst_image_path: Path,
    dst_mask_path: Path,
    file_mode: str = "copy",
    dry_run: bool = False,
) -> Tuple[str, bool, Optional[str]]:
    """Process a single image and mask case for nnU-Net.

    Ensures:
    1. Image is written as single-channel grayscale PNG (matching channel_names: {"0": "US"}).
    2. Mask is written as uint8 PNG with values strictly in {0, 1} (background=0, lesion=1).
    """
    if dry_run:
        return case_id, True, None

    try:
        dst_image_path.parent.mkdir(parents=True, exist_ok=True)
        dst_mask_path.parent.mkdir(parents=True, exist_ok=True)

        if file_mode == "symlink":
            # Attempt symbolic link. Note: If source is JPG, it's not a true PNG byte-stream,
            # but NaturalImage2DIO reads through skimage/PIL. Grayscale conversion is safer via copy.
            try:
                if dst_image_path.exists() or dst_image_path.is_symlink():
                    dst_image_path.unlink()
                if dst_mask_path.exists() or dst_mask_path.is_symlink():
                    dst_mask_path.unlink()
                os.symlink(src_image_path.resolve(), dst_image_path)
                os.symlink(src_mask_path.resolve(), dst_mask_path)
                return case_id, True, None
            except OSError as err:
                # Fall back to copy if symlink privilege is not held (common on Windows)
                pass

        elif file_mode == "hardlink":
            try:
                if dst_image_path.exists():
                    dst_image_path.unlink()
                if dst_mask_path.exists():
                    dst_mask_path.unlink()
                os.link(src_image_path.resolve(), dst_image_path)
                os.link(src_mask_path.resolve(), dst_mask_path)
                return case_id, True, None
            except OSError:
                pass

        # Standard file_mode == 'copy' or fallback
        # 1. Read ultrasound image as grayscale
        raw_img = cv2.imread(str(src_image_path), cv2.IMREAD_GRAYSCALE)
        if raw_img is None:
            return case_id, False, f"Failed to read image: {src_image_path}"

        # 2. Read mask and enforce binary values: 0 for background, 1 for lesion
        raw_mask = cv2.imread(str(src_mask_path), cv2.IMREAD_GRAYSCALE)
        if raw_mask is None:
            return case_id, False, f"Failed to read mask: {src_mask_path}"

        if raw_img.shape != raw_mask.shape:
            return case_id, False, f"Geometry mismatch: img={raw_img.shape}, mask={raw_mask.shape}"

        # Normalize binary mask to strictly {0, 1}
        binary_mask = (raw_mask > 0).astype(np.uint8)

        # 3. Save as PNG
        cv2.imwrite(str(dst_image_path), raw_img)
        cv2.imwrite(str(dst_mask_path), binary_mask)

        return case_id, True, None
    except Exception as exc:
        return case_id, False, str(exc)


def generate_nnunet_dataset_json(
    output_folder: Path,
    num_training_cases: int,
    dataset_name: str = "MMOTU",
    channel_name: str = "US",
    file_ending: str = ".png",
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Generate canonical nnU-Net v2 dataset.json metadata file."""
    dataset_json: Dict[str, Any] = {
        "channel_names": {
            "0": channel_name,
        },
        "labels": {
            "background": 0,
            "lesion": 1,
        },
        "numTraining": num_training_cases,
        "file_ending": file_ending,
        "name": dataset_name,
        "description": "MMOTU 2D Ultrasound Ovarian Lesion Binary Segmentation (Ceiling Benchmark)",
        "reference": "MMOTU Dataset (OTU_2d) / Graduation Thesis Benchmark",
        "licence": "Research purpose only (MMOTU dataset terms apply)",
        "release": "2.0",
        "converted_by": "nnU-Net Benchmark Architect",
    }

    if not dry_run:
        output_folder.mkdir(parents=True, exist_ok=True)
        target_path = output_folder / "dataset.json"
        with target_path.open("w", encoding="utf-8") as f:
            json.dump(dataset_json, f, indent=2)
    return dataset_json


def generate_splits_final_json(
    train_ids: List[str],
    val_ids: List[str],
    output_folder: Path,
    num_folds: int = 5,
    dry_run: bool = False,
) -> List[Dict[str, List[str]]]:
    """Generate splits_final.json compatible with nnU-Net manual splits.

    Fold 0 is configured with the exact official MMOTU train and validation split.
    Folds 1..(num_folds-1) rotate or subdivide the dataset to satisfy the 5-fold format.
    """
    splits: List[Dict[str, List[str]]] = []

    # Fold 0: Exact official MMOTU split
    splits.append({
        "train": sorted(train_ids),
        "val": sorted(val_ids),
    })

    # Synthetic cross-validation folds if 5 folds requested
    all_ids = sorted(train_ids + val_ids)
    n = len(all_ids)
    fold_size = n // num_folds

    for k in range(1, num_folds):
        val_start = k * fold_size
        val_end = (k + 1) * fold_size if k < (num_folds - 1) else n
        fold_val = all_ids[val_start:val_end]
        fold_train = [cid for cid in all_ids if cid not in fold_val]
        splits.append({
            "train": fold_train,
            "val": fold_val,
        })

    if not dry_run:
        output_folder.mkdir(parents=True, exist_ok=True)
        target_path = output_folder / "splits_final.json"
        with target_path.open("w", encoding="utf-8") as f:
            json.dump(splits, f, indent=2)
    return splits


def prepare_mmotu_dataset(
    train_csv: Path,
    val_csv: Path,
    output_dir: Path,
    dataset_name: str = "MMOTU",
    channel_name: str = "US",
    val_mode: str = "train_with_split",
    file_mode: str = "copy",
    limit: Optional[int] = None,
    dry_run: bool = False,
    num_workers: int = 4,
) -> Dict[str, Any]:
    """Execute complete dataset transformation into nnU-Net v2 format."""
    train_records = load_split_records(train_csv)
    val_records = load_split_records(val_csv)

    if limit is not None and limit > 0:
        # Distribute limit proportionally between train and val
        total_orig = len(train_records) + len(val_records)
        train_lim = max(1, int(round(limit * len(train_records) / total_orig)))
        val_lim = max(1, limit - train_lim)
        train_records = train_records[:train_lim]
        val_records = val_records[:val_lim]

    images_tr = output_dir / "imagesTr"
    labels_tr = output_dir / "labelsTr"
    images_ts = output_dir / "imagesTs"
    labels_ts = output_dir / "labelsTs"

    if not dry_run:
        images_tr.mkdir(parents=True, exist_ok=True)
        labels_tr.mkdir(parents=True, exist_ok=True)
        if val_mode == "test":
            images_ts.mkdir(parents=True, exist_ok=True)
            labels_ts.mkdir(parents=True, exist_ok=True)

    # Determine assignments based on val_mode
    tasks = []
    train_case_ids: List[str] = []
    val_case_ids: List[str] = []

    for row in train_records:
        cid = row["case_id"]
        train_case_ids.append(cid)
        img_src = (ROOT / row["image_path"]).resolve()
        mask_src = (ROOT / row["mask_path"]).resolve()
        dst_img = images_tr / f"{cid}_0000.png"
        dst_mask = labels_tr / f"{cid}.png"
        tasks.append((cid, img_src, mask_src, dst_img, dst_mask, file_mode, dry_run))

    if val_mode == "train_with_split":
        for row in val_records:
            cid = row["case_id"]
            val_case_ids.append(cid)
            img_src = (ROOT / row["image_path"]).resolve()
            mask_src = (ROOT / row["mask_path"]).resolve()
            dst_img = images_tr / f"{cid}_0000.png"
            dst_mask = labels_tr / f"{cid}.png"
            tasks.append((cid, img_src, mask_src, dst_img, dst_mask, file_mode, dry_run))
        num_training = len(train_records) + len(val_records)
        num_testing = 0
    elif val_mode == "test":
        for row in val_records:
            cid = row["case_id"]
            val_case_ids.append(cid)
            img_src = (ROOT / row["image_path"]).resolve()
            mask_src = (ROOT / row["mask_path"]).resolve()
            dst_img = images_ts / f"{cid}_0000.png"
            dst_mask = labels_ts / f"{cid}.png"
            tasks.append((cid, img_src, mask_src, dst_img, dst_mask, file_mode, dry_run))
        num_training = len(train_records)
        num_testing = len(val_records)
    else:
        raise ValueError(f"Unknown val_mode: {val_mode}. Choose 'train_with_split' or 'test'.")

    # Run conversion tasks
    errors: List[str] = []
    if num_workers > 1 and not dry_run:
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [
                executor.submit(
                    convert_single_case,
                    t[0], t[1], t[2], t[3], t[4], t[5], t[6]
                )
                for t in tasks
            ]
            for fut in as_completed(futures):
                cid, success, err = fut.result()
                if not success:
                    errors.append(f"Case {cid}: {err}")
    else:
        for t in tasks:
            cid, success, err = convert_single_case(t[0], t[1], t[2], t[3], t[4], t[5], t[6])
            if not success:
                errors.append(f"Case {cid}: {err}")

    if errors:
        raise RuntimeError(f"Encountered {len(errors)} conversion errors:\n" + "\n".join(errors[:10]))

    # Create dataset.json
    dataset_json = generate_nnunet_dataset_json(
        output_folder=output_dir,
        num_training_cases=num_training,
        dataset_name=dataset_name,
        channel_name=channel_name,
        file_ending=".png",
        dry_run=dry_run,
    )

    # Create splits_final.json
    splits_json = generate_splits_final_json(
        train_ids=train_case_ids,
        val_ids=val_case_ids,
        output_folder=output_dir,
        dry_run=dry_run,
    )

    # Create manifest.json with full disclosure
    manifest = {
        "dataset_name": dataset_name,
        "output_dir": output_dir.as_posix(),
        "task": "2D Ultrasound Ovarian Lesion Binary Segmentation",
        "split_level": "image-level",
        "patient_identity_available": False,
        "patient_level_independence_verified": False,
        "val_mode": val_mode,
        "file_mode": file_mode,
        "dry_run": dry_run,
        "num_training_cases": num_training,
        "num_testing_cases": num_testing,
        "train_cases_count": len(train_records),
        "val_cases_count": len(val_records),
        "channel_names": dataset_json["channel_names"],
        "labels": dataset_json["labels"],
        "source_splits": {
            "train_csv": train_csv.relative_to(ROOT).as_posix() if train_csv.is_relative_to(ROOT) else str(train_csv),
            "val_csv": val_csv.relative_to(ROOT).as_posix() if val_csv.is_relative_to(ROOT) else str(val_csv),
        },
        "splits_final_json": (output_dir / "splits_final.json").as_posix(),
        "nnunet_env_setup": {
            "nnUNet_raw": str(output_dir.parent.resolve()),
            "nnUNet_preprocessed_target": f"nnUNet_preprocessed/{output_dir.name}",
            "splits_final_instruction": (
                f"Copy {output_dir / 'splits_final.json'} into "
                f"$env:nnUNet_preprocessed/{output_dir.name}/splits_final.json after plan_and_preprocess."
            ),
        },
    }

    if not dry_run:
        target_manifest = output_dir / "manifest.json"
        with target_manifest.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    default_splits_dir = ROOT / "ai_training/splits/mmotu_2d_official_2026-10-27"
    parser.add_argument(
        "--splits-dir",
        type=Path,
        default=default_splits_dir,
        help="Directory containing official train.csv and val.csv",
    )
    parser.add_argument(
        "--train-csv",
        type=Path,
        default=None,
        help="Path to train.csv (defaults to --splits-dir/train.csv)",
    )
    parser.add_argument(
        "--val-csv",
        type=Path,
        default=None,
        help="Path to val.csv (defaults to --splits-dir/val.csv)",
    )
    parser.add_argument(
        "--dataset-id",
        type=int,
        default=101,
        help="nnU-Net 3-digit dataset identifier (e.g. 101 -> Dataset101_MMOTU)",
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        default="MMOTU",
        help="nnU-Net dataset name string",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Exact destination path for DatasetXXX_Name. If omitted, uses "
            "$env:nnUNet_raw/DatasetXXX_Name or nnUNet_raw/DatasetXXX_Name in repository root."
        ),
    )
    parser.add_argument(
        "--val-mode",
        choices=["train_with_split", "test"],
        default="train_with_split",
        help=(
            "'train_with_split' puts all cases in imagesTr/labelsTr and outputs splits_final.json "
            "for fold 0 evaluation (recommended for nnU-Net). 'test' puts val cases in imagesTs/labelsTs."
        ),
    )
    parser.add_argument(
        "--file-mode",
        choices=["copy", "symlink", "hardlink"],
        default="copy",
        help="Storage strategy. 'copy' converts to 1-channel grayscale PNG. 'symlink' creates symlinks.",
    )
    parser.add_argument(
        "--channel-name",
        type=str,
        default="US",
        help="Channel modality name (default: US)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit total number of cases (for testing or debugging)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect files and metadata without writing images/masks",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run nnunetv2 verify_dataset_integrity after preparation",
    )
    parser.add_argument(
        "--num-workers",
        type=int,
        default=4,
        help="Number of parallel worker threads for image processing",
    )

    args = parser.parse_args()

    # Resolve CSV paths
    train_csv = args.train_csv or (args.splits_dir / "train.csv")
    val_csv = args.val_csv or (args.splits_dir / "val.csv")

    if not train_csv.exists() or not val_csv.exists():
        print(f"Error: Missing split CSV files at {args.splits_dir}", file=sys.stderr)
        print("Please ensure train.csv and val.csv exist or run scripts/prepare_mmotu_segmentation_splits.py first.")
        sys.exit(1)

    # Resolve output directory
    if args.output_dir is not None:
        output_dir = args.output_dir.resolve()
    else:
        raw_root = os.environ.get("nnUNet_raw")
        if raw_root:
            base_dir = Path(raw_root)
        else:
            base_dir = ROOT / "nnUNet_raw"
        dataset_folder_name = f"Dataset{args.dataset_id:03d}_{args.dataset_name}"
        output_dir = (base_dir / dataset_folder_name).resolve()

    print("=" * 60)
    print(f"Preparing nnU-Net dataset: {output_dir.name}")
    print(f"Output directory : {output_dir}")
    print(f"Train split CSV  : {train_csv}")
    print(f"Val split CSV    : {val_csv}")
    print(f"Validation mode  : {args.val_mode}")
    print(f"File mode        : {args.file_mode}")
    print(f"Channel name     : {args.channel_name}")
    print(f"Limit            : {args.limit or 'Full dataset'}")
    print(f"Dry run          : {args.dry_run}")
    print("=" * 60)

    manifest = prepare_mmotu_dataset(
        train_csv=train_csv,
        val_csv=val_csv,
        output_dir=output_dir,
        dataset_name=args.dataset_name,
        channel_name=args.channel_name,
        val_mode=args.val_mode,
        file_mode=args.file_mode,
        limit=args.limit,
        dry_run=args.dry_run,
        num_workers=args.num_workers,
    )

    print("\nDataset preparation completed successfully.")
    print(json.dumps(manifest, indent=2))

    if args.verify and not args.dry_run:
        print("\nRunning nnUNetv2 verify_dataset_integrity...")
        try:
            from nnunetv2.experiment_planning.verify_dataset_integrity import verify_dataset_integrity
            verify_dataset_integrity(str(output_dir), num_processes=min(args.num_workers, 4))
            print("Integrity verification PASSED.")
        except Exception as exc:
            print(f"Integrity verification FAILED: {exc}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
