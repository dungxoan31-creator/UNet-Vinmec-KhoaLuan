"""
Standard U-Net Baseline Training Pipeline with Combo Loss (BCE + Soft Dice).
Optimized for NVIDIA RTX GPU with CUDA Mixed Precision (AMP).
Patient-Level Stratified Validation and Best Model Checkpointing.
"""

import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai_training.dataset_loader import get_dataloaders
from backend.models.unet import StandardUNet


class SoftDiceLoss(nn.Module):
    def __init__(self, smooth=1.0):
        super().__init__()
        self.smooth = smooth

    def forward(self, logits, targets):
        probs = torch.sigmoid(logits)
        num = 2.0 * (probs * targets).sum() + self.smooth
        den = probs.sum() + targets.sum() + self.smooth
        return 1.0 - (num / den)


class ComboLoss(nn.Module):
    def __init__(self, bce_weight=0.5, dice_weight=0.5):
        super().__init__()
        self.bce = nn.BCEWithLogitsLoss()
        self.dice = SoftDiceLoss()
        self.bce_weight = bce_weight
        self.dice_weight = dice_weight

    def forward(self, logits, targets):
        return self.bce_weight * self.bce(logits, targets) + self.dice_weight * self.dice(logits, targets)


def compute_batch_dice(logits, targets, smooth=1e-5):
    return compute_batch_metrics(logits, targets)["dice"].item()


def compute_batch_metrics(logits, targets):
    """Mean per-image segmentation metrics with explicit empty-mask handling."""
    prediction = (torch.sigmoid(logits) > 0.5).flatten(1)
    truth = (targets > 0.5).flatten(1)
    tp = (prediction & truth).sum(dim=1).float()
    predicted = prediction.sum(dim=1).float()
    labeled = truth.sum(dim=1).float()
    union = predicted + labeled - tp
    return {
        "dice": torch.where(predicted + labeled == 0, 1.0, 2 * tp / (predicted + labeled).clamp_min(1)).mean(),
        "iou": torch.where(union == 0, 1.0, tp / union.clamp_min(1)).mean(),
        "recall": torch.where(labeled == 0, 1.0, tp / labeled.clamp_min(1)).mean(),
        "precision": torch.where(predicted == 0, (labeled == 0).float(), tp / predicted.clamp_min(1)).mean(),
    }


