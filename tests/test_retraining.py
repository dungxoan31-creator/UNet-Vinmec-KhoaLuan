import json

import pytest
import torch
from torch.utils.data import DataLoader

from ai_training.dataset_loader import get_dataloaders
from ai_training.train_baseline_unet import compute_batch_dice, compute_batch_metrics, train_baseline
from scripts.prepare_vinmec import prepare_splits
from tests.test_vinmec_pipeline import _pair


def test_dice_weights_each_case_equally():
    logits = torch.tensor([[[[10.0, 10.0]]], [[[-10.0, -10.0]]]])
    masks = torch.ones_like(logits)
    assert abs(compute_batch_dice(logits, masks) - 0.5) < 1e-4


def test_empty_ground_truth_recall_matches_evaluator_convention():
    metrics = compute_batch_metrics(torch.full((1, 1, 2, 2), 10.0), torch.zeros(1, 1, 2, 2))
    assert metrics["dice"].item() == 0.0
    assert metrics["iou"].item() == 0.0
    assert metrics["recall"].item() == 1.0


def test_training_augmentation_is_reproducible(tmp_path):
    for stem in range(6):
        _pair(tmp_path, "train", str(stem))
    _pair(tmp_path, "test", "9")
    splits = tmp_path / "splits"
    prepare_splits(tmp_path, splits, val_fraction=0.3)
    first, _, _ = get_dataloaders(splits, batch_size=2, seed=17)
    second, _, _ = get_dataloaders(splits, batch_size=2, seed=17)
    for first_batch, second_batch in zip(first, second):
        assert first_batch["case_id"] == second_batch["case_id"]
        assert torch.equal(first_batch["image"], second_batch["image"])
        assert torch.equal(first_batch["mask"], second_batch["mask"])


def test_training_persists_metrics_and_configuration_each_epoch(tmp_path, monkeypatch):
    samples = [
        {"image": torch.ones(1, 8, 8), "mask": torch.ones(1, 8, 8)},
        {"image": torch.zeros(1, 8, 8), "mask": torch.zeros(1, 8, 8)},
        {"image": torch.ones(1, 8, 8), "mask": torch.ones(1, 8, 8)},
    ]
    loader = DataLoader(samples, batch_size=2)
    monkeypatch.setattr("ai_training.train_baseline_unet.get_dataloaders", lambda **kwargs: (loader, loader, loader))
    def tiny_model(**kwargs):
        model = torch.nn.Conv2d(1, 1, 1)
        with torch.no_grad():
            model.weight.fill_(1.0)
            model.bias.fill_(0.5)
        return model

    monkeypatch.setattr("ai_training.train_baseline_unet.StandardUNet", tiny_model)
    checkpoint = train_baseline(epochs=2, batch_size=2, checkpoint_dir=str(tmp_path), seed=17, patience=8)
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
    samples = [{"image": torch.ones(1, 8, 8), "mask": torch.zeros(1, 8, 8)}] * 2
    loader = DataLoader(samples, batch_size=2)
    monkeypatch.setattr("ai_training.train_baseline_unet.get_dataloaders", lambda **kwargs: (loader, loader, loader))
    initial_weights = {}

    def tiny_model(**kwargs):
        model = torch.nn.Conv2d(1, 1, 1)
        initial_weights.update({name: value.clone() for name, value in model.state_dict().items()})
        return model

    monkeypatch.setattr("ai_training.train_baseline_unet.StandardUNet", tiny_model)
    scaler_type = torch.amp.GradScaler
    monkeypatch.setattr("ai_training.train_baseline_unet.torch.amp.GradScaler", lambda device, enabled: scaler_type(device, enabled=enabled, init_scale=2.0**30))
    checkpoint = train_baseline(epochs=1, batch_size=2, checkpoint_dir=str(tmp_path))
    history = json.loads((tmp_path / "vinmec_unet_best_history.json").read_text())
    assert history[0]["amp_skipped_steps"] == 1
    saved_weights = torch.load(checkpoint, map_location="cpu", weights_only=True)
    assert all(torch.equal(saved_weights[name], value) for name, value in initial_weights.items())
