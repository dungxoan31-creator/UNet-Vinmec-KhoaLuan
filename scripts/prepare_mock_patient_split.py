"""Create demo-only synthetic groups; these IDs are not patient identifiers."""

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path

import cv2

from scripts.prepare_vinmec import _pairs


def prepare_mock_splits(data_dir: Path, output_dir: Path, val_fraction: float = 0.15, seed: int = 42) -> dict:
    if not 0 < val_fraction < 1:
        raise ValueError("val_fraction must be between zero and one")
    train_pool = _pairs(data_dir / "train/train_image", data_dir / "train/train_label/label")
    test_pool = _pairs(data_dir / "test/image", data_dir / "test/label/black_write")
    hashes = [row["image_sha256"] for row in train_pool + test_pool]
    if len(hashes) != len(set(hashes)):
        raise ValueError("Exact duplicate image across the source train/test pool")

    case_ids = [row["case_id"] for row in train_pool + test_pool]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Image IDs must be unique across the source pools")
    random_generator = random.Random(seed)

    def make_groups(rows, source):
        random_generator.shuffle(rows)
        groups = []
        offset = 0
        while offset < len(rows):
            group = rows[offset:offset + random_generator.choice((1, 1, 2, 2, 3, 4))]
            group_id = hashlib.blake2s(f"{seed}:{source}:{len(groups)}".encode(), digest_size=5).hexdigest().upper()
            for row in group:
                row["patient_id"] = f"SIM-{group_id}"
            groups.append(group)
            offset += len(group)
        return groups

    train_groups = make_groups(train_pool, "train")
    test_groups = make_groups(test_pool, "test")
    random_generator.shuffle(train_groups)
    n_val = max(1, round(len(train_groups) * val_fraction))
    if n_val >= len(train_groups):
        raise ValueError("No training groups remain")
    groups_by_split = {
        "train": train_groups[n_val:],
        "val": train_groups[:n_val],
        "test": test_groups,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    with (output_dir / "synthetic_patient_mapping.csv").open("w", newline="", encoding="utf-8") as mapping_stream:
        mapping_writer = csv.DictWriter(mapping_stream, fieldnames=("image_id", "patient_id", "label"))
        mapping_writer.writeheader()
        for split, groups in groups_by_split.items():
            rows = [row for group in groups for row in group]
            counts[split] = len(rows)
            with (output_dir / f"{split}.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            for row in rows:
                mask = cv2.imread(row["mask_path"], cv2.IMREAD_GRAYSCALE)
                mapping_writer.writerow({
                    "image_id": row["case_id"],
                    "patient_id": row["patient_id"],
                    "label": int(cv2.countNonZero(mask) > 0),
                })

    summary = {
        "source": str(data_dir),
        "seed": seed,
        "val_fraction": val_fraction,
        "counts": counts,
        "split_level": "synthetic_group_demo",
        "patient_ids_verified": False,
        "source_test_preserved": True,
        "group_assignment": "Artificial groups of 1-4 images, sampled for software testing; not based on patient metadata",
        "label_definition": "1 if the supplied pixel mask has foreground, otherwise 0; not a diagnosis",
        "warning": "SIM IDs are synthetic; group disjointness does not establish patient independence or prevent clinical data leakage.",
    }
    (output_dir / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("dataset/Vinmec_2D"))
    parser.add_argument("--output-dir", type=Path, default=Path("ai_training/splits/mock_patient_2d"))
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(prepare_mock_splits(args.data_dir, args.output_dir, args.val_fraction, args.seed), indent=2))
