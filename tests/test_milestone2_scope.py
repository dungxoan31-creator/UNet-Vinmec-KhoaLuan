from pathlib import Path

import cv2
import numpy as np

from ai_training.dataset_loader import OvarianUltrasoundDataset
from evaluation.benchmark_api import milestone_1_validation_case
from scripts.audit_m1_scope import audit_m1_scope
from scripts.generate_m1_empty_masks import generate_empty_masks
from scripts.sanity_check_m1_validation import validation_rows


def test_milestone_2_audit_preserves_milestone_1_membership():
    root = Path(__file__).resolve().parents[1]
    summary = audit_m1_scope(root)

    assert summary["split_counts"] == {"train": 215, "val": 46, "test": 46}
    assert summary["archive_membership_matches_current"] is True
    assert summary["recorded_pid_labels"] == 185
    assert summary["source_patient_identity_verified"] is False
    assert summary["missing_empty_mask_files"] == 0
    assert summary["derived_empty_mask_files"] == 35
    assert summary["unreadable_image_mask_pairs"] == 0
    assert summary["native_positive_masks_for_empty_records"] == 35


def test_latency_probe_uses_milestone_1_validation_only():
    root = Path(__file__).resolve().parents[1]
    case = milestone_1_validation_case(root)

    assert case["split"] == "VAL"
    assert case["is_empty_mask"] == "False"
    assert "vinmec_m1_307" in case["image_path"]
    assert (root / case["image_path"]).is_file()


def test_sanity_check_uses_all_and_only_milestone_1_validation_rows():
    root = Path(__file__).resolve().parents[1]
    rows = validation_rows(root)

    assert len(rows) == 46
    assert all(row["split"] == "VAL" for row in rows)
    assert len({row["case_id"] for row in rows}) == 46
    assert all((root / row["image_path"]).is_file() for row in rows)


def test_generate_empty_masks_and_load_mismatched_raw_image(tmp_path):
    splits = tmp_path / "ai_training/splits"
    splits.mkdir(parents=True)
    image_path = tmp_path / "dataset/Vinmec_2D/train/train_image/1.JPG"
    source_mask = tmp_path / "dataset/Vinmec_2D/train/train_label/label/1.PNG"
    image_path.parent.mkdir(parents=True)
    source_mask.parent.mkdir(parents=True)
    assert cv2.imwrite(str(image_path), np.full((20, 30), 90, dtype=np.uint8))
    assert cv2.imwrite(str(source_mask), np.full((20, 30), 255, dtype=np.uint8))
    fields = "case_id,image_path,mask_path,is_empty_mask,patient_id,split\n"
    mask_path = "dataset/vinmec_ovarian/empty_masks/empty_mask_001.png"
    (splits / "train.csv").write_text(
        fields + f"control_1,dataset/Vinmec_2D/train/train_image/1.JPG,{mask_path},True,ANON-1,TRAIN\n",
        encoding="utf-8",
    )
    for name in ("val", "test"):
        (splits / f"{name}.csv").write_text(fields, encoding="utf-8")

    manifest = generate_empty_masks(tmp_path, expected_count=1)
    assert manifest["record_count"] == 1
    assert manifest["source_positive_count"] == 1
    assert manifest["clinical_negative_verified"] is False
    saved = cv2.imread(str(tmp_path / mask_path), cv2.IMREAD_UNCHANGED)
    assert saved.shape == (512, 512)
    assert saved.dtype == np.uint8
    assert not saved.any()

    dataset = OvarianUltrasoundDataset(splits / "train.csv")
    sample = dataset[0]
    assert tuple(sample["image"].shape) == (1, 512, 512)
    assert tuple(sample["mask"].shape) == (1, 512, 512)
    assert not sample["mask"].any()
