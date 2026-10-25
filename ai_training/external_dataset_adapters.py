"""
External Ovarian Ultrasound Dataset Adapters & Integration Architecture.
Supported Datasets:
1. MMOTU (Multi-Modality Ovarian Tumor Ultrasound: 2D B-mode & CEUS)
2. OvaTUS (Ovarian Tumor Ultrasound Dataset - Sigmlab / BV Phụ sản TW)
3. ShaunSpinelli/ultrasound_ovarian_seg (OTU_2D 8-class segmentation & normal ovary)
4. HananSaadat/ovarian_ultrasound_dataset (Normal / Dominant Follicle / PCO)
5. PCOSGen (Polycystic Ovary Syndrome 4,668 images)

Clinical Integrity:
- Keeps Physiological Follicles (<30mm / PCOS) mapped to O-RADS 1.
- Keeps Neoplastic Lesions (MMOTU, OvaTUS) mapped to O-RADS 2-5 segmentation targets.
- Preserves zero-leakage isolation from the local Vinmec benchmark cohort.
"""

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset

from backend.services.preprocessor import UltrasoundPreprocessor


class ClinicalCategory(StrEnum):
    NORMAL_PHYSIOLOGICAL = "O-RADS 1: Normal / Physiological Follicle / PCOS"
    BENIGN_NEOPLASM = "O-RADS 2-3: Benign Ovarian Neoplasm"
    INDETERMINATE_OR_HIGH_RISK = "O-RADS 4-5: Suspicious / Malignant Neoplasm"
    UNSPECIFIED_LESION = "Unspecified Lesion Mask"


@dataclass(frozen=True)
class ExternalDatasetConfig:
    name: str
    citation_source: str
    modality: str  # e.g., "2D B-Mode", "CEUS", "Multi-Modal"
    has_pixel_masks: bool
    clinical_focus: ClinicalCategory
    default_orads_tier: int  # 1 for follicles/normal, 2-5 for tumors


SUPPORTED_EXTERNAL_DATASETS = {
    "mmotu": ExternalDatasetConfig(
        name="MMOTU",
        citation_source="Li et al., 2022 (PubMed Central / Springer)",
        modality="2D B-Mode + CEUS",
        has_pixel_masks=True,
        clinical_focus=ClinicalCategory.BENIGN_NEOPLASM,
        default_orads_tier=2,
    ),
    "ovatus": ExternalDatasetConfig(
        name="OvaTUS",
        citation_source="Sigmlab & Bệnh viện Phụ sản Trung ương (Hà Nội)",
        modality="2D B-Mode",
        has_pixel_masks=True,
        clinical_focus=ClinicalCategory.BENIGN_NEOPLASM,
        default_orads_tier=2,
    ),
    "shaun_spinelli_otu": ExternalDatasetConfig(
        name="ShaunSpinelli/OTU_2D",
        citation_source="GitHub: ShaunSpinelli/ultrasound_ovarian_seg",
        modality="2D B-Mode",
        has_pixel_masks=True,
        clinical_focus=ClinicalCategory.UNSPECIFIED_LESION,
        default_orads_tier=2,
    ),
    "hanan_saadat": ExternalDatasetConfig(
        name="HananSaadat/ovarian_ultrasound_dataset",
        citation_source="Hanan Saadat (CC BY 4.0 - GitHub)",
        modality="2D B-Mode",
        has_pixel_masks=False,
        clinical_focus=ClinicalCategory.NORMAL_PHYSIOLOGICAL,
        default_orads_tier=1,
    ),
    "pcosgen": ExternalDatasetConfig(
        name="PCOSGen",
        citation_source="PCOSGen Polycystic Ovary Benchmark (4,668 images)",
        modality="2D B-Mode",
        has_pixel_masks=False,
        clinical_focus=ClinicalCategory.NORMAL_PHYSIOLOGICAL,
        default_orads_tier=1,
    ),
}


class ExternalUltrasoundAdapter(Dataset):
    """
    Standardizes disparate external ovarian ultrasound datasets into unified
    Letterbox 512x512 tensors with CLAHE enhancement for model pretraining or screening.
    """

    def __init__(
        self,
        samples: list[dict[str, Any]],
        dataset_key: str,
        target_size: tuple = (512, 512),
        is_train: bool = False,
    ):
        if dataset_key not in SUPPORTED_EXTERNAL_DATASETS:
            raise ValueError(f"Unsupported external dataset: {dataset_key}. Supported: {list(SUPPORTED_EXTERNAL_DATASETS.keys())}")

        self.samples = samples
        self.dataset_key = dataset_key
        self.config = SUPPORTED_EXTERNAL_DATASETS[dataset_key]
        self.target_size = target_size
        self.is_train = is_train
        self.preprocessor = UltrasoundPreprocessor(target_size=target_size)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        item = self.samples[idx]
        image_path = item["image_path"]

        # Read Grayscale
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"External image not found: {image_path}")

        image_raw = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image_raw is None:
            raise ValueError(f"Failed to decode image: {image_path}")

        # Standard 512x512 Letterbox + CLAHE
        padded_img, _ = self.preprocessor.letterbox_resize(image_raw, target_size=self.target_size, is_mask=False)
        enhanced_img = self.preprocessor.clahe.apply(padded_img)
        processed_image = torch.from_numpy(enhanced_img).unsqueeze(0).float() / 255.0

        # Handle mask if available
        mask_tensor = torch.zeros((1, *self.target_size), dtype=torch.float32)
        has_mask = False

        mask_path = item.get("mask_path")
        if mask_path and os.path.exists(mask_path):
            mask_raw = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
            if mask_raw is not None:
                mask_binary = (mask_raw > 0).astype(np.uint8)
                padded_mask, _ = self.preprocessor.letterbox_resize(mask_binary, target_size=self.target_size, is_mask=True)
                mask_tensor = torch.from_numpy(padded_mask).unsqueeze(0).float()
                has_mask = True

        return {
            "image": processed_image,
            "mask": mask_tensor,
            "has_mask": has_mask,
            "dataset_name": self.config.name,
            "clinical_focus": self.config.clinical_focus.value,
            "orads_tier": item.get("orads_tier", self.config.default_orads_tier),
            "label": item.get("label", "normal" if self.config.default_orads_tier == 1 else "neoplasm"),
            "image_id": item.get("sample_id", Path(image_path).stem),
        }
