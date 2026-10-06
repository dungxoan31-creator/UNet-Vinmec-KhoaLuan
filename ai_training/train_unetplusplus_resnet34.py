"""Train a Validation-selected U-Net++ candidate with an ImageNet ResNet34 encoder."""

import argparse
import hashlib
import importlib.metadata
import json
import random
import statistics
import time
from pathlib import Path

import numpy as np
import segmentation_models_pytorch as smp
import torch
from torch.utils.data import DataLoader

from ai_training.dataset_loader import OvarianUltrasoundDataset
from ai_training.train_baseline_unet import ComboLoss

GRAY_MEAN = 0.449
GRAY_STD = 0.226
BASELINE_VALIDATION_DICE = 0.6724380325257447


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_model(pretrained: bool = True) -> torch.nn.Module:
    return smp.UnetPlusPlus(
        encoder_name="resnet34",
        encoder_weights="imagenet" if pretrained else None,
        in_channels=1,
        classes=1,
        activation=None,
    )


def normalize_grayscale(images: torch.Tensor) -> torch.Tensor:
    return (images - GRAY_MEAN) / GRAY_STD


def batch_metrics(logits: torch.Tensor, targets: torch.Tensor) -> dict[str, torch.Tensor]:
    predictions = torch.sigmoid(logits) >= 0.5
    truth = targets >= 0.5
    predictions = predictions.flatten(1)
    truth = truth.flatten(1)
    tp = (predictions & truth).sum(1).float()
    fp = (predictions & ~truth).sum(1).float()
    fn = (~predictions & truth).sum(1).float()
    tn = (~predictions & ~truth).sum(1).float()
    dice_denominator = 2 * tp + fp + fn
    union = tp + fp + fn
    return {
        "dice": torch.where(dice_denominator == 0, 1.0, 2 * tp / dice_denominator.clamp_min(1)),
        "iou": torch.where(union == 0, 1.0, tp / union.clamp_min(1)),
        "recall": torch.where(tp + fn == 0, 1.0, tp / (tp + fn).clamp_min(1)),
        "precision": torch.where(tp + fp == 0, 1.0, tp / (tp + fp).clamp_min(1)),
        "specificity": torch.where(tn + fp == 0, 1.0, tn / (tn + fp).clamp_min(1)),
    }


def validate_splits(train_dataset, val_dataset, manifest: dict) -> None:
    counts = manifest["split_counts"]
    if len(train_dataset) != counts["train"] or len(val_dataset) != counts["val"]:
        raise ValueError("Train/Validation sample counts do not match the frozen split manifest")

    train_hashes = set(train_dataset.df["image_sha256"].astype(str))
    val_hashes = set(val_dataset.df["image_sha256"].astype(str))
    if len(train_hashes) != len(train_dataset) or len(val_hashes) != len(val_dataset):
        raise ValueError("Duplicate image SHA-256 found in Train or Validation")
    overlap = train_hashes & val_hashes
    if overlap:
        raise ValueError(f"Train/Validation image SHA-256 overlap: {len(overlap)}")


def run_epoch(model, loader, criterion, device, optimizer=None, scaler=None) -> dict[str, float]:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    metrics = {key: [] for key in ("dice", "iou", "recall", "precision", "specificity")}
    amp_enabled = device.type == "cuda"

    context = torch.enable_grad if training else torch.no_grad
    with context():
        for batch in loader:
            images = normalize_grayscale(batch["image"].to(device, non_blocking=True))
            masks = batch["mask"].to(device, non_blocking=True)
            if training:
                optimizer.zero_grad(set_to_none=True)

            with torch.amp.autocast(device_type=device.type, enabled=amp_enabled):
                logits = model(images)
                loss = criterion(logits, masks)

            if training:
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()

            count = images.shape[0]
            total_loss += loss.detach().item() * count
            for name, value in batch_metrics(logits.detach(), masks).items():
                metrics[name].extend(value.float().cpu().tolist())

    return {"loss": total_loss / len(loader.dataset), **{key: statistics.mean(values) for key, values in metrics.items()}}


