"""
Enhanced U-Net++ Trainer for Ovarian Ultrasound Lesion Segmentation.
Supports:
- scSE (Spatial and Channel Squeeze & Excitation) attention decoder blocks
- AdvancedHybridLoss (Focal-Tversky + SoftDice + BCE)
- Domain-adapted pretraining initialization (from MMOTU Stage 1 ultrasound weights)
- Differential learning rate schedule (Encoder LR vs Decoder LR)
- Optimized for 4GB VRAM GPU with AMP FP16 and Gradient Accumulation
- Horizontal-flip Test-Time Augmentation (TTA) and threshold calibration
- Exact split integrity verification and SHA-256 hashing
"""

import argparse
import hashlib
import json
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import segmentation_models_pytorch as smp
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from ai_training.dataset_loader import OvarianUltrasoundDataset
from ai_training.loss import AdvancedHybridLoss
from ai_training.train_baseline_unet import validate_training_split_integrity

GRAY_MEAN = 0.449
GRAY_STD = 0.226


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_grayscale(images: torch.Tensor) -> torch.Tensor:
    return (images - GRAY_MEAN) / GRAY_STD


def build_boosted_model(
    encoder_name: str = "resnet34",
    attention_type: str | None = "scse",
    pretrained_weights: str | None = "imagenet",
) -> nn.Module:
    """Builds U-Net++ with optional scSE attention and specified encoder."""
    return smp.UnetPlusPlus(
        encoder_name=encoder_name,
        encoder_weights=pretrained_weights,
        in_channels=1,
        classes=1,
        decoder_attention_type=attention_type,
        activation=None,
    )


def compute_metrics(
    logits: torch.Tensor,
    targets: torch.Tensor,
    threshold: float = 0.5,
) -> dict[str, torch.Tensor]:
    predictions = torch.sigmoid(logits) >= threshold
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
        "precision": torch.where(tp + fp == 0, (tp + fn == 0).float(), tp / (tp + fp).clamp_min(1)),
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


def evaluate_loader(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    tta_horizontal_flip: bool = False,
    threshold: float = 0.4,
) -> dict[str, float]:
    model.eval()
    total_loss = 0.0
    metrics = {k: [] for k in ("dice", "iou", "recall", "precision", "specificity")}
    with torch.no_grad():
        for batch in loader:
            images = normalize_grayscale(batch["image"].to(device, non_blocking=True))
            masks = batch["mask"].to(device, non_blocking=True)

            with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
                logits = model(images)
                if tta_horizontal_flip:
                    flipped_logits = model(torch.flip(images, dims=(3,)))
                    logits = (logits + torch.flip(flipped_logits, dims=(3,))) * 0.5
                loss = criterion(logits, masks)

            batch_size = images.shape[0]
            total_loss += loss.detach().item() * batch_size

            batch_res = compute_metrics(logits, masks, threshold=threshold)
            for k, v in batch_res.items():
                metrics[k].extend(v.float().cpu().tolist())

    return {
        "loss": total_loss / len(loader.dataset),
        **{k: statistics.mean(v) for k, v in metrics.items()},
    }


