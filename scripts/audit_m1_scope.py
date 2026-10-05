"""Audit Milestone 1 split membership and locally available source files."""

import csv
import hashlib
import json
from pathlib import Path

import cv2

SPLITS = ("train", "val", "test")


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def _native_mask(root: Path, image_path: str) -> Path:
    image = Path(image_path)
    source = image_path.replace("\\", "/")
    if "/vinmec_m1_307/images/" in source:
        # Format stem is XXX_originalstem
        parts = image.stem.split("_", 1)
        orig_stem = parts[1] if len(parts) > 1 else image.stem
        # Check archive locations
        for candidate in [
            root / "dataset_backup_archive/Vinmec_2D/train/train_label/label" / f"{orig_stem}.PNG",
            root / "dataset_backup_archive/Vinmec_2D/test/label/black_write" / f"{orig_stem}.PNG",
            root / "dataset_backup_archive/Vinmec_CEUS/label" / f"{orig_stem}.PNG",
        ]:
            if candidate.is_file():
                return candidate
        return root / "dataset/vinmec_m1_307/masks" / f"{image.stem}.png"
    elif "/Vinmec_CEUS/image/" in source:
        folder = "dataset/Vinmec_CEUS/label"
    elif "/Vinmec_2D/train/train_image/" in source:
        folder = "dataset/Vinmec_2D/train/train_label/label"
    elif "/Vinmec_2D/test/image/" in source:
        folder = "dataset/Vinmec_2D/test/label/black_write"
    else:
        raise ValueError(f"Unknown Milestone 1 image layout: {image_path}")
    return root / folder / f"{image.stem}.PNG"



def audit_m1_scope(root: Path) -> dict:
    active = {name: _rows(root / "ai_training/splits" / f"{name}.csv") for name in SPLITS}
    archive = {
        name: _rows(root / "ai_training/splits/archive_milestone_1" / f"{name}.csv")
        for name in SPLITS
    }
    def identity(row: dict[str, str]) -> tuple[str, str, str, str]:
        return row["case_id"], row["patient_id"], row["is_empty_mask"], row["subset"]
    patients = {name: {row["patient_id"] for row in rows} for name, rows in active.items()}
    all_rows = [row for rows in active.values() for row in rows]
    empty = [row for row in all_rows if row["is_empty_mask"].lower() == "true"]
    native_masks = [_native_mask(root, row["image_path"]) for row in empty]
    native_arrays = [cv2.imread(str(path), cv2.IMREAD_GRAYSCALE) for path in native_masks]
    derived_masks = [cv2.imread(str(root / row["mask_path"]), cv2.IMREAD_GRAYSCALE) for row in empty]

    return {
        "reference": "Milestone 1, 307 records; not the 2026-10-03 retraining split",
        "split_counts": {name: len(rows) for name, rows in active.items()},
        "archive_membership_matches_current": all(
            sorted(map(identity, active[name])) == sorted(map(identity, archive[name]))
            for name in SPLITS
        ),
        "archive_split_sha256": {
            name: hashlib.sha256(
                (root / "ai_training/splits/archive_milestone_1" / f"{name}.csv").read_bytes()
            ).hexdigest()
            for name in SPLITS
        },
        "recorded_pid_labels": len(set.union(*patients.values())),
        "recorded_pid_labels_disjoint": all(
            not patients[left] & patients[right]
            for index, left in enumerate(SPLITS)
            for right in SPLITS[index + 1 :]
        ),
        "source_patient_identity_verified": False,
        "declared_empty_mask_records": len(empty),
        "missing_empty_mask_files": sum(
            not (root / row["mask_path"]).is_file() for row in empty
        ),
        "derived_empty_mask_files": sum(
            mask is not None and mask.shape == (512, 512) and not mask.any()
            for mask in derived_masks
        ),
        "missing_nonempty_mask_files": sum(
            not (root / row["mask_path"]).is_file()
            for row in all_rows
            if row["is_empty_mask"].lower() != "true"
        ),
        "missing_image_files": sum(not (root / row["image_path"]).is_file() for row in all_rows),
        "unreadable_image_mask_pairs": sum(
            cv2.imread(str(root / row["image_path"]), cv2.IMREAD_GRAYSCALE) is None
            or cv2.imread(str(root / row["mask_path"]), cv2.IMREAD_GRAYSCALE) is None
            for row in all_rows
        ),
        "native_positive_masks_for_empty_records": sum(
            mask is not None and bool(mask.max() > 0) for mask in native_arrays
        ),
        "native_masks_missing_for_empty_records": sum(mask is None for mask in native_arrays),
        "note": "Declared empty controls are derived zero masks for pipeline compatibility, not verified clinical negatives. Native labels of those same images contain positive pixels.",
    }


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    output = project_root / "evaluation/milestone_2_m1_scope/data_audit_2026-10-04.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(audit_m1_scope(project_root), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(output)
