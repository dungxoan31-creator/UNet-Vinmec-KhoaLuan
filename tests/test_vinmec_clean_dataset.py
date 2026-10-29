"""Exercise the clean-dataset builder only against synthetic inputs in pytest tmp_path."""

import csv
import json

import cv2
import numpy as np


def _write_synthetic_pair(image_path, mask_path, center):
    image_path.parent.mkdir(parents=True, exist_ok=True)
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    image = np.zeros((96, 96), dtype=np.uint8)
    cv2.ellipse(image, center, (24, 18), 0, 0, 360, 80, -1)
    cv2.circle(image, center, 7, 20, -1)
    mask = np.zeros_like(image)
    cv2.ellipse(mask, center, (12, 9), 0, 0, 360, 255, -1)
    assert cv2.imwrite(str(image_path), image)
    assert cv2.imwrite(str(mask_path), mask)


def test_builder_copies_and_reports_only_synthetic_pairs(tmp_path, monkeypatch):
    from scripts import build_vinmec_clean_dataset as builder

    source_2d_images = tmp_path / "source/2d/images"
    source_2d_masks = tmp_path / "source/2d/masks"
    source_3d_images = tmp_path / "source/3d/images"
    source_3d_masks = tmp_path / "source/3d/masks"
    source_ceus_images = tmp_path / "source/ceus/images"
    source_ceus_masks = tmp_path / "source/ceus/masks"

    _write_synthetic_pair(
        source_2d_images / "synthetic_left.png",
        source_2d_masks / "synthetic_left_binary.PNG",
        (30, 34),
    )
    _write_synthetic_pair(
        source_3d_images / "synthetic_right.png",
        source_3d_masks / "synthetic_right_binary.PNG",
        (62, 58),
    )
    _write_synthetic_pair(
        source_ceus_images / "synthetic_left.png",
        source_ceus_masks / "synthetic_left.PNG",
        (30, 34),
    )
    # The CEUS entry is an exact synthetic duplicate of the higher-priority 2D image.
    (source_ceus_images / "synthetic_left.png").write_bytes((source_2d_images / "synthetic_left.png").read_bytes())
    (source_ceus_masks / "synthetic_left.PNG").write_bytes((source_2d_masks / "synthetic_left_binary.PNG").read_bytes())

    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(builder, "TARGET_CLEAN", tmp_path / "dataset/Vinmec_clean")
    monkeypatch.setattr(builder, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(
        builder,
        "SOURCES",
        [
            ("Vinmec_2d", source_2d_images, source_2d_masks, "_binary.PNG", "2d"),
            ("Vinmec_3d", source_3d_images, source_3d_masks, "_binary.PNG", "3d"),
            ("Vinmec_CEUS", source_ceus_images, source_ceus_masks, ".PNG", "3d"),
        ],
    )

    builder.main()

    clean = tmp_path / "dataset/Vinmec_clean"
    summary_path = tmp_path / "reports/dataset_deduplication_summary.json"
    report_path = tmp_path / "reports/dataset_deduplication_report.csv"
    assert summary_path.is_file()
    assert report_path.is_file()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["total_initial_images"] == 3
    assert summary["total_duplicate_images_detected"] == 1
    assert summary["total_images_retained_in_clean"] == 2
    assert summary["total_masks_retained_in_clean"] == 2
    assert summary["number_of_images_equals_number_of_masks"] is True
    assert len(list((clean / "2d/images").iterdir())) == 1
    assert len(list((clean / "2d/masks").iterdir())) == 1
    assert len(list((clean / "3d/images").iterdir())) == 1
    assert len(list((clean / "3d/masks").iterdir())) == 1

    with report_path.open(newline="", encoding="utf-8-sig") as source:
        rows = list(csv.DictReader(source))
    assert {row["status"] for row in rows} == {"VALID_PAIR", "DUPLICATE_PAIR"}
    assert {row["source_dataset"] for row in rows} == {"Vinmec_2d", "Vinmec_3d", "Vinmec_CEUS"}