def run_training(
    split_dir: Path,
    output_dir: Path,
    encoder_name: str = "resnet34",
    attention_type: str | None = "scse",
    init_checkpoint: Path | None = None,
    epochs: int = 25,
    batch_size: int = 2,
    gradient_accumulation_steps: int = 2,
    encoder_lr: float = 2e-5,
    decoder_lr: float = 1e-4,
    patience: int = 7,
    seed: int = 42,
) -> dict:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        torch.cuda.empty_cache()

    split_dir = split_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    split_integrity = validate_training_split_integrity(split_dir)
    manifest = json.loads((split_dir / "manifest.json").read_text(encoding="utf-8"))
    split_provenance = {
        "split_dir": str(split_dir),
        "manifest_sha256": sha256_file(split_dir / "manifest.json"),
        "train_csv_sha256": sha256_file(split_dir / "train.csv"),
        "validation_csv_sha256": sha256_file(split_dir / "val.csv"),
        "test_csv_sha256": sha256_file(split_dir / "test.csv"),
    }
    train_dataset = OvarianUltrasoundDataset(
        str(split_dir / "train.csv"),
        is_train=True,
        seed=seed,
        rotation_limit=15,
        elastic_probability=0.0,  # Fast vectorized affine transforms
    )
    val_dataset = OvarianUltrasoundDataset(str(split_dir / "val.csv"), is_train=False)
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
    pretrained_weights = "imagenet" if init_checkpoint is None else None
    model = build_boosted_model(
        encoder_name=encoder_name,
        attention_type=attention_type,
        pretrained_weights=pretrained_weights,
    ).to(device)

    if init_checkpoint is not None and init_checkpoint.is_file():
        print(f"Loading pre-trained checkpoint: {init_checkpoint}", flush=True)
        state_dict = torch.load(init_checkpoint, map_location=device, weights_only=True)
        model_dict = model.state_dict()
        filtered_dict = {k: v for k, v in state_dict.items() if k in model_dict and v.shape == model_dict[k].shape}
        print(f"Loaded {len(filtered_dict)}/{len(model_dict)} tensor layers from pre-trained checkpoint.", flush=True)
        model_dict.update(filtered_dict)
        model.load_state_dict(model_dict)

    criterion = AdvancedHybridLoss(tversky_weight=0.5, dice_weight=0.3, bce_weight=0.2).to(device)

    # Differential Learning Rates
    optimizer = torch.optim.AdamW(
        [
            {"params": model.encoder.parameters(), "lr": encoder_lr},
            {"params": model.decoder.parameters(), "lr": decoder_lr},
            {"params": model.segmentation_head.parameters(), "lr": decoder_lr},
        ],
        weight_decay=1e-4,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    scaler = torch.amp.GradScaler(device.type, enabled=device.type == "cuda")

    best_checkpoint_path = output_dir / f"boosted_{encoder_name}_{attention_type or 'noatt'}_best.pth"
    last_checkpoint_path = output_dir / f"boosted_{encoder_name}_{attention_type or 'noatt'}_last.pth"

    best_dice = -1.0
    best_epoch = 0
    no_improvement = 0
    history = []
    started_time = time.perf_counter()

    print(
        f"Starting training on {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})"
        f" for {epochs} epochs | batch_size={batch_size} (accum={gradient_accumulation_steps}) "
        f"| encoder_lr={encoder_lr}, decoder_lr={decoder_lr}",
        flush=True,
    )

    for epoch in range(1, epochs + 1):
        epoch_start = time.perf_counter()
        model.train()
        train_loss = 0.0
        train_dices = []
        optimizer.zero_grad(set_to_none=True)

        for step, batch in enumerate(train_loader):
            images = normalize_grayscale(batch["image"].to(device, non_blocking=True))
            masks = batch["mask"].to(device, non_blocking=True)

            with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
                logits = model(images)
                loss = criterion(logits, masks)
                loss_scaled = loss / gradient_accumulation_steps

            scaler.scale(loss_scaled).backward()

            if (step + 1) % gradient_accumulation_steps == 0 or (step + 1) == len(train_loader):
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)

            train_loss += loss.detach().item() * images.shape[0]
            with torch.no_grad():
                res = compute_metrics(logits.detach(), masks, threshold=0.5)
                train_dices.extend(res["dice"].float().cpu().tolist())

        scheduler.step()
        train_stats = {
            "loss": train_loss / len(train_dataset),
            "dice": statistics.mean(train_dices),
        }

        # Fast Validation with AMP FP16
        val_stats = evaluate_loader(
            model=model,
            loader=val_loader,
            criterion=criterion,
            device=device,
            tta_horizontal_flip=False,
            threshold=0.4,
        )

        improved = val_stats["dice"] > best_dice + 1e-4
        if improved:
            best_dice = val_stats["dice"]
            best_epoch = epoch
            no_improvement = 0
            torch.save(model.state_dict(), best_checkpoint_path)
        else:
            no_improvement += 1

        torch.save(model.state_dict(), last_checkpoint_path)
        epoch_duration = round(time.perf_counter() - epoch_start, 2)

        record = {
            "epoch": epoch,
            "train": train_stats,
            "validation": val_stats,
            "best_validation_dice": best_dice,
            "is_best": improved,
            "epoch_seconds": epoch_duration,
        }
        history.append(record)
        (output_dir / "training_history.json").write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")

        print(
            f"Epoch {epoch:02d}/{epochs} | Train Loss: {train_stats['loss']:.4f}, Dice: {train_stats['dice']:.4f} | "
            f"Val Dice: {val_stats['dice']:.4f}, IoU: {val_stats['iou']:.4f}, Recall: {val_stats['recall']:.4f}, "
            f"Prec: {val_stats['precision']:.4f} | Best Dice: {best_dice:.4f} | Time: {epoch_duration}s",
            flush=True,
        )

        if no_improvement >= patience:
            print(f"Early stopping triggered after {patience} epochs without improvement.", flush=True)
            break

    # Final multi-threshold evaluation of the best model with Horizontal-Flip TTA
    print(f"\n--- Loading best model from epoch {best_epoch} for TTA threshold calibration ---", flush=True)
    model.load_state_dict(torch.load(best_checkpoint_path, map_location=device, weights_only=True))
    threshold_results = {}
    for th in [0.30, 0.35, 0.40, 0.45, 0.50]:
        th_stats = evaluate_loader(model, val_loader, criterion, device, tta_horizontal_flip=True, threshold=th)
        threshold_results[f"threshold_{th:.2f}"] = th_stats
        print(
            f"TTA Threshold {th:.2f} -> Dice: {th_stats['dice']:.4f}, IoU: {th_stats['iou']:.4f}, "
            f"Recall: {th_stats['recall']:.4f}, Precision: {th_stats['precision']:.4f}",
            flush=True,
        )

    run_summary = {
        "architecture": f"U-Net++ ({encoder_name}) with {attention_type or 'no'} attention",
        "encoder": encoder_name,
        "attention": attention_type,
        "init_checkpoint": str(init_checkpoint) if init_checkpoint else "imagenet",
        "split_integrity": split_integrity,
        "split_provenance": split_provenance,
        "loss": "AdvancedHybridLoss(0.5 FocalTversky + 0.3 SoftDice + 0.2 BCE)",
        "epochs_requested": epochs,
        "epochs_completed": len(history),
        "best_epoch": best_epoch,
        "best_checkpoint": str(best_checkpoint_path),
        "best_checkpoint_sha256": sha256_file(best_checkpoint_path),
        "best_validation": history[best_epoch - 1]["validation"] if best_epoch > 0 else None,
        "tta_threshold_calibration": threshold_results,
        "total_duration_seconds": round(time.perf_counter() - started_time, 2),
        "patient_level_independence_verified": False,
        "test_split_used_for_training_or_selection": False,
    }
    (output_dir / "run_summary.json").write_text(json.dumps(run_summary, indent=2) + "\n", encoding="utf-8")
    return run_summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--encoder", type=str, default="resnet34")
    parser.add_argument("--attention", type=str, default="scse")
    parser.add_argument("--init_checkpoint", type=str, default=None)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch_size", type=int, default=2)
    parser.add_argument("--grad_accum", type=int, default=2)
    parser.add_argument("--encoder_lr", type=float, default=2e-5)
    parser.add_argument("--decoder_lr", type=float, default=1e-4)
    parser.add_argument("--patience", type=int, default=6)
    parser.add_argument("--output_dir", type=str, default="checkpoints/boosted_unetplusplus_scse")
    args = parser.parse_args()

    split_dir = ROOT / "ai_training/splits/unified_vinmec_clean_2026-10-06"
    init_ckpt = Path(args.init_checkpoint) if args.init_checkpoint else None
    run_training(
        split_dir=split_dir,
        output_dir=ROOT / args.output_dir,
        encoder_name=args.encoder,
        attention_type=args.attention if args.attention != "none" else None,
        init_checkpoint=init_ckpt,
        epochs=args.epochs,
        batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        encoder_lr=args.encoder_lr,
        decoder_lr=args.decoder_lr,
        patience=args.patience,
    )
