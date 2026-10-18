"""Join existing near-duplicate candidates to the frozen split without changing data."""

import csv
import hashlib
import json
import statistics
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np

from backend.core.dataset_paths import resolve_dataset_path
from scripts.build_vinmec_clean_dataset import compute_dhash, compute_phash

ROOT = Path(__file__).resolve().parents[1]
SPLIT = ROOT / "ai_training/splits/unified_vinmec_clean_2026-10-06"
SOURCE = ROOT / "reports/possible_duplicates_report.csv"
OUTPUT = ROOT / "evaluation/milestone_3_2026-10-07"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def main() -> None:
    split_rows = {split: read_csv(SPLIT / f"{split}.csv") for split in ("train", "val", "test")}
    split_hashes = {split: {row["image_sha256"] for row in rows} for split, rows in split_rows.items()}
    exact_overlap = sum(
        len(split_hashes[left] & split_hashes[right])
        for left, right in (("train", "val"), ("train", "test"), ("val", "test"))
    )
    samples = {
        row["image_path"]: {**row, "split": split}
        for split, rows in split_rows.items()
        for row in rows
    }
    candidates = read_csv(SOURCE)
    counts: Counter[str] = Counter()
    cross = []
    for candidate in candidates:
        first = samples.get(candidate["image_1_path"])
        second = samples.get(candidate["image_2_path"])
        if first is None or second is None:
            counts["excluded_or_unmatched"] += 1
            continue
        group = "/".join(sorted((first["split"], second["split"])))
        counts[group] += 1
        if first["split"] == second["split"]:
            continue
        paths = [resolve_dataset_path(ROOT, row["image_path"]) for row in (first, second)]
        for path, row in zip(paths, (first, second), strict=True):
            if hashlib.sha256(path.read_bytes()).hexdigest() != row["image_sha256"]:
                raise ValueError(f"Image hash differs from frozen split: {path}")
        images = [cv2.imread(str(path), cv2.IMREAD_GRAYSCALE) for path in paths]
        if any(image is None for image in images):
            raise ValueError(f"Unreadable candidate pair: {paths}")
        phash_distance = int(np.count_nonzero(compute_phash(images[0]) != compute_phash(images[1])))
        dhash_distance = int(np.count_nonzero(compute_dhash(images[0]) != compute_dhash(images[1])))
        if (phash_distance, dhash_distance) != (
            int(candidate["phash_distance"]),
            int(candidate["dhash_distance"]),
        ):
            raise ValueError(f"Perceptual distances differ from candidate report: {paths}")
        normalized = [cv2.resize(image, (256, 256)).astype(np.float32) for image in images]
        cross.append(
            {
                "image_1_path": first["image_path"],
                "split_1": first["split"],
                "image_1_sha256": first["image_sha256"],
                "image_2_path": second["image_path"],
                "split_2": second["split"],
                "image_2_sha256": second["image_sha256"],
                "phash_distance_reported": candidate["phash_distance"],
                "dhash_distance_reported": candidate["dhash_distance"],
                "resized_256_mae": round(float(np.abs(normalized[0] - normalized[1]).mean()), 4),
                "resized_256_correlation": round(float(np.corrcoef(*(image.ravel() for image in normalized))[0, 1]), 6),
                "status": "candidate_only; patient_or_exam_identity_unverified",
            }
        )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "cross_split_near_duplicate_candidates.csv").open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=list(cross[0]))
        writer.writeheader()
        writer.writerows(cross)
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "command": "python -m scripts.audit_cross_split_near_duplicates",
        "candidate_source": SOURCE.relative_to(ROOT).as_posix(),
        "candidate_source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "candidate_count": len(candidates),
        "counts_by_split_pair": dict(counts),
        "cross_split_candidate_count": len(cross),
        "cross_split_candidate_csv": "evaluation/milestone_3_2026-10-07/cross_split_near_duplicate_candidates.csv",
        "exact_sha256_overlap_between_splits": exact_overlap,
        "identity_interpretation": "Perceptual similarity is a review signal, not proof of a shared patient or examination.",
        "coverage_note": "Only the 47 candidates in the existing pHash/dHash <= 2 report were evaluated; other near duplicates may exist.",
    }
    (OUTPUT / "cross_split_near_duplicate_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    sensitivity = {
        "generated_at": datetime.now(UTC).isoformat(),
        "method": "Descriptive subset means from existing per-image CSVs; no training, inference, re-splitting, or corrected-metric claim.",
        "candidate_csv": summary["cross_split_candidate_csv"],
        "results": {},
    }
    for split, metric_file, summary_file, checkpoint in (
        (
            "val",
            ROOT / "evaluation/milestone_3_audit_2026-10-06/validation_replay_2026-10-07/validation_per_image.csv",
            ROOT / "evaluation/milestone_3_audit_2026-10-06/validation_replay_2026-10-07/validation_summary.json",
            "U-Net++ validation lock",
        ),
        (
            "test",
            ROOT / "evaluation/milestone_3_2026-10-06/test_per_image.csv",
            ROOT / "evaluation/milestone_3_2026-10-06/test_summary.json",
            "historical refined Standard U-Net",
        ),
    ):
        scores = {row["image_path"]: float(row["dice"]) for row in read_csv(metric_file)}
        declared = json.loads(summary_file.read_text(encoding="utf-8"))
        declared_mean = (
            declared["metrics"]["dice"]
            if split == "val"
            else declared["segmentation_metrics_only"]["foreground_dice_mean"]
        )
        if abs(statistics.mean(scores.values()) - declared_mean) > 1e-10:
            raise ValueError(f"Per-image Dice differs from {summary_file}")
        flagged = {
            row[f"image_{side}_path"]
            for row in cross
            for side in ("1", "2")
            if row[f"split_{side}"] == split
        }
        if not flagged <= scores.keys():
            raise ValueError(f"Candidate images missing from {split} metric CSV")
        remaining = [score for path, score in scores.items() if path not in flagged]
        sensitivity["results"][split] = {
            "checkpoint_role": checkpoint,
            "source_csv": metric_file.relative_to(ROOT).as_posix(),
            "total_count": len(scores),
            "reported_mean_dice_recomputed": statistics.mean(scores.values()),
            "flagged_candidate_images": len(flagged),
            "flagged_mean_dice": statistics.mean(scores[path] for path in flagged),
            "remaining_count": len(remaining),
            "remaining_mean_dice_descriptive_only": statistics.mean(remaining),
        }
    all_rows = [{**row, "split": split} for split, rows in split_rows.items() for row in rows]
    phashes, dhashes, current_paths = [], [], []
    for row in all_rows:
        path = resolve_dataset_path(ROOT, row["image_path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["image_sha256"]:
            raise ValueError(f"Image hash differs from frozen split: {path}")
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError(f"Unreadable frozen image: {path}")
        current_paths.append(path)
        phashes.append(compute_phash(image))
        dhashes.append(compute_dhash(image))
    phashes, dhashes = np.stack(phashes), np.stack(dhashes)
    expanded = []
    for i, first in enumerate(all_rows):
        pdist = np.count_nonzero(phashes[i] != phashes[i + 1 :], axis=1)
        ddist = np.count_nonzero(dhashes[i] != dhashes[i + 1 :], axis=1)
        for offset in np.flatnonzero((pdist <= 4) | (ddist <= 4)):
            j = i + 1 + int(offset)
            second = all_rows[j]
            if first["split"] == second["split"]:
                continue
            images = [cv2.imread(str(path), cv2.IMREAD_GRAYSCALE) for path in (current_paths[i], current_paths[j])]
            resized = [cv2.resize(image, (256, 256)).astype(np.float32) for image in images]
            expanded.append(
                {
                    "image_1_path": first["image_path"],
                    "split_1": first["split"],
                    "image_2_path": second["image_path"],
                    "split_2": second["split"],
                    "phash_distance": int(pdist[offset]),
                    "dhash_distance": int(ddist[offset]),
                    "resized_256_correlation": round(
                        float(np.corrcoef(*(image.ravel() for image in resized))[0, 1]), 6
                    ),
                }
            )
    old_pairs = {frozenset((row["image_1_path"], row["image_2_path"])) for row in cross}
    expanded_pairs = {frozenset((row["image_1_path"], row["image_2_path"])) for row in expanded}
    if not old_pairs <= expanded_pairs:
        raise ValueError("Strict-threshold candidates missing from expanded scan")
    expanded_path = OUTPUT / "cross_split_expanded_candidates.csv"
    with expanded_path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=list(expanded[0]))
        writer.writeheader()
        writer.writerows(expanded)
    strong = [row for row in expanded if row["resized_256_correlation"] >= 0.95]
    adjacency: dict[str, set[str]] = {}
    split_by_path = {}
    for row in strong:
        left, right = row["image_1_path"], row["image_2_path"]
        adjacency.setdefault(left, set()).add(right)
        adjacency.setdefault(right, set()).add(left)
        split_by_path[left], split_by_path[right] = row["split_1"], row["split_2"]
    components = []
    unseen = set(adjacency)
    while unseen:
        component = set()
        first_path = min(unseen)
        unseen.remove(first_path)
        stack = [first_path]
        while stack:
            path = stack.pop()
            if path in component:
                continue
            component.add(path)
            stack.extend(adjacency[path] - component)
            unseen.discard(path)
        components.append(component)
    components.sort(key=lambda component: min(component))
    three_split_components = [
        [{"image_path": path, "split": split_by_path[path]} for path in sorted(component)]
        for component in components
        if {split_by_path[path] for path in component} == {"train", "val", "test"}
    ]
    expanded_summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "command": "python -m scripts.audit_cross_split_near_duplicates",
        "images_scanned": len(all_rows),
        "image_sha256_verified": len(all_rows),
        "candidate_rule": "pHash distance <= 4 OR dHash distance <= 4, across different frozen splits",
        "cross_split_candidates": len(expanded),
        "previous_strict_candidates_recovered": len(old_pairs),
        "additional_candidates": len(expanded_pairs - old_pairs),
        "candidates_with_resized_correlation_at_least_0_95": len(strong),
        "additional_candidates_with_correlation_at_least_0_95": sum(
            frozenset((row["image_1_path"], row["image_2_path"])) not in old_pairs for row in strong
        ),
        "strong_similarity_components_spanning_all_three_splits": three_split_components,
        "expanded_csv": expanded_path.relative_to(ROOT).as_posix(),
        "interpretation": "Image-similarity candidates only; patient/examination identity remains unverified. The threshold is heuristic and does not establish completeness.",
        "model_inference_performed": False,
    }
    (OUTPUT / "cross_split_expanded_summary.json").write_text(
        json.dumps(expanded_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    sensitivity["expanded_threshold_4_results"] = {}
    for split, result in sensitivity["results"].items():
        scores = {row["image_path"]: float(row["dice"]) for row in read_csv(ROOT / result["source_csv"])}
        flagged = {
            row[f"image_{side}_path"]
            for row in expanded
            for side in ("1", "2")
            if row[f"split_{side}"] == split
        }
        if not flagged <= scores.keys():
            raise ValueError(f"Expanded candidates missing from {split} metric CSV")
        remaining = [score for path, score in scores.items() if path not in flagged]
        sensitivity["expanded_threshold_4_results"][split] = {
            "flagged_candidate_images": len(flagged),
            "flagged_mean_dice": statistics.mean(scores[path] for path in flagged),
            "remaining_count": len(remaining),
            "remaining_mean_dice_descriptive_only": statistics.mean(remaining),
        }
    (OUTPUT / "cross_split_sensitivity.json").write_text(
        json.dumps(sensitivity, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"candidates": len(candidates), "cross_split": len(cross), "groups": dict(counts)}))


if __name__ == "__main__":
    main()
