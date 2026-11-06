import csv
import hashlib
import json
from collections import defaultdict

import scripts.validate_vinmec_datasets as validator


def test_split_audit_resolves_relocated_image_paths(tmp_path):
    image = tmp_path / "dataset/2d/images/frame.JPG"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"image-bytes")
    split_csv = tmp_path / "train.csv"
    with split_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("image_path",))
        writer.writeheader()
        writer.writerow({"image_path": "dataset/Vinmec/Vinmec_2d/images/frame.JPG"})
    assignments, details = defaultdict(set), defaultdict(list)

    validator._read_csv_assignments(tmp_path, split_csv, "train", assignments, details)

    digest = hashlib.sha256(b"image-bytes").hexdigest()
    assert assignments[digest] == {("train", split_csv.as_posix())}
    assert details[digest][0]["image_path"] == "dataset/2d/images/frame.JPG"


def test_split_audit_includes_the_active_unified_manifest(tmp_path):
    image = tmp_path / "dataset/2d/images/active.JPG"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"active-split-image")
    split_dir = tmp_path / "ai_training/splits/unified_vinmec_clean_2026-10-06"
    split_dir.mkdir(parents=True)
    with (split_dir / "train.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("image_path",))
        writer.writeheader()
        writer.writerow({"image_path": "dataset/Vinmec/Vinmec_2d/images/active.JPG"})
    assignments, _ = validator._split_assignments(tmp_path)

    digest = hashlib.sha256(b"active-split-image").hexdigest()
    assert ("unified_train", (split_dir / "train.csv").as_posix()) in assignments[digest]


def test_active_split_summary_checks_files_and_actual_image_bytes(tmp_path):
    summary_builder = getattr(validator, "_active_split_integrity", None)
    assert callable(summary_builder)

    split_dir = tmp_path / "ai_training/splits/unified_vinmec_clean_2026-10-06"
    split_dir.mkdir(parents=True)
    (split_dir / "manifest.json").write_text(
        json.dumps({
            "source_patient_identity_verified": True,
            "patient_ids_verified": True,
            "identity_level": "patient_verified",
            "identity_limit": "No verified source Patient/Case IDs",
            "split_counts": {"train": 1, "val": 1, "test": 1},
        }),
        encoding="utf-8",
    )
    image_dir = tmp_path / "dataset/2d/images"
    mask_dir = tmp_path / "dataset/2d/masks"
    image_dir.mkdir(parents=True)
    mask_dir.mkdir(parents=True)
    shared_image = image_dir / "shared.JPG"
    test_image = image_dir / "test.JPG"
    shared_image.write_bytes(b"same-image")
    test_image.write_bytes(b"test-image")
    for name in ("shared.PNG", "test.PNG"):
        (mask_dir / name).write_bytes(b"mask")
    rows = {
        "train": [("shared.JPG", "shared.PNG", "a" * 64)],
        "val": [("shared.JPG", "shared.PNG", "b" * 64)],
        "test": [("test.JPG", "test.PNG", hashlib.sha256(b"test-image").hexdigest())],
    }
    for split, samples in rows.items():
        with (split_dir / f"{split}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=("case_id", "patient_id", "image_path", "mask_path", "image_sha256"))
            writer.writeheader()
            for index, (image, mask, digest) in enumerate(samples):
                writer.writerow({
                    "case_id": f"{split}-{index}",
                    "patient_id": "SIM-shared" if split in {"train", "val"} else "SIM-test",
                    "image_path": f"dataset/Vinmec/Vinmec_2d/images/{image}",
                    "mask_path": f"dataset/Vinmec/Vinmec_2d/annotations/{mask}",
                    "image_sha256": digest,
                })

    summary = summary_builder(tmp_path)

    assert summary["patient_level_verified"] is False
    assert summary["patient_id_overlap_count"] == 1
    assert summary["declared_hash_overlap_count"] == 0
    assert summary["actual_hash_overlap_count"] == 1
    assert summary["recorded_hash_mismatch_count"] == 2
    assert summary["missing_pair_count"] == 0


def test_active_split_summary_rejects_verified_manifest_without_patient_ids(tmp_path):
    split_dir = tmp_path / "ai_training/splits/unified_vinmec_clean_2026-10-06"
    split_dir.mkdir(parents=True)
    (split_dir / "manifest.json").write_text(
        json.dumps({
            "source_patient_identity_verified": True,
            "patient_ids_verified": True,
            "identity_level": "patient_verified",
            "split_counts": {split: 1 for split in ("train", "val", "test")},
        }),
        encoding="utf-8",
    )
    for split in ("train", "val", "test"):
        (split_dir / f"{split}.csv").write_text(
            "case_id,patient_id\n" f"{split}-case,\n",
            encoding="utf-8",
        )

    summary = validator._active_split_integrity(tmp_path)

    assert summary["patient_level_verified"] is False
    assert summary["patient_ids_present"] == 0


def test_active_split_summary_does_not_verify_missing_partition_csv(tmp_path):
    split_dir = tmp_path / "ai_training/splits/unified_vinmec_clean_2026-10-06"
    split_dir.mkdir(parents=True)
    (split_dir / "manifest.json").write_text(
        json.dumps({
            "source_patient_identity_verified": True,
            "patient_ids_verified": True,
            "identity_level": "patient_verified",
            "split_counts": {split: 1 for split in ("train", "val", "test")},
        }),
        encoding="utf-8",
    )
    for split in ("train", "val"):
        (split_dir / f"{split}.csv").write_text(
            "case_id,patient_id\n" f"{split}-case,P-{split}\n",
            encoding="utf-8",
        )

    summary = validator._active_split_integrity(tmp_path)

    assert summary["manifest_counts_match_csv"] is False
    assert summary["patient_level_verified"] is False


def test_legacy_split_evidence_uses_manifest_and_csv_contents(tmp_path):
    evidence_builder = getattr(validator, "_read_legacy_vinmec_2d_split_evidence", None)
    assert callable(evidence_builder)

    split_dir = tmp_path / "ai_training/splits/full_dataset_2026-10-03/vinmec_split_2d"
    split_dir.mkdir(parents=True)
    (split_dir / "manifest.json").write_text(
        '{"split_level":"sample-level","source_test_included_in_pool":true}',
        encoding="utf-8",
    )
    for name, paths in {
        "train": ["dataset/Vinmec_2D/test/image/1.JPG", "dataset/Vinmec_2D/train/train_image/2.JPG"],
        "val": ["dataset/Vinmec_2D/test/image/3.JPG"],
        "test": [],
    }.items():
        with (split_dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=("image_path",))
            writer.writeheader()
            writer.writerows({"image_path": path} for path in paths)

    evidence = evidence_builder(tmp_path)

    assert evidence["source_test_included_in_pool"] is True
    assert evidence["split_level"] == "sample-level"
    assert evidence["split_counts"] == {"train": 2, "val": 1, "test": 0}
    assert evidence["source_test_rows_in_train_val"] == {"train": 1, "val": 1}
    assert evidence["source_test_count"] == 2


def test_m1_summary_does_not_count_missing_referenced_native_labels(tmp_path):
    summarizer = getattr(validator, "_summarize_m1_empty_masks", None)
    assert callable(summarizer)

    summary = summarizer(
        [
            {
                "status": "derived_empty_mask_requires_source_label_review",
                "fallback_mask_exists": "false",
                "fallback_mask_readable": "false",
                "fallback_mask_empty": "false",
                "label_path": "dataset/native/label.PNG",
                "native_target_exists": "false",
                "native_target_pixels": "",
                "native_target_shape_matches": "false",
            }
        ],
        provenance_exists=False,
    )

    assert summary["count"] == 1
    assert summary["fallback_masks_present"] == 0
    assert summary["native_source_labels_found"] == 0
    assert summary["native_source_labels_positive"] == 0
    assert "unavailable" in summary["audit_note"]
