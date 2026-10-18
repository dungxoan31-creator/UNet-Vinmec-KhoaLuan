"""Trace missing M1 files to retained sources without reconstructing ground truth."""

import csv
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evaluation/milestone_3_2026-10-07"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    rows = [row for split in ("train", "val", "test") for row in read_csv(ROOT / f"ai_training/splits/{split}.csv")]
    index = {
        source: entry
        for entry in read_csv(ROOT / "dataset/index.csv")
        for source in entry["source_image_paths"].split(";")
    }
    results = []
    for row in rows:
        stem = Path(row["image_path"]).stem.split("_", 1)[1]
        candidates = []
        for group in ("2d", "3d"):
            image = ROOT / "dataset" / group / "images" / f"{stem}.JPG"
            mask = ROOT / "dataset" / group / "masks" / f"{stem}{'_binary' if group == '2d' else ''}.PNG"
            decoded = cv2.imread(str(image), cv2.IMREAD_GRAYSCALE) if image.is_file() else None
            if decoded is not None and decoded.shape == (int(row["image_height"]), int(row["image_width"])):
                candidates.append((group, image, mask))
        entry = index.get(row["image_path"])
        result = {
            "case_id": row["case_id"],
            "split": row["split"],
            "declared_empty_control": row["is_empty_mask"].lower() == "true",
            "missing_m1_image_path": row["image_path"],
            "missing_m1_mask_path": row["mask_path"],
            "original_image_present": (ROOT / row["image_path"]).is_file(),
            "original_mask_present": (ROOT / row["mask_path"]).is_file(),
            "current_image_candidates_by_name_and_shape": len(candidates),
            "current_image_path": "",
            "current_image_sha256": "",
            "image_hash_matches_canonical_index": "not_indexed",
            "current_native_mask_path": "",
            "current_native_mask_sha256": "",
            "native_mask_shape_matches_m1_metadata": "not_applicable",
            "native_foreground_matches_m1_metadata": "not_applicable",
            "native_foreground_pixels": "",
            "m1_mask_pixel_equivalence": "unknown_original_file_missing",
        }
        if len(candidates) == 1:
            _, image, mask = candidates[0]
            result["current_image_path"] = image.relative_to(ROOT).as_posix()
            result["current_image_sha256"] = sha256(image)
            if entry is not None:
                result["image_hash_matches_canonical_index"] = result["current_image_sha256"] == entry["image_sha256"]
            if mask.is_file():
                decoded_mask = cv2.imread(str(mask), cv2.IMREAD_GRAYSCALE)
                if decoded_mask is not None:
                    foreground = int((decoded_mask > 0).sum())
                    result["current_native_mask_path"] = mask.relative_to(ROOT).as_posix()
                    result["current_native_mask_sha256"] = sha256(mask)
                    result["native_foreground_pixels"] = foreground
                    if not result["declared_empty_control"]:
                        result["native_mask_shape_matches_m1_metadata"] = decoded_mask.shape == (
                            int(row["mask_height"]),
                            int(row["mask_width"]),
                        )
                        result["native_foreground_matches_m1_metadata"] = foreground == int(row["positive_pixels"])
        results.append(result)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT / "m1_recoverability.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    counts = Counter()
    for result in results:
        counts["rows"] += 1
        counts["unique_image_matches"] += result["current_image_candidates_by_name_and_shape"] == 1
        counts["index_image_hash_matches"] += result["image_hash_matches_canonical_index"] is True
        counts["not_in_canonical_index"] += result["image_hash_matches_canonical_index"] == "not_indexed"
        counts["nonempty_native_shape_matches"] += result["native_mask_shape_matches_m1_metadata"] is True
        counts["nonempty_native_foreground_matches"] += result["native_foreground_matches_m1_metadata"] is True
        counts["empty_control_native_mask_positive"] += result["declared_empty_control"] and int(
            result["native_foreground_pixels"] or 0
        ) > 0
        counts["original_image_files_present"] += result["original_image_present"]
        counts["original_mask_files_present"] += result["original_mask_present"]
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "command": "python -m scripts.audit_m1_recoverability",
        "counts": dict(counts),
        "rows_csv": csv_path.relative_to(ROOT).as_posix(),
        "conclusion": "Retained sources can be matched technically, but missing original M1 mask bytes prevent an exact M1 replay. Derived empty controls are not clinical negatives.",
        "dataset_or_split_modified": False,
    }
    (OUTPUT / "m1_recoverability_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(dict(counts)))


if __name__ == "__main__":
    main()
