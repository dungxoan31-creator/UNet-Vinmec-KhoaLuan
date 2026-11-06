import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import torch

import ai_training.finetune_2d_unet as finetuning
import ai_training.train_baseline_unet as baseline
import ai_training.train_full_unet as full_training
from ai_training.train_full_unet import train_full
from tests.patient_split_fixture import attach_source_identity_evidence


def test_full_trainer_rejects_incomplete_image_level_split_before_writing_output(tmp_path):
    split_dir = tmp_path / "image-level-only"
    split_dir.mkdir()
    (split_dir / "manifest.json").write_text(
        json.dumps({"status": "ready_for_image_level_training"}), encoding="utf-8"
    )
    output_dir = tmp_path / "checkpoints"

    with pytest.raises(ValueError, match="Required train split"):
        train_full(split_dir=split_dir, output_dir=output_dir, epochs=1)

    assert not output_dir.exists()


def test_full_trainer_uses_train_and_validation_only_and_selects_by_validation(tmp_path, monkeypatch):
    split_dir = tmp_path / "verified-split"
    split_dir.mkdir()
    counts = {}
    for index, split in enumerate(("train", "val", "test"), start=1):
        image_path = split_dir / "images" / f"{split}.png"
        mask_path = split_dir / "masks" / f"{split}.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        mask_path.parent.mkdir(parents=True, exist_ok=True)
        assert cv2.imwrite(str(image_path), np.full((24, 32), index, dtype=np.uint8))
        assert cv2.imwrite(str(mask_path), np.zeros((24, 32), dtype=np.uint8))
        row = {
            "case_id": f"case-{split}",
            "patient_id": f"patient-{index}",
            "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "mask_sha256": hashlib.sha256(mask_path.read_bytes()).hexdigest(),
            "image_path": str(image_path),
            "mask_path": str(mask_path),
        }
        with (split_dir / f"{split}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=row.keys())
            writer.writeheader()
            writer.writerow(row)
        counts[split] = 1
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

    opened = []

    class TinyDataset(torch.utils.data.Dataset):
        def __init__(self, csv_file, is_train=False, seed=42):
            opened.append((Path(csv_file).name, is_train))

        def __len__(self):
            return 1

        def __getitem__(self, _index):
            return {"image": torch.ones(1, 8, 8), "mask": torch.zeros(1, 8, 8)}

    monkeypatch.setattr(baseline, "OvarianUltrasoundDataset", TinyDataset)
    monkeypatch.setattr(full_training, "StandardUNet", lambda **_kwargs: torch.nn.Conv2d(1, 1, 1))
    monkeypatch.setattr(finetuning, "StandardUNet", lambda **_kwargs: torch.nn.Conv2d(1, 1, 1))
    monkeypatch.setattr(full_training.torch.cuda, "is_available", lambda: False)
    output_dir = tmp_path / "full-output"

    checkpoint = train_full(split_dir=split_dir, output_dir=output_dir, epochs=1, batch_size=1)

    assert opened == [("train.csv", True), ("val.csv", False)]
    assert checkpoint.is_file()
    config = json.loads((output_dir / "full_unet_run_config.json").read_text(encoding="utf-8"))
    assert config["identity_status"] == "image_level_verified"
    assert config["patient_level_independence_verified"] is False
    assert config["test_split_image_data_used"] is False
    history = json.loads((output_dir / "full_unet_training_history.json").read_text(encoding="utf-8"))
    assert "val_dice" in history[0]

    fine_tuned = finetuning.finetune(
        split_dir=split_dir,
        checkpoint=checkpoint,
        output_dir=tmp_path / "finetune-output",
        epochs=1,
    )

    assert fine_tuned.is_file()
    assert opened == [
        ("train.csv", True),
        ("val.csv", False),
        ("train.csv", True),
        ("val.csv", False),
    ]
