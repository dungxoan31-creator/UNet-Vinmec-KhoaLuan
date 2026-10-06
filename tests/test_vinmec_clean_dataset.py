"""Unit test for Vinmec_clean dataset integrity and deduplication audit."""

import csv
import hashlib
import json
import os
from pathlib import Path
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CLEAN_DIR = ROOT / "dataset" / "Vinmec_clean"
REPORTS_DIR = ROOT / "reports"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def test_clean_dataset_structure():
    assert CLEAN_DIR.is_dir(), "Vinmec_clean folder does not exist"
    assert (CLEAN_DIR / "2d" / "images").is_dir()
    assert (CLEAN_DIR / "2d" / "masks").is_dir()
    assert (CLEAN_DIR / "3d" / "images").is_dir()
    assert (CLEAN_DIR / "3d" / "masks").is_dir()


def test_exact_pair_counts_and_equality():
    imgs_2d = os.listdir(CLEAN_DIR / "2d" / "images")
    masks_2d = os.listdir(CLEAN_DIR / "2d" / "masks")
    imgs_3d = os.listdir(CLEAN_DIR / "3d" / "images")
    masks_3d = os.listdir(CLEAN_DIR / "3d" / "masks")

    assert len(imgs_2d) == 1469
    assert len(masks_2d) == 1469
    assert len(imgs_3d) == 170
    assert len(masks_3d) == 170

    total_images = len(imgs_2d) + len(imgs_3d)
    total_masks = len(masks_2d) + len(masks_3d)

    assert total_images == 1639
    assert total_masks == 1639
    assert total_images == total_masks


def test_stem_mapping_one_to_one():
    for mod in ["2d", "3d"]:
        img_stems = {Path(f).stem for f in os.listdir(CLEAN_DIR / mod / "images")}
        mask_stems = {Path(f).stem for f in os.listdir(CLEAN_DIR / mod / "masks")}
        assert img_stems == mask_stems, f"Mismatch in stems for {mod}"


def test_zero_duplicate_images_in_clean():
    seen_hashes = set()
    for mod in ["2d", "3d"]:
        for f in os.listdir(CLEAN_DIR / mod / "images"):
            p = CLEAN_DIR / mod / "images" / f
            h = sha256_file(p)
            assert h not in seen_hashes, f"Duplicate image hash detected in clean: {f}"
            seen_hashes.add(h)
    assert len(seen_hashes) == 1639


def test_image_mask_dimension_matches():
    # Sample check 50 random samples in 2d and 3d
    for mod in ["2d", "3d"]:
        imgs = sorted(os.listdir(CLEAN_DIR / mod / "images"))[:25]
        for f in imgs:
            stem = Path(f).stem
            p_img = CLEAN_DIR / mod / "images" / f
            p_mask = CLEAN_DIR / mod / "masks" / f"{stem}.PNG"
            with Image.open(p_img) as im, Image.open(p_mask) as m:
                assert im.size == m.size, f"Size mismatch for {p_img} and {p_mask}"


def test_reports_generated():
    rep_csv = REPORTS_DIR / "dataset_deduplication_report.csv"
    pos_csv = REPORTS_DIR / "possible_duplicates_report.csv"
    sum_json = REPORTS_DIR / "dataset_deduplication_summary.json"

    assert rep_csv.is_file()
    assert pos_csv.is_file()
    assert sum_json.is_file()

    with sum_json.open(encoding="utf-8") as f:
        data = json.load(f)
    assert data["total_initial_images"] == 3011
    assert data["total_duplicate_images_detected"] == 1372
    assert data["total_images_retained_in_clean"] == 1639
    assert data["total_masks_retained_in_clean"] == 1639
    assert data["duplicate_pairs_removed"] == 1372
    assert data["unmatched_files_count"] == 0
    assert data["number_of_images_equals_number_of_masks"] is True
