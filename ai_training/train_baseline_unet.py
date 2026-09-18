"""
Standard U-Net Baseline Training Pipeline with Combo Loss (BCE + Soft Dice).
Optimized for NVIDIA RTX GPU with CUDA Mixed Precision (AMP).
Patient-Level Stratified Validation and Best Model Checkpointing.
"""

import os
import sys
import json
import time
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models.unet import StandardUNet
from ai_training.dataset_loader import get_dataloaders


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
    probs = torch.sigmoid(logits)
    preds = (probs > 0.5).float()
    intersection = (preds * targets).sum().item()
    total = preds.sum().item() + targets.sum().item()
    if total == 0:
        return 1.0
    return (2.0 * intersection) / (total + smooth)


def train_baseline(
    epochs=12,
    batch_size=4,
    lr=1e-3,
    checkpoint_dir="checkpoints",
    splits_dir="ai_training/splits"
):
    print("=" * 70, flush=True)
    print("   BƯỚC 5: HUẤN LUYỆN MÔ HÌNH STANDARD U-NET BASELINE", flush=True)
    print("=" * 70, flush=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[THIẾT BỊ] Huấn luyện trên: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})", flush=True)

    os.makedirs(checkpoint_dir, exist_ok=True)
    best_checkpoint_path = os.path.join(checkpoint_dir, "baseline_unet_best.pth")

    # 1. Dataloaders
    train_loader, val_loader, _ = get_dataloaders(splits_dir=splits_dir, batch_size=batch_size, num_workers=0)
    print(f"[DỮ LIỆU] Số batch Train: {len(train_loader)} | Số batch Val: {len(val_loader)} (Batch size: {batch_size})", flush=True)

    # 2. Model & Loss & Optimizer
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    criterion = ComboLoss(bce_weight=0.5, dice_weight=0.5)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    scaler = torch.amp.GradScaler('cuda', enabled=(device.type == 'cuda'))

    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[MÔ HÌNH] Standard U-Net (Base filters: 32) | Tổng tham số: {total_params:,} (~7.76M)", flush=True)

    best_val_dice = 0.0
    history = []

    start_time = time.time()
    for epoch in range(1, epochs + 1):
        # TRAIN
        model.train()
        train_loss = 0.0
        train_dice = 0.0
        for batch in train_loader:
            images = batch["image"].to(device, non_blocking=True)
            masks = batch["mask"].to(device, non_blocking=True)

            optimizer.zero_grad()
            with torch.amp.autocast('cuda', enabled=(device.type == 'cuda')):
                logits = model(images)
                loss = criterion(logits, masks)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            train_loss += loss.item()
            train_dice += compute_batch_dice(logits, masks)

        train_loss /= len(train_loader)
        train_dice /= len(train_loader)

        # VALIDATION
        model.eval()
        val_loss = 0.0
        val_dice = 0.0
        with torch.no_grad():
            for batch in val_loader:
                images = batch["image"].to(device, non_blocking=True)
                masks = batch["mask"].to(device, non_blocking=True)

                with torch.amp.autocast('cuda', enabled=(device.type == 'cuda')):
                    logits = model(images)
                    loss = criterion(logits, masks)

                val_loss += loss.item()
                val_dice += compute_batch_dice(logits, masks)

        val_loss /= len(val_loader)
        val_dice /= len(val_loader)
        scheduler.step()

        # Lưu checkpoint tốt nhất
        is_best = val_dice > best_val_dice
        if is_best:
            best_val_dice = val_dice
            torch.save(model.state_dict(), best_checkpoint_path)

        epoch_stat = {
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "train_dice": round(train_dice, 4),
            "val_loss": round(val_loss, 4),
            "val_dice": round(val_dice, 4),
            "lr": round(optimizer.param_groups[0]["lr"], 6),
            "is_best": is_best
        }
        history.append(epoch_stat)

        star = " ★ [BEST SAVED]" if is_best else ""
        print(f"Epoch [{epoch:02d}/{epochs:02d}] - Train Loss: {train_loss:.4f} | Train Dice: {train_dice:.4f} || Val Loss: {val_loss:.4f} | Val Dice: {val_dice:.4f}{star}", flush=True)

    total_duration = time.time() - start_time
    print("-" * 70, flush=True)
    print(f"[HOÀN TẤT] Thời gian huấn luyện: {total_duration:.2f}s", flush=True)
    print(f"[KẾT QUẢ] Best Validation Dice: {best_val_dice:.4f}", flush=True)
    print(f"[CHECKPOINT] Trọng số tối ưu lưu tại: {best_checkpoint_path}", flush=True)

    # Lưu log
    log_path = os.path.join(checkpoint_dir, "baseline_training_history.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

    return best_checkpoint_path


if __name__ == "__main__":
    train_baseline(epochs=12, batch_size=4, lr=1e-3)
