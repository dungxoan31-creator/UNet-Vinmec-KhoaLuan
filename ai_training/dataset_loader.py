"""
Standardized PyTorch Dataset & DataLoader for Ovarian Ultrasound Segmentation:
- Synchronous Letterbox resize to 512x512 (Aspect Ratio preserving)
- Mask interpolation: cv2.INTER_NEAREST (zero artificial blurry border artifacts)
- Image enhancement: Speckle median denoise + CLAHE (clip=2.0, tile=(8,8))
- Normalization: [0.0, 1.0] float tensor (1, 1, 512, 512)
- Strict alignment between Training and Production Inference preprocessing
"""

import os
import sys
import random
import cv2
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.services.preprocessor import UltrasoundPreprocessor

def cv2_imread_unicode(file_path, flags=cv2.IMREAD_GRAYSCALE):
    if not os.path.exists(file_path):
        return None
    with open(file_path, "rb") as f:
        bytes_data = f.read()
    arr = np.frombuffer(bytes_data, dtype=np.uint8)
    return cv2.imdecode(arr, flags)

class OvarianUltrasoundDataset(Dataset):
    """
    Standardized Dataset for Ovarian Ultrasound Segmentation.
    Guarantees 100% identical preprocessing between Training and Inference.
    """
    def __init__(self, csv_path, target_size=(512, 512), is_train=False, enable_augmentation=True):
        self.df = pd.read_csv(csv_path)
        self.target_size = target_size
        self.is_train = is_train
        self.enable_augmentation = enable_augmentation and is_train
        self.preprocessor = UltrasoundPreprocessor(target_size=target_size)

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_path = row["image_path"]
        mask_path = row["mask_path"]
        case_id = row.get("case_id", row.get("sample_id", f"case_{idx}"))

        # 1. Read Image and Mask
        img_raw = cv2_imread_unicode(img_path, cv2.IMREAD_GRAYSCALE)
        mask_raw = cv2_imread_unicode(mask_path, cv2.IMREAD_GRAYSCALE)

        if img_raw is None:
            img_raw = np.zeros(self.target_size, dtype=np.uint8)
        if mask_raw is None:
            mask_raw = np.zeros(self.target_size, dtype=np.uint8)

        orig_h, orig_w = img_raw.shape[:2]

        # 2. Binary thresholding for Ground Truth
        mask_binary = (mask_raw > 127).astype(np.uint8)

        # 3. Synchronous Letterbox Resize preserving aspect ratio
        padded_img, transform_params = self.preprocessor.letterbox_resize(img_raw, self.target_size)

        # Apply exact same scale & padding to mask with NEAREST interpolation
        scale = transform_params["scale"]
        pad_x = transform_params["pad_x"]
        pad_y = transform_params["pad_y"]
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        resized_mask = cv2.resize(mask_binary, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
        padded_mask = np.zeros(self.target_size, dtype=np.uint8)
        padded_mask[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized_mask

        # 4. Image Enhancement (Speckle filtering + CLAHE)
        enhanced_img = self.preprocessor.enhance_contrast_and_denoise(padded_img)

        # 5. Ultrasound-safe Augmentations (Training only)
        if self.enable_augmentation:
            # Horizontal Flip (Ovarian bilateral anatomy)
            if random.random() > 0.5:
                enhanced_img = cv2.flip(enhanced_img, 1)
                padded_mask = cv2.flip(padded_mask, 1)

            # Small affine rotation (+/- 10 degrees)
            if random.random() > 0.5:
                angle = random.uniform(-10.0, 10.0)
                M = cv2.getRotationMatrix2D((self.target_size[1] // 2, self.target_size[0] // 2), angle, 1.0)
                enhanced_img = cv2.warpAffine(enhanced_img, M, self.target_size, flags=cv2.INTER_LINEAR, borderValue=0)
                padded_mask = cv2.warpAffine(padded_mask, M, self.target_size, flags=cv2.INTER_NEAREST, borderValue=0)

            # Photometric Jitter (Brightness/Contrast +/- 10%)
            if random.random() > 0.5:
                alpha = random.uniform(0.9, 1.1)
                beta = random.uniform(-10, 10)
                enhanced_img = np.clip(alpha * enhanced_img + beta, 0, 255).astype(np.uint8)

            # Speckle noise simulation
            if random.random() > 0.7:
                noise = np.random.normal(0, 4.0, enhanced_img.shape)
                enhanced_img = np.clip(enhanced_img + noise, 0, 255).astype(np.uint8)

        # 6. Normalize to [0.0, 1.0] float tensor (1, 1, 512, 512)
        norm_img = enhanced_img.astype(np.float32) / 255.0
        norm_mask = padded_mask.astype(np.float32)

        tensor_img = torch.from_numpy(norm_img).unsqueeze(0)   # (1, H, W)
        tensor_mask = torch.from_numpy(norm_mask).unsqueeze(0) # (1, H, W)

        return {
            "image": tensor_img,
            "mask": tensor_mask,
            "case_id": case_id,
            "sample_id": case_id,
            "img_path": img_path,
            "mask_path": mask_path,
            "orig_h": orig_h,
            "orig_w": orig_w
        }

def get_dataloaders(protocol="unified", batch_size=8, target_size=(512, 512), num_workers=0):
    """
    Returns train, val, and test DataLoaders for the specified protocol.
    protocol: 'unified' (70/15/15) or 'standard' (700/120/382)
    """
    if protocol == "standard":
        train_csv = "ai_training/splits/train.csv"
        val_csv = "ai_training/splits/val.csv"
        test_csv = "ai_training/splits/test.csv"
    else:
        train_csv = "ai_training/splits/train_v2.csv"
        val_csv = "ai_training/splits/val_v2.csv"
        test_csv = "ai_training/splits/test_v2.csv"

    train_ds = OvarianUltrasoundDataset(train_csv, target_size=target_size, is_train=True, enable_augmentation=True)
    val_ds = OvarianUltrasoundDataset(val_csv, target_size=target_size, is_train=False, enable_augmentation=False)
    test_ds = OvarianUltrasoundDataset(test_csv, target_size=target_size, is_train=False, enable_augmentation=False)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)
    test_loader = DataLoader(test_ds, batch_size=1, shuffle=False, num_workers=num_workers)

    return train_loader, val_loader, test_loader
