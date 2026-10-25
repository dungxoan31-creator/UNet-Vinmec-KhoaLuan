import csv
import hashlib
import json

import albumentations as A
import cv2
import numpy as np
import pytest
import torch
from torch.utils.data import DataLoader

from ai_training.dataset_loader import get_dataloaders
from ai_training.train_baseline_unet import (
    compute_batch_dice,
    compute_batch_metrics,
    load_initial_checkpoint,
    train_baseline,
)
from scripts.prepare_vinmec import prepare_splits
from tests.patient_split_fixture import attach_source_identity_evidence
from tests.test_vinmec_pipeline import _pair


def _write_verified_patient_split(split_dir):
    split_dir.mkdir(parents=True)
    counts = {}
    for split in ("train", "val", "test"):
        image_path = split_dir / f"{split}.jpg"
        mask_path = split_dir / f"{split}.png"
        assert cv2.imwrite(str(image_path), np.full((24, 32), len(counts) + 1, dtype=np.uint8))
        assert cv2.imwrite(str(mask_path), np.zeros((24, 32), dtype=np.uint8))
        with (split_dir / f"{split}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=("case_id", "patient_id", "image_path", "mask_path", "image_sha256", "mask_sha256"),
            )
            writer.writeheader()
            writer.writerow({
                "case_id": f"case-{split}",
                "patient_id": f"patient-{split}",
                "image_path": str(image_path),
                "mask_path": str(mask_path),
                "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                "mask_sha256": hashlib.sha256(mask_path.read_bytes()).hexdigest(),
            })
        counts[split] = 1
    (split_dir / "manifest.json").write_text(
        json.dumps({
            "patient_ids_verified": True,
            "source_patient_identity_verified": True,
            "split_counts": counts,
        }),
        encoding="utf-8",
    )
    attach_source_identity_evidence(split_dir)


def test_dice_weights_each_case_equally():
    logits = torch.tensor([[[[10.0, 10.0]]], [[[-10.0, -10.0]]]])
    masks = torch.ones_like(logits)
    assert abs(compute_batch_dice(logits, masks) - 0.5) < 1e-4


def test_empty_ground_truth_recall_matches_evaluator_convention():
    metrics = compute_batch_metrics(torch.full((1, 1, 2, 2), 10.0), torch.zeros(1, 1, 2, 2))
    assert metrics["dice"].item() == 0.0
    assert metrics["iou"].item() == 0.0
    assert metrics["recall"].item() == 1.0


def test_initial_checkpoint_loads_all_weights_strictly(tmp_path):
    source = torch.nn.Conv2d(1, 1, 1)
    checkpoint = tmp_path / "initial.pth"
    torch.save(source.state_dict(), checkpoint)
    target = torch.nn.Conv2d(1, 1, 1)

    digest = load_initial_checkpoint(target, checkpoint, torch.device("cpu"))

    assert len(digest) == 64
    assert all(torch.equal(source.state_dict()[key], target.state_dict()[key]) for key in source.state_dict())


def test_initial_checkpoint_rejects_architecture_mismatch(tmp_path):
    checkpoint = tmp_path / "initial.pth"
    torch.save(torch.nn.Conv2d(1, 1, 1).state_dict(), checkpoint)

    with pytest.raises(RuntimeError):
        load_initial_checkpoint(torch.nn.Conv2d(2, 1, 1), checkpoint, torch.device("cpu"))


def test_training_augmentation_is_reproducible(tmp_path):
    for stem in range(6):
        _pair(tmp_path, "train", str(stem))
    _pair(tmp_path, "test", "9")
    splits = tmp_path / "splits"
    prepare_splits(tmp_path, splits, val_fraction=0.3)
    first, _, _ = get_dataloaders(splits, batch_size=2, seed=17)
    second, _, _ = get_dataloaders(splits, batch_size=2, seed=17)
    geometry = next(
        transform
        for transform in first.dataset.transform.transforms
        if isinstance(transform, A.Affine)
    )
    assert type(geometry) is A.Affine
    assert geometry.scale == {"x": (0.95, 1.05), "y": (0.95, 1.05)}
    assert geometry.translate_percent == {
        "x": (-0.05, 0.05),
        "y": (-0.05, 0.05),
    }
    assert geometry.rotate == (-10.0, 10.0)
    assert geometry.mask_interpolation == cv2.INTER_NEAREST
    assert geometry.border_mode == cv2.BORDER_CONSTANT
    assert geometry.p == 0.4
    for first_batch, second_batch in zip(first, second):
        assert first_batch["case_id"] == second_batch["case_id"]
        assert torch.equal(first_batch["image"], second_batch["image"])
        assert torch.equal(first_batch["mask"], second_batch["mask"])


