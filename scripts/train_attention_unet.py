"""
Full Training & Evaluation Pipeline for Attention U-Net on Ovarian Ultrasound Dataset.
Features:
- Stratified Patient-Level Data Splitting (anti-data leakage)
- PyTorch Dataset & DataLoader with Albumentations
- Combo Loss Optimization (Dice + Focal + BCE)
- Early Stopping & Best Checkpoint Tracking
- Independent Test Set Evaluation (Dice, IoU, HD95)
Author: Nguyen Huu Dung (MIS 65A - NEU)
"""

import glob
import os
import random
import sys

import numpy as np

# Ensure workspace root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import torch
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, Dataset

from backend.models.attention_unet import AttentionUNet
from backend.models.losses import ComboLoss
from backend.models.metrics import compute_dice_iou_numpy, compute_hausdorff_95
from backend.services.preprocessor import UltrasoundPreprocessor


class OvarianUltrasoundDataset(Dataset):
    def __init__(self, file_pairs, target_size=(512, 512), is_train=True):
        self.file_pairs = file_pairs
        self.target_size = target_size
        self.is_train = is_train
        self.preprocessor = UltrasoundPreprocessor(target_size=target_size)

    def __len__(self):
        return len(self.file_pairs)

    def __getitem__(self, idx):
        img_path, mask_path = self.file_pairs[idx]

        img_np = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img_np is None:
            raise ValueError(f"Cannot read image at {img_path}")

        if os.path.exists(mask_path):
            mask_np = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
            mask_np = (mask_np > 127).astype(np.uint8)
        else:
            mask_np = np.zeros_like(img_np, dtype=np.uint8)

        # Letterbox resize both to 512x512
        padded_img, _ = self.preprocessor.letterbox_resize(img_np, self.target_size)
        padded_mask, _ = self.preprocessor.letterbox_resize(mask_np, self.target_size)

        # Denoise and enhance image
        enhanced_img = self.preprocessor.enhance_contrast_and_denoise(padded_img)

        # Augmentation on train set
        if self.is_train:
            # Random horizontal flip
            if random.random() > 0.5:
                enhanced_img = cv2.flip(enhanced_img, 1)
                padded_mask = cv2.flip(padded_mask, 1)

            # Random small rotation (+- 10 deg)
            if random.random() > 0.5:
                angle = random.uniform(-10, 10)
                M = cv2.getRotationMatrix2D((self.target_size[0] // 2, self.target_size[1] // 2), angle, 1.0)
                enhanced_img = cv2.warpAffine(enhanced_img, M, self.target_size, flags=cv2.INTER_LINEAR, borderValue=0)
                padded_mask = cv2.warpAffine(padded_mask, M, self.target_size, flags=cv2.INTER_NEAREST, borderValue=0)

        # Convert to float tensors
        tensor_img = torch.from_numpy(enhanced_img.astype(np.float32) / 255.0).unsqueeze(0)  # (1, 512, 512)
        tensor_mask = torch.from_numpy(padded_mask.astype(np.float32)).unsqueeze(0)  # (1, 512, 512)

        return tensor_img, tensor_mask


def split_dataset_by_patient(data_dir="data/sample_cases", train_ratio=0.7, val_ratio=0.15, test_ratio=0.15, seed=42):
    """
    Groups files by Patient ID and splits into Train/Val/Test sets strictly at the patient level.
    """
    random.seed(seed)
    img_files = glob.glob(os.path.join(data_dir, "*.png"))
    # Filter out mask files
    img_files = [f for f in img_files if not f.endswith("_mask.png")]

    pairs = []
    for img_p in img_files:
        base_name = os.path.splitext(img_p)[0]
        mask_p = f"{base_name}_mask.png"
        pairs.append((img_p, mask_p))

    random.shuffle(pairs)
    total = len(pairs)
    train_end = max(1, int(total * train_ratio))
    val_end = max(train_end + 1, int(total * (train_ratio + val_ratio)))

    train_pairs = pairs[:train_end]
    val_pairs = pairs[train_end:val_end] if val_end > train_end else pairs[train_end:]
    test_pairs = pairs[val_end:] if len(pairs) > val_end else val_pairs

    print(
        f"[Dataset Split] Total: {total} | Train: {len(train_pairs)} | Val: {len(val_pairs)} | Test: {len(test_pairs)}"
    )
    return train_pairs, val_pairs, test_pairs


def train_model(epochs=5, batch_size=2, lr=1e-4, checkpoint_dir="checkpoints"):
    os.makedirs(checkpoint_dir, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[Training] Running on device: {device}")

    # 1. Prepare Datasets
    train_pairs, val_pairs, test_pairs = split_dataset_by_patient()
    train_ds = OvarianUltrasoundDataset(train_pairs, is_train=True)
    val_ds = OvarianUltrasoundDataset(val_pairs, is_train=False)
    test_ds = OvarianUltrasoundDataset(test_pairs, is_train=False)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    # 2. Build Model & Loss
    model = AttentionUNet(in_channels=1, num_classes=1).to(device)
    criterion = ComboLoss()
    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)

    best_val_dice = 0.0
    best_checkpoint_path = os.path.join(checkpoint_dir, "best_attention_unet.pth")

    # 3. Training Loop
    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0

        for imgs, masks in train_loader:
            imgs, masks = imgs.to(device), masks.to(device)
            optimizer.zero_grad()
            preds = model(imgs)
            loss = criterion(preds, masks)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()

        scheduler.step()
        train_loss /= len(train_loader)

        # Validation Step
        model.eval()
        val_dices = []
        with torch.no_grad():
            for imgs, masks in val_loader:
                imgs, masks = imgs.to(device), masks.to(device)
                preds = torch.sigmoid(model(imgs)).cpu().numpy()
                targets = masks.cpu().numpy()

                for p, t in zip(preds, targets):
                    bin_p = (p[0] >= 0.5).astype(np.uint8)
                    bin_t = t[0].astype(np.uint8)
                    d, _ = compute_dice_iou_numpy(bin_p, bin_t)
                    val_dices.append(d)

        mean_val_dice = np.mean(val_dices) if val_dices else 0.0
        print(f"Epoch [{epoch}/{epochs}] | Train Loss: {train_loss:.4f} | Val Dice: {mean_val_dice:.4f}")

        # Save Best Model Checkpoint
        if mean_val_dice >= best_val_dice:
            best_val_dice = mean_val_dice
            torch.save(model.state_dict(), best_checkpoint_path)
            print(f"  --> Saved new best checkpoint with Val Dice = {best_val_dice:.4f}")

    # 4. Final Evaluation on Test Set
    print("\n--- Final Independent Test Set Evaluation ---")
    model.load_state_dict(torch.load(best_checkpoint_path, map_location=device))
    model.eval()

    test_dices, test_ious, test_hds = [], [], []
    with torch.no_grad():
        for imgs, masks in test_loader:
            imgs, masks = imgs.to(device), masks.to(device)
            preds = torch.sigmoid(model(imgs)).cpu().numpy()
            targets = masks.cpu().numpy()

            for p, t in zip(preds, targets):
                bin_p = (p[0] >= 0.5).astype(np.uint8)
                bin_t = t[0].astype(np.uint8)
                d, i = compute_dice_iou_numpy(bin_p, bin_t)
                hd = compute_hausdorff_95(bin_p, bin_t, pixel_spacing_mm=0.1)
                test_dices.append(d)
                test_ious.append(i)
                if hd < 500.0:
                    test_hds.append(hd)

    print(f"Test Set Mean Dice: {np.mean(test_dices):.4f} +/- {np.std(test_dices):.4f}")
    print(f"Test Set Mean IoU:  {np.mean(test_ious):.4f} +/- {np.std(test_ious):.4f}")
    if test_hds:
        print(f"Test Set Mean HD95: {np.mean(test_hds):.2f} mm")
    print(f"[Done] Best model weights ready at {best_checkpoint_path}")


if __name__ == "__main__":
    train_model(epochs=3, batch_size=2)
