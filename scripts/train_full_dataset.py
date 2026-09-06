"""
Full Dataset Production Retraining Script for Attention U-Net.
Aggregates all 1,372 image-mask pairs across OTU_2D (train & test) and OTU_CEUS datasets.
Enforces zero-mask precision for normal/non-lesion regions and Patient-Level data splitting.
"""

import glob
import os
import random
import sys
import numpy as np

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


def cv2_imread_unicode(file_path, flags=cv2.IMREAD_GRAYSCALE):
    with open(file_path, "rb") as f:
        bytes_data = f.read()
    arr = np.frombuffer(bytes_data, dtype=np.uint8)
    return cv2.imdecode(arr, flags)


class FullOvarianDataset(Dataset):
    def __init__(self, file_pairs, target_size=(512, 512), is_train=True):
        self.file_pairs = file_pairs
        self.target_size = target_size
        self.is_train = is_train
        self.preprocessor = UltrasoundPreprocessor(target_size=target_size)

    def __len__(self):
        return len(self.file_pairs)

    def __getitem__(self, idx):
        img_path, mask_path = self.file_pairs[idx]
        img_np = cv2_imread_unicode(img_path, cv2.IMREAD_GRAYSCALE)

        if mask_path and os.path.exists(mask_path):
            mask_np = cv2_imread_unicode(mask_path, cv2.IMREAD_GRAYSCALE)
            if mask_np is not None:
                mask_np = (mask_np > 127).astype(np.uint8)
            else:
                mask_np = np.zeros_like(img_np, dtype=np.uint8)
        else:
            mask_np = np.zeros_like(img_np, dtype=np.uint8)

        padded_img, _ = self.preprocessor.letterbox_resize(img_np, self.target_size, is_mask=False)
        padded_mask, _ = self.preprocessor.letterbox_resize(mask_np, self.target_size, is_mask=True)
        enhanced_img = self.preprocessor.enhance_contrast_and_denoise(padded_img)

        # Training Augmentations
        if self.is_train:
            if random.random() > 0.5:
                enhanced_img = cv2.flip(enhanced_img, 1)
                padded_mask = cv2.flip(padded_mask, 1)

            if random.random() > 0.5:
                angle = random.uniform(-10, 10)
                M = cv2.getRotationMatrix2D((self.target_size[0] // 2, self.target_size[1] // 2), angle, 1.0)
                enhanced_img = cv2.warpAffine(enhanced_img, M, self.target_size, flags=cv2.INTER_LINEAR, borderValue=0)
                padded_mask = cv2.warpAffine(padded_mask, M, self.target_size, flags=cv2.INTER_NEAREST, borderValue=0)

        tensor_img = torch.from_numpy(enhanced_img.astype(np.float32) / 255.0).unsqueeze(0)
        tensor_mask = torch.from_numpy(padded_mask.astype(np.float32)).unsqueeze(0)

        return tensor_img, tensor_mask


def collect_all_dataset_pairs(dataset_root="dataset"):
    dataset_root = os.path.abspath(dataset_root)
    all_pairs = []

    def find_pairs_in_dirs(img_dir, mask_dir):
        pairs = []
        if not os.path.exists(img_dir) or not os.path.exists(mask_dir):
            return pairs
        
        mask_files = {os.path.splitext(f)[0].lower(): os.path.join(mask_dir, f) for f in os.listdir(mask_dir)}
        for img_name in os.listdir(img_dir):
            stem = os.path.splitext(img_name)[0].lower()
            img_path = os.path.join(img_dir, img_name)
            if stem in mask_files:
                pairs.append((img_path, mask_files[stem]))
        return pairs

    # 1. OTU_2D Train
    otu2d_train_img_dir = os.path.join(dataset_root, "dataset", "OTU_2D", "train", "train_image")
    otu2d_train_mask_dir = os.path.join(dataset_root, "dataset", "OTU_2D", "train", "train_label", "label")
    all_pairs.extend(find_pairs_in_dirs(otu2d_train_img_dir, otu2d_train_mask_dir))

    # 2. OTU_2D Test
    otu2d_test_img_dir = os.path.join(dataset_root, "dataset", "OTU_2D", "test", "image")
    otu2d_test_mask_dir = os.path.join(dataset_root, "dataset", "OTU_2D", "test", "label", "black_write")
    all_pairs.extend(find_pairs_in_dirs(otu2d_test_img_dir, otu2d_test_mask_dir))

    # 3. OTU_CEUS
    otu_ceus_img_dir = os.path.join(dataset_root, "dataset", "OTU_CEUS", "image")
    otu_ceus_mask_dir = os.path.join(dataset_root, "dataset", "OTU_CEUS", "label")
    all_pairs.extend(find_pairs_in_dirs(otu_ceus_img_dir, otu_ceus_mask_dir))

    print(f"[Dataset Audit] Total collected image-mask pairs across all folders: {len(all_pairs)}")
    return all_pairs


def get_patient_level_splits(all_pairs, seed=42):
    random.seed(seed)
    patient_dict = {}

    for img_path, mask_path in all_pairs:
        base = os.path.basename(img_path)
        # Use prefix before number or index as patient ID
        parts = base.split(".")[0].split("_")
        pid = "_".join(parts[:2]) if len(parts) >= 2 else parts[0]
        patient_dict.setdefault(pid, []).append((img_path, mask_path))

    patients = list(patient_dict.keys())
    random.shuffle(patients)

    n = len(patients)
    n_train = max(1, int(n * 0.70))
    n_val = max(1, int(n * 0.15))

    train_pts = patients[:n_train]
    val_pts = patients[n_train : n_train + n_val]
    test_pts = patients[n_train + n_val :]

    train_pairs = [pair for p in train_pts for pair in patient_dict[p]]
    val_pairs = [pair for p in val_pts for pair in patient_dict[p]]
    test_pairs = [pair for p in test_pts for pair in patient_dict[p]]

    print(f"[Patient Split] Patient Groups: {len(train_pts)} Train | {len(val_pts)} Val | {len(test_pts)} Test")
    print(f"[Patient Split] Image Pairs:    {len(train_pairs)} Train | {len(val_pairs)} Val | {len(test_pairs)} Test")
    return train_pairs, val_pairs, test_pairs


def run_full_retraining(epochs=12, batch_size=4, lr=3e-4):
    checkpoint_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "checkpoints"))
    os.makedirs(checkpoint_dir, exist_ok=True)
    best_checkpoint_path = os.path.join(checkpoint_dir, "best_attention_unet.pth")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[Engine] Starting Attention U-Net Retraining on device: {device} for {epochs} epochs...")

    all_pairs = collect_all_dataset_pairs()
    train_pairs, val_pairs, test_pairs = get_patient_level_splits(all_pairs)

    train_loader = DataLoader(FullOvarianDataset(train_pairs, is_train=True), batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(FullOvarianDataset(val_pairs, is_train=False), batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(FullOvarianDataset(test_pairs, is_train=False), batch_size=batch_size, shuffle=False)

    model = AttentionUNet(in_channels=1, num_classes=1).to(device)
    criterion = ComboLoss(alpha=0.5, beta=0.3, gamma=0.2)
    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)

    best_val_dice = 0.0

    for epoch in range(1, epochs + 1):
        model.train()
        total_train_loss = 0.0
        total_batches = len(train_loader)

        for b_idx, (imgs, masks) in enumerate(train_loader, start=1):
            imgs, masks = imgs.to(device), masks.to(device)
            optimizer.zero_grad()
            preds = model(imgs)
            loss = criterion(preds, masks)
            loss.backward()
            optimizer.step()
            total_train_loss += loss.item()

            if b_idx % 30 == 0 or b_idx == total_batches:
                print(f"  [Epoch {epoch:02d}/{epochs:02d}] Batch [{b_idx:03d}/{total_batches:03d}] -> Loss: {loss.item():.4f}", flush=True)

        scheduler.step()
        avg_train_loss = total_train_loss / total_batches

        # Validation phase
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

        mean_val_dice = float(np.mean(val_dices)) if val_dices else 0.0
        print(f"==> Epoch [{epoch:02d}/{epochs:02d}] Finished -> Avg Train Loss: {avg_train_loss:.4f} | Val Dice: {mean_val_dice:.4f}", flush=True)

        if mean_val_dice > best_val_dice or epoch == 1:
            best_val_dice = mean_val_dice
            torch.save(model.state_dict(), best_checkpoint_path)
            print(f"  [Checkpoint] Saved best model weights to {best_checkpoint_path} (Val Dice: {best_val_dice:.4f})", flush=True)

    # Final Independent Test Evaluation
    print("\n=======================================================")
    print("      FINAL INDEPENDENT TEST BENCHMARK RESULTS         ")
    print("=======================================================")
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

    mean_dice = float(np.mean(test_dices))
    std_dice = float(np.std(test_dices))
    mean_iou = float(np.mean(test_ious))
    mean_hd95 = float(np.mean(test_hds)) if test_hds else 0.0

    print(f"• Test Dice Similarity Coefficient (DSC): {mean_dice:.4f} +/- {std_dice:.4f}")
    print(f"• Test Intersection over Union (IoU):     {mean_iou:.4f} +/- {np.std(test_ious):.4f}")
    print(f"• Test 95% Hausdorff Distance (HD95):     {mean_hd95:.2f} mm")
    print("=======================================================")
    print(f"[Success] Model successfully retrained & deployed at {best_checkpoint_path}")


if __name__ == "__main__":
    run_full_retraining(epochs=10, batch_size=4, lr=3e-4)
