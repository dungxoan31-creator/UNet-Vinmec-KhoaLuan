import csv
import hashlib
import json

import cv2
import numpy as np
import pytest

from ai_training.finetune_2d_unet import finetune, validate_checkpoint_provenance
from tests.patient_split_fixture import attach_source_identity_evidence


def test_finetune_blocks_unverified_split_before_loading_checkpoint_or_writing_output(tmp_path):
    split_dir = tmp_path / "image-level-only"
    split_dir.mkdir()
    (split_dir / "manifest.json").write_text(
        json.dumps({"status": "ready_for_image_level_training"}), encoding="utf-8"
    )
    output_dir = tmp_path / "finetune-output"

    with pytest.raises(ValueError, match="(?i)patient-level independence"):
        finetune(
            split_dir=split_dir,
            checkpoint=tmp_path / "missing-checkpoint.pth",
            output_dir=output_dir,
            epochs=1,
        )

    assert not output_dir.exists()


def test_finetune_rejects_checkpoint_without_verified_training_provenance(tmp_path):
    split_dir = tmp_path / "patient-split"
    split_dir.mkdir()
    counts = {}
    for index, split in enumerate(("train", "val", "test"), start=1):
        image_path = split_dir / f"{split}.jpg"
        mask_path = split_dir / f"{split}.png"
        assert cv2.imwrite(str(image_path), np.full((24, 32), index, dtype=np.uint8))
        assert cv2.imwrite(str(mask_path), np.zeros((24, 32), dtype=np.uint8))
        rows = [{
            "case_id": f"case-{split}",
            "patient_id": f"patient-{index}",
            "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "mask_sha256": hashlib.sha256(mask_path.read_bytes()).hexdigest(),
            "image_path": str(image_path),
            "mask_path": str(mask_path),
        }]
        with (split_dir / f"{split}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        counts[split] = len(rows)
    (split_dir / "manifest.json").write_text(
        json.dumps(
            {
                "patient_ids_verified": True,
                "source_patient_identity_verified": True,
                "split_counts": counts,
            }
        ),
        encoding="utf-8",
    )
    attach_source_identity_evidence(split_dir)
    output_dir = tmp_path / "finetune-output"

    with pytest.raises(ValueError, match="(?i)checkpoint provenance"):
        finetune(
            split_dir=split_dir,
            checkpoint=tmp_path / "unverified-checkpoint.pth",
            output_dir=output_dir,
            epochs=1,
        )

    assert not output_dir.exists()


def test_checkpoint_provenance_rejects_sha256_mismatch(tmp_path):
    checkpoint = tmp_path / "model.pth"
    checkpoint.write_bytes(b"weights")
    provenance = {
        "identity_status": "patient_level_verified",
        "test_split_image_data_used": False,
        "checkpoint_sha256": "0" * 64,
        "checkpoint": str(checkpoint.resolve()),
        "split_manifest_sha256": "1" * 64,
    }
    (tmp_path / "full_unet_run_config.json").write_text(json.dumps(provenance), encoding="utf-8")

    with pytest.raises(ValueError, match="(?i)checkpoint provenance"):
        validate_checkpoint_provenance(checkpoint)


def test_checkpoint_provenance_rejects_different_split_manifest(tmp_path):
    checkpoint = tmp_path / "model.pth"
    checkpoint.write_bytes(b"weights")
    provenance = {
        "identity_status": "patient_level_verified",
        "test_split_image_data_used": False,
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "checkpoint": str(checkpoint.resolve()),
        "split_manifest_sha256": "1" * 64,
    }
    (tmp_path / "full_unet_run_config.json").write_text(json.dumps(provenance), encoding="utf-8")

    with pytest.raises(ValueError, match="(?i)checkpoint provenance"):
        validate_checkpoint_provenance(checkpoint, expected_split_manifest_sha256="2" * 64)
