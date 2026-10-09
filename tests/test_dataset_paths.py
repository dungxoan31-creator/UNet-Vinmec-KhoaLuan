import csv
import hashlib
from pathlib import Path

from backend.core.dataset_paths import resolve_dataset_path

ROOT = Path(__file__).resolve().parents[1]


def test_relocated_validation_image_keeps_recorded_bytes():
    path = resolve_dataset_path(ROOT, "dataset/Vinmec/Vinmec_2d/images/1098.JPG")
    assert path == ROOT / "dataset/2d/images/1098.JPG"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "0019dc47555bfb7a8b60b9d50cc2b54938dbf1facc654a8b4291c8cbd64b07b6"
    )


def test_relocated_mask_and_missing_historical_mask_are_distinct():
    assert resolve_dataset_path(ROOT, "dataset/Vinmec/Vinmec_2d/annotations/1098_binary.PNG") == (
        ROOT / "dataset/2d/masks/1098_binary.PNG"
    )
    missing = resolve_dataset_path(ROOT, "dataset/vinmec_ovarian/empty_masks/empty_mask_001.png")
    assert not missing.exists()


def test_frozen_split_still_resolves_to_same_source_images():
    split_dir = ROOT / "ai_training/splits/unified_vinmec_clean_2026-10-06"
    total = 0
    for name in ("train", "val", "test"):
        with (split_dir / f"{name}.csv").open(newline="", encoding="utf-8-sig") as source:
            for row in csv.DictReader(source):
                image = resolve_dataset_path(ROOT, row["image_path"])
                mask = resolve_dataset_path(ROOT, row["mask_path"])
                assert image.is_file() and mask.is_file(), row["case_id"]
                assert hashlib.sha256(image.read_bytes()).hexdigest() == row["image_sha256"]
                total += 1
    assert total == 1604


def test_relocated_3d_masks_match_audited_pixel_equivalent_copies():
    """Each retained 3D mask is the exact CEUS copy audited against the canonical binary mask."""
    report = ROOT / "reports/dataset_deduplication_report.csv"
    with report.open(newline="", encoding="utf-8-sig") as source:
        duplicate_masks = {
            row["image_hash"]: row
            for row in csv.DictReader(source)
            if row["source_dataset"] == "Vinmec_CEUS"
        }
    provenance_path = ROOT / "evaluation/milestone_3_audit_2026-10-06/verified_data/mask_provenance.csv"
    with provenance_path.open(newline="", encoding="utf-8-sig") as source:
        provenance = {row["sample_id"]: row for row in csv.DictReader(source)}

    checked = 0
    split_dir = ROOT / "ai_training/splits/unified_vinmec_clean_2026-10-06"
    for split in ("train", "val", "test"):
        with (split_dir / f"{split}.csv").open(newline="", encoding="utf-8-sig") as source:
            for row in csv.DictReader(source):
                if "Vinmec_3d" not in row["mask_path"]:
                    continue
                sample_id = row["image_sha256"]
                duplicate = duplicate_masks[sample_id]
                audit = provenance[sample_id]
                assert audit["mapping_status"] == "canonical_and_existing_duplicate_targets_verified"
                assert duplicate["mask_path"] in audit["source_target_paths"].split(";")
                assert duplicate["mask_path"] not in audit["missing_source_paths"].split(";")
                current = resolve_dataset_path(ROOT, row["mask_path"])
                assert hashlib.sha256(current.read_bytes()).hexdigest() == duplicate["mask_hash"]
                checked += 1
    assert checked == 166
