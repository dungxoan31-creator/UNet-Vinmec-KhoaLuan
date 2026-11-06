"""
Unit tests for ai_training.train_boosted_unetplusplus module.
"""

import hashlib
import json

import torch
import torch.nn as nn

from ai_training import train_boosted_unetplusplus as trainer
from ai_training.train_boosted_unetplusplus import build_boosted_model, compute_metrics


def test_build_boosted_model_scse():
    model = build_boosted_model(encoder_name="resnet34", attention_type="scse", pretrained_weights=None)
    x = torch.randn(1, 1, 128, 128)
    out = model(x)
    assert out.shape == (1, 1, 128, 128)


def test_compute_metrics_accuracy():
    logits = torch.tensor([[[[10.0, 10.0], [-10.0, -10.0]]]])  # 2 positive, 2 negative
    targets = torch.tensor([[[[1.0, 1.0], [0.0, 0.0]]]])       # Perfect match
    metrics = compute_metrics(logits, targets, threshold=0.5)

    assert metrics["dice"].item() == 1.0
    assert metrics["iou"].item() == 1.0
    assert metrics["recall"].item() == 1.0
    assert metrics["precision"].item() == 1.0
    assert metrics["specificity"].item() == 1.0


def test_run_summary_preserves_validated_split_provenance(tmp_path, monkeypatch):
    from pathlib import Path

    split_dir = tmp_path / "split"
    split_dir.mkdir()
    (split_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (split_dir / "train.csv").write_text("image_path,mask_path\ntrain.png,train-mask.png\n", encoding="utf-8")
    (split_dir / "val.csv").write_text("image_path,mask_path\nval.png,val-mask.png\n", encoding="utf-8")
    (split_dir / "test.csv").write_text("image_path,mask_path\ntest.png,test-mask.png\n", encoding="utf-8")
    output_dir = tmp_path / "output"
    integrity = {
        "status": "image_level_verified",
        "patient_level_independence_verified": False,
        "unique_image_hashes": 3,
        "integrity_checked_splits": ["train", "val", "test"],
        "test_split_integrity_inspected": True,
    }

    class TinyDataset(torch.utils.data.Dataset):
        def __len__(self):
            return 1

        def __getitem__(self, _index):
            return {"image": torch.zeros(1, 16, 16), "mask": torch.zeros(1, 16, 16)}

    class TinyModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.encoder = nn.Conv2d(1, 1, kernel_size=1)
            self.decoder = nn.Conv2d(1, 1, kernel_size=1)
            self.segmentation_head = nn.Conv2d(1, 1, kernel_size=1)

        def forward(self, image):
            return self.segmentation_head(self.decoder(self.encoder(image)))

    monkeypatch.setattr(trainer, "validate_training_split_integrity", lambda _path: integrity)
    dataset_csvs = []

    def build_dataset(csv_file, *_args, **_kwargs):
        dataset_csvs.append(Path(csv_file).name)
        return TinyDataset()

    monkeypatch.setattr(trainer, "OvarianUltrasoundDataset", build_dataset)
    monkeypatch.setattr(trainer, "validate_splits", lambda *_args: None)
    monkeypatch.setattr(trainer, "build_boosted_model", lambda **_kwargs: TinyModel())
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(
        trainer,
        "evaluate_loader",
        lambda *_args, **_kwargs: {
            "loss": 0.2, "dice": 0.5, "iou": 0.4,
            "recall": 0.5, "precision": 0.5, "specificity": 0.5,
        },
    )

    summary = trainer.run_training(
        split_dir=split_dir,
        output_dir=output_dir,
        epochs=1,
        batch_size=1,
        gradient_accumulation_steps=1,
        patience=1,
    )

    assert summary["split_integrity"] == integrity
    expected_hashes = {
        name: hashlib.sha256((split_dir / filename).read_bytes()).hexdigest()
        for name, filename in (
            ("manifest_sha256", "manifest.json"),
            ("train_csv_sha256", "train.csv"),
            ("validation_csv_sha256", "val.csv"),
            ("test_csv_sha256", "test.csv"),
        )
    }
    assert summary["split_provenance"] == {
        "split_dir": str(split_dir.resolve()),
        **expected_hashes,
    }
    assert summary["test_split_used_for_training_or_selection"] is False
    assert "test_split_accessed" not in summary
    assert dataset_csvs == ["train.csv", "val.csv"]
    persisted = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert persisted["split_integrity"]["patient_level_independence_verified"] is False
    assert persisted["split_integrity"]["test_split_integrity_inspected"] is True
    assert persisted["test_split_used_for_training_or_selection"] is False