def test_training_persists_metrics_and_configuration_each_epoch(tmp_path, monkeypatch):
    split_dir = tmp_path / "patient-level-split"
    _write_verified_patient_split(split_dir)
    samples = [
        {"image": torch.ones(1, 8, 8), "mask": torch.ones(1, 8, 8)},
        {"image": torch.zeros(1, 8, 8), "mask": torch.zeros(1, 8, 8)},
        {"image": torch.ones(1, 8, 8), "mask": torch.ones(1, 8, 8)},
    ]
    loader = DataLoader(samples, batch_size=2)
    monkeypatch.setattr("ai_training.train_baseline_unet.get_train_val_dataloaders", lambda **kwargs: (loader, loader))
    def tiny_model(**kwargs):
        model = torch.nn.Conv2d(1, 1, 1)
        with torch.no_grad():
            model.weight.fill_(1.0)
            model.bias.fill_(0.5)
        return model

    monkeypatch.setattr("ai_training.train_baseline_unet.StandardUNet", tiny_model)
    checkpoint = train_baseline(epochs=2, batch_size=2, checkpoint_dir=str(tmp_path), seed=17, patience=8, splits_dir=str(split_dir))
    assert torch.load(checkpoint, map_location="cpu", weights_only=True)
    assert torch.load(tmp_path / "baseline_unet_last.pth", map_location="cpu", weights_only=True)
    history = json.loads((tmp_path / "vinmec_unet_best_history.json").read_text())
    assert len(history) == 2
    assert all({"val_dice", "val_iou", "val_recall", "elapsed_seconds"} <= row.keys() for row in history)
    assert all(abs(row["val_dice"] - 0.6667) < 1e-4 for row in history)
    config = json.loads((tmp_path / "run_config.json").read_text())
    assert config["seed"] == 17
    assert config["batch_size"] == 2
    assert config["device"] in {"cpu", "cuda"}
    assert config["train_samples"] == len(samples)
    assert config["optimizer"] == "AdamW(weight_decay=1e-4)"
    assert config["scheduler"] == "CosineAnnealingLR(eta_min=1e-6)"
    assert config["validation_metric"] == "mean per-image Dice at 512x512, threshold 0.5"


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA AMP overflow requires a GPU")
def test_amp_gradient_overflow_skips_update_instead_of_crashing(tmp_path, monkeypatch):
    import ai_training.train_baseline_unet as baseline_unet

    split_dir = tmp_path / "patient-level-split"
    _write_verified_patient_split(split_dir)
    samples = [{"image": torch.ones(1, 8, 8), "mask": torch.zeros(1, 8, 8)}] * 2
    loader = DataLoader(samples, batch_size=2)
    monkeypatch.setattr("ai_training.train_baseline_unet.get_train_val_dataloaders", lambda **kwargs: (loader, loader))
    initial_weights = {}

    def tiny_model(**kwargs):
        model = torch.nn.Conv2d(1, 1, 1)
        initial_weights.update({name: value.clone() for name, value in model.state_dict().items()})
        return model

    monkeypatch.setattr("ai_training.train_baseline_unet.StandardUNet", tiny_model)
    scaler_type = torch.amp.GradScaler
    monkeypatch.setattr("ai_training.train_baseline_unet.torch.amp.GradScaler", lambda device, enabled: scaler_type(device, enabled=enabled, init_scale=2.0**30))
    schedulers = []
    cosine_annealing_lr = torch.optim.lr_scheduler.CosineAnnealingLR

    def create_scheduler(*args, **kwargs):
        scheduler = cosine_annealing_lr(*args, **kwargs)
        schedulers.append(scheduler)
        return scheduler

    monkeypatch.setattr(baseline_unet, "CosineAnnealingLR", create_scheduler)
    checkpoint = train_baseline(epochs=1, batch_size=2, checkpoint_dir=str(tmp_path), splits_dir=str(split_dir))
    history = json.loads((tmp_path / "vinmec_unet_best_history.json").read_text())
    assert history[0]["amp_skipped_steps"] == 1
    assert schedulers[0].last_epoch == 0
    saved_weights = torch.load(checkpoint, map_location="cpu", weights_only=True)
    assert all(torch.equal(saved_weights[name], value) for name, value in initial_weights.items())
