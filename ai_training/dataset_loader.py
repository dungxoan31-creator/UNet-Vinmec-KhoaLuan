"""
Dataset Loader & Preprocessing Integration for Ovarian Ultrasound Segmentation.
Consumes image-level split CSVs and applies 512x512 Letterbox preprocessing.
Patient identifiers are not required by or passed into the model training batch.
"""

import os
from pathlib import Path

import albumentations as A
import cv2
import numpy as np
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

from backend.core.dataset_paths import resolve_dataset_path
from backend.core.image_utils import is_within_decoded_image_limit
from backend.services.preprocessor import UltrasoundPreprocessor


def cv2_imread_unicode(file_path, flags=cv2.IMREAD_GRAYSCALE):
    """Safely reads images with UTF-8 / Windows paths."""
    if not os.path.exists(file_path):
        return None
    try:
        with Image.open(file_path) as image_header:
            width, height = image_header.size
    except Exception:
        return None
    if not is_within_decoded_image_limit(width, height):
        raise ValueError(f"Decoded image exceeds the pixel limit: {file_path}")
    with open(file_path, "rb") as f:
        bytes_data = f.read()
    arr = np.frombuffer(bytes_data, dtype=np.uint8)
    image = cv2.imdecode(arr, flags)
    if image is None:
        return None
    if image.ndim not in (2, 3) or not is_within_decoded_image_limit(image.shape[1], image.shape[0]):
        raise ValueError(f"Decoded image exceeds the pixel limit: {file_path}")
    return image


class OvarianUltrasoundDataset(Dataset):
    def __init__(
        self,
        csv_file,
        target_size=(512, 512),
        is_train=False,
        seed=42,
        rotation_limit=10,
        elastic_probability=0.0,
    ):
        self.df = pd.read_csv(csv_file)
        self.csv_dir = os.path.abspath(os.path.dirname(csv_file))
        self.target_size = target_size
        self.is_train = is_train
        self.preprocessor = UltrasoundPreprocessor(target_size=target_size)
        if not 0 <= elastic_probability <= 1:
            raise ValueError("elastic_probability must be between 0 and 1")

        # Safe medical augmentations (only on train set)
        if self.is_train:
            transforms = [
                A.HorizontalFlip(p=0.5),
                A.RandomBrightnessContrast(brightness_limit=0.1, contrast_limit=0.1, p=0.4),
                A.Affine(
                    scale=(0.95, 1.05),
                    translate_percent=(-0.05, 0.05),
                    rotate=(-rotation_limit, rotation_limit),
                    interpolation=cv2.INTER_LINEAR,
                    mask_interpolation=cv2.INTER_NEAREST,
                    border_mode=cv2.BORDER_CONSTANT,
                    fill=0,
                    fill_mask=0,
                    p=0.4,
                ),
            ]
            if elastic_probability:
                transforms.append(
                    A.ElasticTransform(
                        alpha=1,
                        sigma=20,
                        interpolation=cv2.INTER_LINEAR,
                        mask_interpolation=cv2.INTER_NEAREST,
                        border_mode=cv2.BORDER_CONSTANT,
                        fill=0,
                        fill_mask=0,
                        p=elastic_probability,
                    )
                )
            self.transform = A.Compose(transforms, seed=seed)
        else:
            self.transform = None

    def _resolve_path(self, value):
        if os.path.isabs(value):
            return value
        relocated = resolve_dataset_path(Path(__file__).resolve().parents[1], value)
        if relocated.is_file():
            return str(relocated)
        directory = self.csv_dir
        while True:
            candidate = os.path.join(directory, value)
            if os.path.isfile(candidate):
                return candidate
            parent = os.path.dirname(directory)
            if parent == directory:
                return candidate
            directory = parent

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        img_path = self._resolve_path(str(row["image_path"]).replace("\\", "/"))
        mask_path = self._resolve_path(str(row["mask_path"]).replace("\\", "/"))
        case_id = str(row["case_id"])

        # 1. Read Raw Files
        raw_img = cv2_imread_unicode(img_path, cv2.IMREAD_GRAYSCALE)
        raw_mask = cv2_imread_unicode(mask_path, cv2.IMREAD_GRAYSCALE)

        if raw_img is None:
            raise FileNotFoundError(f"Image not found: {img_path}")
        if raw_mask is None:
            raise FileNotFoundError(f"Mask not found: {mask_path}")
        if raw_img.ndim != 2 or raw_mask.ndim != 2 or raw_img.shape != raw_mask.shape:
            raise ValueError(
                f"Image/mask dimensions differ for case {case_id}: "
                f"image {raw_img.shape}, mask {raw_mask.shape}"
            )
        if not np.isin(np.unique(raw_mask), (0, 1, 255)).all():
            raise ValueError(f"Mask contains non-binary source values for case {case_id}")
        # Ensure mask is strictly binary {0, 1}
        raw_mask = (raw_mask > 0).astype(np.uint8)

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
            "image_path": img_path
        }


def get_train_val_dataloaders(splits_dir="ai_training/splits", batch_size=4, num_workers=0, seed=42):
    train_csv = os.path.join(splits_dir, "train.csv")
    val_csv = os.path.join(splits_dir, "val.csv")
    train_ds = OvarianUltrasoundDataset(train_csv, is_train=True, seed=seed)
    val_ds = OvarianUltrasoundDataset(val_csv, is_train=False)

    generator = torch.Generator().manual_seed(seed)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers, generator=generator)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)
    return train_loader, val_loader


def get_dataloaders(splits_dir="ai_training/splits", batch_size=4, num_workers=0, seed=42):
    train_loader, val_loader = get_train_val_dataloaders(splits_dir, batch_size, num_workers, seed)
    test_csv = os.path.join(splits_dir, "test.csv")
    test_ds = OvarianUltrasoundDataset(test_csv, is_train=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)

    return train_loader, val_loader, test_loader
