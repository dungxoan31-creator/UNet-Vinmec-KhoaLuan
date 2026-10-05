"""Create metadata-only synthetic Patient-Level Split rows matching the milestone report."""

import argparse
import csv
import json
import random
from pathlib import Path

TARGETS = {
    "train": {"images": 215, "patients": 130, "empty_masks": 25},
    "val": {"images": 46, "patients": 27, "empty_masks": 5},
    "test": {"images": 46, "patients": 28, "empty_masks": 5},
}
FIELDS = ("sample_id", "patient_id", "split", "is_empty_mask", "record_type")


def build_demo(seed: int = 42) -> tuple[list[dict], list[dict], dict]:
    rng = random.Random(seed)
    samples: list[dict] = []
    patients: list[dict] = []
    sample_number = 1
    patient_number = 1

    for split, target in TARGETS.items():
        group_sizes = [2] * (target["images"] - target["patients"]) + [1] * (2 * target["patients"] - target["images"])
        rng.shuffle(group_sizes)
        split_groups = []
        for size in group_sizes:
            patient_id = f"SYN-PAT-{patient_number:03d}"
            patient_number += 1
            group = []
            for _ in range(size):
                sample = {
                    "sample_id": f"SYN-IMG-{sample_number:04d}",
                    "patient_id": patient_id,
                    "split": split,
                    "is_empty_mask": False,
                    "record_type": "synthetic_demo_only",
                }
                sample_number += 1
                samples.append(sample)
                group.append(sample)
            split_groups.append((patient_id, group))

        # Match the report's empty-mask totals, assigning at most one per synthetic patient.
        candidate_groups = list(range(len(split_groups)))
        rng.shuffle(candidate_groups)
        for group_index in candidate_groups[: target["empty_masks"]]:
            _, group = split_groups[group_index]
            rng.choice(group)["is_empty_mask"] = True

        for patient_id, group in split_groups:
            patients.append({
                "patient_id": patient_id,
                "split": split,
                "image_count": len(group),
                "empty_mask_count": sum(row["is_empty_mask"] for row in group),
                "record_type": "synthetic_demo_only",
            })

    summary = {}
    for split, target in TARGETS.items():
        split_rows = [row for row in samples if row["split"] == split]
        split_patients = [row for row in patients if row["split"] == split]
        summary[split] = {
            "images": len(split_rows),
            "patients": len(split_patients),
            "empty_masks": sum(row["is_empty_mask"] for row in split_rows),
            "image_percentage": round(len(split_rows) / len(samples) * 100, 2),
            "empty_mask_percentage": round(sum(row["is_empty_mask"] for row in split_rows) / len(split_rows) * 100, 2),
        }
        assert summary[split]["images"] == target["images"]
        assert summary[split]["patients"] == target["patients"]
        assert summary[split]["empty_masks"] == target["empty_masks"]

    patient_sets = {
        split: {row["patient_id"] for row in samples if row["split"] == split}
        for split in TARGETS
    }
    assert not (patient_sets["train"] & patient_sets["val"])
    assert not (patient_sets["train"] & patient_sets["test"])
    assert not (patient_sets["val"] & patient_sets["test"])
    assert len(samples) == 307 and len(patients) == 185
    return samples, patients, summary


def write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("ai_training/splits/mock_vinmec_report_307"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)

    samples, patients, summary = build_demo(args.seed)
    write_csv(output / "all_samples.csv", samples, FIELDS)
    write_csv(output / "patient_mapping.csv", patients, ("patient_id", "split", "image_count", "empty_mask_count", "record_type"))
    for split in TARGETS:
        write_csv(output / f"{split}.csv", [row for row in samples if row["split"] == split], FIELDS)

    manifest = {
        "title": "Synthetic Patient-Level Split matching Milestone 1 report counts",
        "report_reference": "docs/reports/BaoCaoTienDoMoc1_NguyenHuuDung_11235559(1).docx",
        "synthetic_demo_only": True,
        "usable_for_training": False,
        "seed": args.seed,
        "total_images": len(samples),
        "total_patients": len(patients),
        "total_empty_masks": sum(row["is_empty_mask"] for row in samples),
        "split_level": "synthetic patient groups; no real patient metadata used",
        "patient_overlap_between_splits": 0,
        "split_summary": summary,
        "sample_assignment": "Synthetic sample IDs and patient IDs; group sizes are artificial and do not encode real patient relationships.",
        "label_assignment": "Empty-mask flags are synthetic and assigned to match reported counts; no annotation files were read or altered.",
        "warning": "This metadata is only for teaching/demo of split logic. It is not Vinmec data, not verified Patient-Level Split evidence, and must not be used to train, evaluate, or support clinical claims.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (output / "README.md").write_text(
        "# Synthetic Patient-Level Split demo\n\n"
        "This metadata-only dataset is generated for student exercises. Every sample ID, patient ID, grouping, and empty-mask flag is synthetic. It contains no image or mask paths and cannot be loaded for model training.\n\n"
        "| Split | Images | Synthetic patients | Synthetic empty masks | Image share | Empty-mask share |\n"
        "|---|---:|---:|---:|---:|---:|\n"
        + "".join(f"| {split.title()} | {v['images']} | {v['patients']} | {v['empty_masks']} | {v['image_percentage']:.2f}% | {v['empty_mask_percentage']:.2f}% |\n" for split, v in summary.items())
        + "\nThe counts reproduce the cited report for simulation only. They do not validate the report's underlying Vinmec data or patient-level independence.\n",
        encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(output), "summary": summary, "synthetic_demo_only": True}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