def train(
    split_dir: Path,
    output_dir: Path,
    epochs: int = 30,
    batch_size: int = 1,
    learning_rate: float = 1e-4,
    patience: int = 6,
    seed: int = 42,
) -> dict:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    manifest_path = split_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    train_csv = split_dir / "train.csv"
    val_csv = split_dir / "val.csv"
    train_dataset = OvarianUltrasoundDataset(str(train_csv), is_train=True, seed=seed)
    val_dataset = OvarianUltrasoundDataset(str(val_csv), is_train=False)
    validate_splits(train_dataset, val_dataset, manifest)

    generator = torch.Generator().manual_seed(seed)
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
        generator=generator,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(pretrained=True).to(device)
    criterion = ComboLoss(bce_weight=0.5, dice_weight=0.5)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    scaler = torch.amp.GradScaler(device.type, enabled=device.type == "cuda")

    output_dir.mkdir(parents=True, exist_ok=True)
    best_path = output_dir / "unetplusplus_resnet34_best.pth"
    last_path = output_dir / "unetplusplus_resnet34_last.pth"
    history = []
    best_dice = -1.0
    best_epoch = 0
    no_improvement = 0
    started = time.perf_counter()

    for epoch in range(1, epochs + 1):
        train_stats = run_epoch(model, train_loader, criterion, device, optimizer, scaler)
        val_stats = run_epoch(model, val_loader, criterion, device)
        scheduler.step()
        improved = val_stats["dice"] > best_dice
        if improved:
            best_dice = val_stats["dice"]
            best_epoch = epoch
            no_improvement = 0
            torch.save(model.state_dict(), best_path)
        else:
            no_improvement += 1
        torch.save(model.state_dict(), last_path)
        record = {
            "epoch": epoch,
            "train": train_stats,
            "validation": val_stats,
            "learning_rate": optimizer.param_groups[0]["lr"],
            "is_best": improved,
        }
        history.append(record)
        (output_dir / "training_history.json").write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
        print(
            f"epoch={epoch:02d}/{epochs} train_dice={train_stats['dice']:.4f} "
            f"val_dice={val_stats['dice']:.4f} val_iou={val_stats['iou']:.4f} "
            f"val_recall={val_stats['recall']:.4f} best={best_dice:.4f}",
            flush=True,
        )
        if no_improvement >= patience:
            break

    duration = time.perf_counter() - started
    result = {
        "architecture": "U-Net++ (Segmentation Models PyTorch) + ResNet34 ImageNet encoder",
        "segmentation_models_pytorch_version": importlib.metadata.version("segmentation-models-pytorch"),
        "encoder": {"name": "resnet34", "weights": "imagenet"},
        "seed": seed,
        "device": str(device),
        "gpu_name": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
        "batch_size": batch_size,
        "epochs_requested": epochs,
        "epochs_completed": len(history),
        "patience": patience,
        "learning_rate": learning_rate,
        "optimizer": "AdamW(weight_decay=1e-4)",
        "scheduler": "CosineAnnealingLR(eta_min=1e-6)",
        "loss": "0.5 BCEWithLogits + 0.5 SoftDice",
        "input": "Grayscale CLAHE Letterbox 512x512, scaled to [0,1], then grayscale ImageNet normalization",
        "augmentation": "Existing synchronized image-mask train transforms from OvarianUltrasoundDataset",
        "gray_normalization": {"mean": GRAY_MEAN, "std": GRAY_STD},
        "threshold": 0.5,
        "selection_metric": "mean per-image Validation Dice",
        "split_dir": str(split_dir),
        "train_count": len(train_dataset),
        "validation_count": len(val_dataset),
        "test_split_accessed": False,
        "train_csv_sha256": sha256_file(train_csv),
        "validation_csv_sha256": sha256_file(val_csv),
        "manifest_sha256": sha256_file(manifest_path),
        "baseline_standard_unet_validation_dice": BASELINE_VALIDATION_DICE,
        "best_epoch": best_epoch,
        "train_metrics_at_best_epoch": history[best_epoch - 1]["train"],
        "best_validation": history[best_epoch - 1]["validation"],
        "duration_seconds": round(duration, 2),
        "best_checkpoint": str(best_path),
        "best_checkpoint_sha256": sha256_file(best_path),
        "last_checkpoint": str(last_path),
        "last_checkpoint_sha256": sha256_file(last_path),
    }
    (output_dir / "run_config.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split-dir", type=Path, default=Path("ai_training/splits/unified_vinmec_clean_2026-10-06"))
    parser.add_argument("--output-dir", type=Path, default=Path("checkpoints/unetplusplus_resnet34_2026-10-06"))
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    train(
        split_dir=args.split_dir,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        patience=args.patience,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
