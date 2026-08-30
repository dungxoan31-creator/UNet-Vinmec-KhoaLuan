"""
Robust Retraining Pipeline for Attention U-Net on Clean 70/15/15 OTU Dataset:
- Loss: Hybrid BCE + Soft Dice + Focal Loss
- Optimizer: AdamW with Cosine Annealing Learning Rate
- Metrics: Validation Dice, IoU, Precision, Recall, Specificity
- Checkpointing: Saves best weights to production model directories
"""

import os
import sys
import time
import json
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models.attention_unet import AttentionUNet
from ai_training.dataset_loader import get_dataloaders

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
        bce = nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction='none')
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

def compute_metrics(logits, targets, threshold=0.5):
    probs = torch.sigmoid(logits)
    preds = (probs > threshold).float()

    preds_flat = preds.view(-1)
    targets_flat = targets.view(-1)

    tp = (preds_flat * targets_flat).sum().item()
    fp = (preds_flat * (1.0 - targets_flat)).sum().item()
    fn = ((1.0 - preds_flat) * targets_flat).sum().item()
    tn = ((1.0 - preds_flat) * (1.0 - targets_flat)).sum().item()

    smooth = 1e-6
    dice = (2.0 * tp + smooth) / (2.0 * tp + fp + fn + smooth)
    iou = (tp + smooth) / (tp + fp + fn + smooth)
    precision = (tp + smooth) / (tp + fp + smooth)
    recall = (tp + smooth) / (tp + fn + smooth)
    specificity = (tn + smooth) / (tn + fp + smooth)

    return {
        "dice": dice,
        "iou": iou,
        "precision": precision,
        "recall": recall,
        "specificity": specificity
    }

def train_model(epochs=5, batch_size=8, lr=1e-4):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[Training] Using Device: {device}")

    train_loader, val_loader, test_loader = get_dataloaders(batch_size=batch_size, num_workers=0)
    print(f"[Data] Train batches: {len(train_loader)} | Val batches: {len(val_loader)} | Test batches: {len(test_loader)}")

    model = AttentionUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    criterion = HybridSegmentationLoss()
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)

    best_val_dice = 0.0
    training_history = []

    os.makedirs("ai_training/production_model", exist_ok=True)
    os.makedirs("checkpoints", exist_ok=True)

    for epoch in range(1, epochs + 1):
        start_time = time.time()
        model.train()
        train_loss = 0.0

        for batch in train_loader:
            images = batch["image"].to(device)
            masks = batch["mask"].to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, masks)
            loss.backward()
            optimizer.step()

            train_loss += loss.item()

        scheduler.step()
        train_loss /= len(train_loader)

        # Validation phase
        model.eval()
        val_loss = 0.0
        val_dice = 0.0
        val_iou = 0.0
        val_prec = 0.0
        val_rec = 0.0
        val_spec = 0.0

        with torch.no_grad():
            for batch in val_loader:
                images = batch["image"].to(device)
                masks = batch["mask"].to(device)

                outputs = model(images)
                loss = criterion(outputs, masks)
                val_loss += loss.item()

                m = compute_metrics(outputs, masks)
                val_dice += m["dice"]
                val_iou += m["iou"]
                val_prec += m["precision"]
                val_rec += m["recall"]
                val_spec += m["specificity"]

        val_loss /= len(val_loader)
        val_dice /= len(val_loader)
        val_iou /= len(val_loader)
        val_prec /= len(val_loader)
        val_rec /= len(val_loader)
        val_spec /= len(val_loader)

        duration = time.time() - start_time
        print(f"Epoch [{epoch}/{epochs}] ({duration:.1f}s) | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Dice: {val_dice:.4f} | Val IoU: {val_iou:.4f} | Val Prec: {val_prec:.4f} | Val Rec: {val_rec:.4f}")

        epoch_record = {
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "val_loss": round(val_loss, 4),
            "val_dice": round(val_dice, 4),
            "val_iou": round(val_iou, 4),
            "val_precision": round(val_prec, 4),
            "val_recall": round(val_rec, 4),
            "val_specificity": round(val_spec, 4),
            "duration_sec": round(duration, 1)
        }
        training_history.append(epoch_record)

        # Checkpoint if best
        if val_dice > best_val_dice:
            best_val_dice = val_dice
            v2_path = "ai_training/production_model/best_attention_unet_v2.pth"
            chk_path = "checkpoints/best_attention_unet.pth"

            torch.save(model.state_dict(), v2_path)
            torch.save(model.state_dict(), chk_path)
            print(f"--> [CHECKPOINT] Saved new best model (Val Dice: {val_dice:.4f}) to {v2_path} and {chk_path}")

    # Save training log
    with open("ai_training/production_model/retraining_log.json", "w", encoding="utf-8") as f:
        json.dump(training_history, f, indent=4)

    print(f"\n[Training Completed] Best Validation Dice Score: {best_val_dice:.4f}")

if __name__ == "__main__":
    train_model(epochs=4, batch_size=8, lr=1.5e-4)
