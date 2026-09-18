"""
Dataset Loader & Preprocessing Integration for Ovarian Ultrasound Segmentation.
Complies with Patient-Level Split and Medical Image Standardization (512x512 Letterbox).
"""

import os
import cv2
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
import albumentations as A

from backend.services.preprocessor import UltrasoundPreprocessor


def cv2_imread_unicode(file_path, flags=cv2.IMREAD_GRAYSCALE):
    """Safely reads images with UTF-8 / Windows paths."""
    if not os.path.exists(file_path):
        return None
    with open(file_path, "rb") as f:
        bytes_data = f.read()
    arr = np.frombuffer(bytes_data, dtype=np.uint8)
    return cv2.imdecode(arr, flags)


class OvarianUltrasoundDataset(Dataset):
    def __init__(self, csv_file, target_size=(512, 512), is_train=False):
        self.df = pd.read_csv(csv_file)
        self.target_size = target_size
        self.is_train = is_train
        self.preprocessor = UltrasoundPreprocessor(target_size=target_size)

        # Safe medical augmentations (only on train set)
        if self.is_train:
            self.transform = A.Compose([
                A.HorizontalFlip(p=0.5),
                A.RandomBrightnessContrast(brightness_limit=0.1, contrast_limit=0.1, p=0.4),
                A.ShiftScaleRotate(shift_limit=0.05, scale_limit=0.05, rotate_limit=10, border_mode=cv2.BORDER_CONSTANT, p=0.4)
            ])
        else:
            self.transform = None

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_path = str(row["image_path"]).replace("\\", "/")
        mask_path = str(row["mask_path"]).replace("\\", "/")
        case_id = str(row["case_id"])
        patient_id = str(row.get("patient_id", "UNKNOWN"))

        # 1. Read Raw Files
        raw_img = cv2_imread_unicode(img_path, cv2.IMREAD_GRAYSCALE)
        raw_mask = cv2_imread_unicode(mask_path, cv2.IMREAD_GRAYSCALE)

        if raw_img is None:
            raise FileNotFoundError(f"Image not found: {img_path}")
        if raw_mask is None:
            # Fallback for empty mask if missing on disk
            raw_mask = np.zeros_like(raw_img, dtype=np.uint8)

        # Ensure mask is strictly binary {0, 1}
        raw_mask = (raw_mask > 127).astype(np.uint8)

        # 2. Letterbox Resize (Bilinear for Image, Nearest for Mask)
        padded_img, _ = self.preprocessor.letterbox_resize(raw_img, target_size=self.target_size, is_mask=False)
        padded_mask, _ = self.preprocessor.letterbox_resize(raw_mask, target_size=self.target_size, is_mask=True)

        # 3. CLAHE Contrast Enhancement
        enhanced_img = self.preprocessor.clahe.apply(padded_img)

        # 4. Augmentation (if train)
        if self.transform is not None:
            augmented = self.transform(image=enhanced_img, mask=padded_mask)
            enhanced_img = augmented["image"]
            padded_mask = augmented["mask"]

        # 5. Normalization to [0, 1] & ToTensor (1, H, W)
        img_tensor = torch.from_numpy(enhanced_img).unsqueeze(0).float() / 255.0
        mask_tensor = torch.from_numpy(padded_mask).unsqueeze(0).float()

        return {
            "image": img_tensor,
            "mask": mask_tensor,
            "case_id": case_id,
            "patient_id": patient_id,
            "image_path": img_path
        }


def get_dataloaders(splits_dir="ai_training/splits", batch_size=4, num_workers=0):
    train_csv = os.path.join(splits_dir, "train.csv")
    val_csv = os.path.join(splits_dir, "val.csv")
    test_csv = os.path.join(splits_dir, "test.csv")

    train_ds = OvarianUltrasoundDataset(train_csv, is_train=True)
    val_ds = OvarianUltrasoundDataset(val_csv, is_train=False)
    test_ds = OvarianUltrasoundDataset(test_csv, is_train=False)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)

    return train_loader, val_loader, test_loader
