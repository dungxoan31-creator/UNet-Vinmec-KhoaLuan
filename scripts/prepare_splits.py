"""Create reproducible image-level Train/Validation/Test splits for mask training.

Patient IDs are neither required nor used. The resulting partitions prove only
image-content separation; they cannot establish patient-independent performance.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "metadata/kltn_ground_truth_307.csv"
SPLIT_NAMES = ("TRAIN", "VAL", "TEST")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_source_path(value: str, root: Path) -> Path:
    path = Path(str(value).replace("\\", "/"))
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def validate_image_split_metadata(df: pd.DataFrame, root: Path = ROOT) -> tuple[pd.DataFrame, dict]:
    """Check image/mask pairs and discard any synthetic patient grouping."""
    required = {"case_id", "image_path", "mask_path"}
    if not required.issubset(df.columns):
        raise ValueError(f"Metadata is missing required columns: {sorted(required - set(df.columns))}")
    if "is_empty_mask" not in df.columns and "status" not in df.columns:
        raise ValueError("Metadata must describe whether each annotation mask is empty")
    if df.empty:
        raise ValueError("Metadata must contain at least one sample")

    normalized = df.copy()
    normalized["case_id"] = normalized["case_id"].astype("string").str.strip()
    if normalized["case_id"].isna().any() or normalized["case_id"].eq("").any():
        raise ValueError("case_id values must be present")
    if normalized["case_id"].duplicated().any():
        raise ValueError("case_id values must be unique")
    for field in ("image_path", "mask_path"):
        normalized[field] = normalized[field].astype("string").str.strip()
        if normalized[field].isna().any() or normalized[field].eq("").any():
            raise ValueError(f"Metadata contains an empty {field}")

    if "is_empty_mask" in normalized.columns:
        raw_empty = normalized["is_empty_mask"].astype("string").str.strip().str.lower()
        truthy = {"true", "1", "yes"}
        falsy = {"false", "0", "no"}
        unknown = set(raw_empty.dropna()) - truthy - falsy
        if raw_empty.isna().any() or unknown:
            raise ValueError("is_empty_mask must contain explicit true/false values")
        normalized["is_empty_mask"] = raw_empty.isin(truthy)
    else:
        normalized["is_empty_mask"] = normalized["status"].astype("string").eq("EMPTY_MASK_CONTROL")

    image_hashes: set[str] = set()
    image_hash_column: list[str] = []
    mask_hash_column: list[str] = []
    positive_pixel_column: list[int] = []
    for row_number, row in enumerate(normalized.to_dict("records"), start=2):
        image_path = _resolve_source_path(row["image_path"], Path(root))
        mask_path = _resolve_source_path(row["mask_path"], Path(root))
        if not image_path.is_file():
            raise FileNotFoundError(f"Missing source image at metadata row {row_number}: {image_path}")
        if not mask_path.is_file():
            raise FileNotFoundError(f"Missing source mask at metadata row {row_number}: {mask_path}")
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if image is None or mask is None:
            raise ValueError(f"Unreadable image/mask pair at metadata row {row_number}")
        if image.ndim != 2 or mask.ndim != 2 or image.shape != mask.shape:
            raise ValueError(
                f"Image/mask dimensions differ at metadata row {row_number}: "
                f"image {image.shape}, mask {mask.shape}"
            )
        if not np.isin(np.unique(mask), (0, 1, 255)).all():
            raise ValueError(f"Mask must be binary at metadata row {row_number}")
        image_hash = _sha256_file(image_path)
        if image_hash in image_hashes:
            raise ValueError(f"Duplicate image content at metadata row {row_number}")
        image_hashes.add(image_hash)
        positive_pixels = int(np.count_nonzero(mask))
        if bool(row["is_empty_mask"]) != (positive_pixels == 0):
            raise ValueError(f"is_empty_mask contradicts mask pixels at metadata row {row_number}")
        image_hash_column.append(image_hash)
        mask_hash_column.append(_sha256_file(mask_path))
        positive_pixel_column.append(positive_pixels)

    normalized["image_sha256"] = image_hash_column
    normalized["mask_sha256"] = mask_hash_column
    normalized["verified_positive_pixels"] = positive_pixel_column
    # Synthetic or unverifiable patient IDs are removed from the generated split files.
    normalized = normalized.drop(columns=["patient_id"], errors="ignore")
    evidence = {
        "unique_images": len(normalized),
        "duplicate_image_hashes": 0,
        "image_mask_pairs_aligned": True,
        "patient_identity_used": False,
        "patient_level_independence_verified": False,
    }
    return normalized, evidence


def create_image_level_splits(
    df: pd.DataFrame,
    val_fraction: float = 0.15,
    test_fraction: float = 0.15,
    seed: int = 42,
) -> tuple[pd.DataFrame, dict]:
    df = df.reset_index(drop=True)
    if val_fraction <= 0 or test_fraction <= 0 or val_fraction + test_fraction >= 1:
        raise ValueError("val_fraction and test_fraction must be positive and sum to less than 1")
    rng = np.random.default_rng(seed)
    split_by_index: dict[int, str] = {}

    for _, stratum in df.groupby("is_empty_mask", sort=True, dropna=False):
        indices = stratum.index.to_numpy().copy()
        rng.shuffle(indices)
        count = len(indices)
        if count < 3:
            raise ValueError("Each mask-presence stratum needs at least three images for 3-way splitting")
        test_count = max(1, int(round(count * test_fraction)))
        val_count = max(1, int(round(count * val_fraction)))
        if test_count + val_count >= count:
            raise ValueError("Not enough samples in a mask-presence stratum for train/validation/test")
        for index in indices[:test_count]:
            split_by_index[int(index)] = "TEST"
        for index in indices[test_count : test_count + val_count]:
            split_by_index[int(index)] = "VAL"
        for index in indices[test_count + val_count :]:
            split_by_index[int(index)] = "TRAIN"

    result = df.copy()
    result["split"] = [split_by_index[int(index)] for index in result.index]
    counts = {split.lower(): int((result["split"] == split).sum()) for split in SPLIT_NAMES}
    if any(count == 0 for count in counts.values()):
        raise ValueError("Generated image-level split contains an empty partition")
    class_counts = {
        split.lower(): {
            "empty_mask": int(((result["split"] == split) & result["is_empty_mask"]).sum()),
            "lesion_mask": int(((result["split"] == split) & ~result["is_empty_mask"]).sum()),
        }
        for split in SPLIT_NAMES
    }
    return result, {"split_counts": counts, "mask_presence_counts": class_counts, "seed": seed}


def main(
    source_csv: Path = DEFAULT_SOURCE,
    output_dir: Path = ROOT / "ai_training/splits/vinmec_307_image_level",
    val_fraction: float = 0.15,
    test_fraction: float = 0.15,
    seed: int = 42,
):
    source_csv = Path(source_csv)
    if not source_csv.is_file():
        raise FileNotFoundError(f"Ground truth metadata not found: {source_csv}")
    data = pd.read_csv(source_csv)
    data, evidence = validate_image_split_metadata(data, root=ROOT)
    data, split_evidence = create_image_level_splits(data, val_fraction, test_fraction, seed)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for split in SPLIT_NAMES:
        data.loc[data["split"] == split].to_csv(out_dir / f"{split.lower()}.csv", index=False)
    data.to_csv(out_dir / "all_samples_image_split.csv", index=False)
    manifest = {
        "title": "Vinmec 307-case image-level mask development split",
        "split_level": "image-level",
        "source_metadata_path": str(source_csv.resolve()),
        "source_metadata_sha256": _sha256_file(source_csv),
        "source_patient_identity_verified": False,
        "patient_ids_verified": False,
        "patient_level_independence_verified": False,
        "identity_limit": "Patient identity is not used; image-level partitions do not establish patient independence.",
        "deduplication": "SHA-256 of image bytes; duplicate image content is rejected before splitting.",
        **evidence,
        **split_evidence,
        "test_partition_used_for_training_or_selection": False,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-csv", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ai_training/splits/vinmec_307_image_level")
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--test-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    main(args.source_csv, args.output_dir, args.val_fraction, args.test_fraction, args.seed)