def train_baseline(
    epochs=12,
    batch_size=4,
    lr=1e-3,
    checkpoint_dir="checkpoints",
    splits_dir="ai_training/splits",
    seed=42,
    patience=8,
):
    print("=" * 70, flush=True)
    print("   BƯỚC 5: HUẤN LUYỆN MÔ HÌNH STANDARD U-NET BASELINE", flush=True)
    print("=" * 70, flush=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[THIẾT BỊ] Huấn luyện trên: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})", flush=True)

    os.makedirs(checkpoint_dir, exist_ok=True)
    best_checkpoint_path = os.path.join(checkpoint_dir, "baseline_unet_best.pth")
    last_checkpoint_path = os.path.join(checkpoint_dir, "baseline_unet_last.pth")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)

    # 1. Dataloaders
    train_loader, val_loader, test_loader = get_dataloaders(splits_dir=splits_dir, batch_size=batch_size, num_workers=0, seed=seed)
    print(f"[DỮ LIỆU] Số batch Train: {len(train_loader)} | Số batch Val: {len(val_loader)} (Batch size: {batch_size})", flush=True)

    # 2. Model & Loss & Optimizer
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    criterion = ComboLoss(bce_weight=0.5, dice_weight=0.5)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    scaler = torch.amp.GradScaler('cuda', enabled=(device.type == 'cuda'))

    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[MÔ HÌNH] Standard U-Net (Base filters: 32) | Tổng tham số: {total_params:,} (~7.76M)", flush=True)

    best_val_dice = float("-inf")
    history = []
    epochs_without_improvement = 0

    start_time = time.time()
    for epoch in range(1, epochs + 1):
        # TRAIN
        model.train()
        train_loss = 0.0
        train_dice = 0.0
        train_count = 0
        amp_skipped_steps = 0
        for batch in train_loader:
            images = batch["image"].to(device, non_blocking=True)
            masks = batch["mask"].to(device, non_blocking=True)

            optimizer.zero_grad()
            with torch.amp.autocast('cuda', enabled=(device.type == 'cuda')):
                logits = model(images)
                loss = criterion(logits, masks)

            scaler.scale(loss).backward()
            previous_scale = scaler.get_scale()
            scaler.step(optimizer)
            scaler.update()
            if scaler.get_scale() < previous_scale:
                amp_skipped_steps += 1

            sample_count = images.shape[0]
            train_loss += loss.item() * sample_count
            train_dice += compute_batch_dice(logits, masks) * sample_count
            train_count += sample_count

        train_loss /= train_count
        train_dice /= train_count

        # VALIDATION
        model.eval()
        val_loss = 0.0
        val_dice = 0.0
        val_iou = 0.0
        val_recall = 0.0
        val_count = 0
        with torch.no_grad():
            for batch in val_loader:
                images = batch["image"].to(device, non_blocking=True)
                masks = batch["mask"].to(device, non_blocking=True)

                with torch.amp.autocast('cuda', enabled=(device.type == 'cuda')):
                    logits = model(images)
                    loss = criterion(logits, masks)

                sample_count = images.shape[0]
                batch_metrics = compute_batch_metrics(logits, masks)
                val_loss += loss.item() * sample_count
                val_dice += batch_metrics["dice"].item() * sample_count
                val_iou += batch_metrics["iou"].item() * sample_count
                val_recall += batch_metrics["recall"].item() * sample_count
                val_count += sample_count

        val_loss /= val_count
        val_dice /= val_count
        val_iou /= val_count
        val_recall /= val_count
        scheduler.step()

        # Lưu checkpoint tốt nhất
        is_best = val_dice > best_val_dice
        if is_best:
            best_val_dice = val_dice
            epochs_without_improvement = 0
            torch.save(model.state_dict(), best_checkpoint_path)
        else:
            epochs_without_improvement += 1

        epoch_stat = {
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "train_dice": round(train_dice, 4),
            "val_loss": round(val_loss, 4),
            "val_dice": round(val_dice, 4),
            "val_iou": round(val_iou, 4),
            "val_recall": round(val_recall, 4),
            "lr": round(optimizer.param_groups[0]["lr"], 6),
            "is_best": is_best,
            "elapsed_seconds": round(time.time() - start_time, 3),
            "amp_skipped_steps": amp_skipped_steps,
        }
        history.append(epoch_stat)
        torch.save(model.state_dict(), last_checkpoint_path)

        star = " ★ [BEST SAVED]" if is_best else ""
        print(f"Epoch [{epoch:02d}/{epochs:02d}] - Train Loss: {train_loss:.4f} | Train Dice: {train_dice:.4f} || Val Loss: {val_loss:.4f} | Val Dice: {val_dice:.4f}{star}", flush=True)
        if epochs_without_improvement >= patience:
            break

    total_duration = time.time() - start_time
    print("-" * 70, flush=True)
    print(f"[HOÀN TẤT] Thời gian huấn luyện: {total_duration:.2f}s", flush=True)
    print(f"[KẾT QUẢ] Best Validation Dice: {best_val_dice:.4f}", flush=True)
    print(f"[CHECKPOINT] Trọng số tối ưu lưu tại: {best_checkpoint_path}", flush=True)

    # Lưu log
    for filename in ("baseline_training_history.json", "vinmec_unet_best_history.json"):
        with open(os.path.join(checkpoint_dir, filename), "w", encoding="utf-8") as stream:
            json.dump(history, stream, indent=2)
    with (Path(checkpoint_dir) / "run_config.json").open("w", encoding="utf-8") as stream:
        json.dump({
            "seed": seed,
            "batch_size": batch_size,
            "epochs": epochs,
            "patience": patience,
            "learning_rate": lr,
            "loss": "0.5 BCE + 0.5 Dice",
            "optimizer": "AdamW(weight_decay=1e-4)",
            "scheduler": "CosineAnnealingLR(eta_min=1e-6)",
            "architecture": "StandardUNet(base_filters=32)",
            "augmentation": "HorizontalFlip, RandomBrightnessContrast, ShiftScaleRotate; train only",
            "validation_metric": "mean per-image Dice at 512x512, threshold 0.5",
            "device": str(device),
            "gpu_name": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
            "train_samples": len(train_loader.dataset),
            "validation_samples": len(val_loader.dataset),
            "test_samples_held_out": len(test_loader.dataset),
            "best_epoch": next((row["epoch"] for row in reversed(history) if row["is_best"]), None),
            "best_validation_dice": best_val_dice,
            "duration_seconds": round(total_duration, 3),
            "split_sha256": {
                split: hashlib.sha256((Path(splits_dir) / f"{split}.csv").read_bytes()).hexdigest()
                for split in ("train", "val", "test")
            },
            "checkpoint_best": best_checkpoint_path,
            "checkpoint_last": last_checkpoint_path,
        }, stream, indent=2)

    return best_checkpoint_path


if __name__ == "__main__":
    train_baseline(epochs=12, batch_size=4, lr=1e-3)
