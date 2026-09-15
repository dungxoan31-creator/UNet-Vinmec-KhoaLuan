"""
Production Training Pipeline for Standard U-Net Baseline on Protocol 1 MMOTU Dataset.
Engineered for NVIDIA GeForce RTX 3050 (4GB VRAM) with Automatic Mixed Precision (AMP fp16).
Author: Nguyen Huu Dung (MIS 65A - NEU)
"""

import os
import sys
import time
import json
import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models.unet import StandardUNet
from ai_training.dataset_loader import get_dataloaders
from ai_training.metrics_clinical import compute_sample_clinical_metrics, compute_dataset_clinical_summary


class DiceLoss(nn.Module):
    def __init__(self, smooth=1e-6):
        super().__init__()
        self.smooth = smooth

    def forward(self, logits, targets):
        probs = torch.sigmoid(logits)
        probs_flat = probs.view(-1)
        targets_flat = targets.view(-1)

        intersection = (probs_flat * targets_flat).sum()
        dice = (2.0 * intersection + self.smooth) / (probs_flat.sum() + targets_flat.sum() + self.smooth)
        return 1.0 - dice


class FocalLoss(nn.Module):
    def __init__(self, alpha=0.25, gamma=2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, logits, targets):
        bce = nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction="none")
        probs = torch.sigmoid(logits)
        p_t = probs * targets + (1 - probs) * (1 - targets)
        loss = self.alpha * ((1 - p_t) ** self.gamma) * bce
        return loss.mean()


class HybridSegmentationLoss(nn.Module):
    def __init__(self):
        super().__init__()
        self.bce = nn.BCEWithLogitsLoss()
        self.dice = DiceLoss()
        self.focal = FocalLoss()

    def forward(self, logits, targets):
        return 0.4 * self.bce(logits, targets) + 0.4 * self.dice(logits, targets) + 0.2 * self.focal(logits, targets)


def train_baseline(epochs=10, batch_size=4, lr=1e-4, smoke_test=False):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 70)
    print("       STANDARD U-NET BASELINE TRAINING (PROTOCOL 1)       ")
    print(f"[DEVICE] Using Device: {device} | Mixed Precision: {device.type == 'cuda'}")
    if device.type == "cuda":
        print(f"[DEVICE] GPU Name: {torch.cuda.get_device_name(0)}")
    print("=" * 70)

    # 1. Load Data (Protocol 1: 700 Train / 120 Val / 382 Held-out Test)
    train_loader, val_loader, test_loader = get_dataloaders(protocol="standard", batch_size=batch_size, num_workers=0)
    print(f"[DATA] Train Batches: {len(train_loader)} | Val Batches: {len(val_loader)}")

    # 2. Initialize Standard U-Net
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    criterion = HybridSegmentationLoss()
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    use_amp = (device.type == "cuda")
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    os.makedirs("checkpoints", exist_ok=True)
    os.makedirs("ai_training/production_model", exist_ok=True)
    best_weights_path = "checkpoints/baseline_unet_best.pth"

    best_val_dice = 0.0
    history = []

    actual_epochs = 1 if smoke_test else epochs
    max_train_batches = 10 if smoke_test else len(train_loader)
    max_val_batches = 5 if smoke_test else len(val_loader)

    print(f"\n[START] Starting training for {actual_epochs} epochs (Smoke-test: {smoke_test})...\n")

    for epoch in range(1, actual_epochs + 1):
        start_time = time.time()
        model.train()
        train_loss = 0.0
        batches_processed = 0

        for b_idx, batch in enumerate(train_loader):
            if smoke_test and b_idx >= max_train_batches:
                break

            images = batch["image"].to(device)
            masks = batch["mask"].to(device)

            optimizer.zero_grad()
            with torch.amp.autocast(device_type="cuda" if use_amp else "cpu", enabled=use_amp, dtype=torch.float16):
                outputs = model(images)
                loss = criterion(outputs, masks)

            if use_amp:
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                loss.backward()
                optimizer.step()

            train_loss += loss.item()
            batches_processed += 1

        scheduler.step()
        train_loss /= max(1, batches_processed)

        # Validation Phase
        model.eval()
        val_loss = 0.0
        val_batches = 0
        sample_evals = []

        with torch.no_grad():
            for b_idx, batch in enumerate(val_loader):
                if smoke_test and b_idx >= max_val_batches:
                    break

                images = batch["image"].to(device)
                masks = batch["mask"].to(device)

                with torch.amp.autocast(device_type="cuda" if use_amp else "cpu", enabled=use_amp, dtype=torch.float16):
                    outputs = model(images)
                    loss = criterion(outputs, masks)

                val_loss += loss.item()
                val_batches += 1

                # Calculate sample-level clinical metrics
                probs = torch.sigmoid(outputs)
                preds = (probs > 0.5).cpu().numpy()
                gts = masks.cpu().numpy()

                for p, g in zip(preds, gts):
                    m = compute_sample_clinical_metrics(p[0], g[0])
                    sample_evals.append(m)

        val_loss /= max(1, val_batches)
        val_summary = compute_dataset_clinical_summary(sample_evals)
        val_fg_dice = val_summary["foreground_dice_mean"]
        val_fg_iou = val_summary["foreground_iou_mean"]
        val_recall = val_summary["recall_sensitivity_mean"]
        val_spec = val_summary["specificity_all_cases"]

        duration = time.time() - start_time
        print(f"Epoch [{epoch:02d}/{actual_epochs:02d}] ({duration:.1f}s) | "
              f"Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | "
              f"Val FG Dice: {val_fg_dice:.4f} | Val FG IoU: {val_fg_iou:.4f} | "
              f"Recall: {val_recall:.4f} | Spec: {val_spec:.4f}")

        epoch_record = {
            "epoch": epoch,
            "duration_sec": round(duration, 2),
            "train_loss": round(train_loss, 4),
            "val_loss": round(val_loss, 4),
            "val_foreground_dice": round(val_fg_dice, 4),
            "val_foreground_iou": round(val_fg_iou, 4),
            "val_recall": round(val_recall, 4),
            "val_specificity": round(val_spec, 4),
            "lesion_cases": val_summary["lesion_cases_count"],
            "normal_cases": val_summary["normal_cases_count"]
        }
        history.append(epoch_record)

        if val_fg_dice > best_val_dice:
            best_val_dice = val_fg_dice
            torch.save(model.state_dict(), best_weights_path)
            print(f"  --> Best Model Saved! Checkpoint: {best_weights_path} (FG Dice: {best_val_dice:.4f})")

    log_path = "ai_training/production_model/baseline_training_log.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)

    print(f"\n[DONE] Training complete! Log saved to: {log_path}")
    print(f"[DONE] Best Model Weights: {best_weights_path}")
    print("=" * 70)
    return best_weights_path, history


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Standard U-Net Baseline")
    parser.add_argument("--epochs", type=int, default=10, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size (4 recommended for 4GB VRAM)")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--smoke-test", action="store_true", help="Run 1 epoch on small subset")
    args = parser.parse_args()

    train_baseline(epochs=args.epochs, batch_size=args.batch_size, lr=args.lr, smoke_test=args.smoke_test)
