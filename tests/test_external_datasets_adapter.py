"""
Tests for External Ovarian Ultrasound Dataset Adapters (MMOTU, OvaTUS, OTU_2D, HananSaadat, PCOSGen).
Enforces Clinical Guardrails & Letterbox Preprocessing Parity.
"""

import cv2
import numpy as np

from ai_training.external_dataset_adapters import (
    SUPPORTED_EXTERNAL_DATASETS,
    ClinicalCategory,
    ExternalUltrasoundAdapter,
)
from scripts.prepare_external_datasets import scan_external_dataset_directory


def test_supported_datasets_registration():
    """Verify all 5 external datasets are formally registered."""
    keys = set(SUPPORTED_EXTERNAL_DATASETS.keys())
    assert {"mmotu", "ovatus", "shaun_spinelli_otu", "hanan_saadat", "pcosgen"} <= keys


def test_external_dataset_name_does_not_create_automatic_orads_tier():
    """
    O-RADS is not inferred from a dataset name, broad dataset focus, or segmentation mask.
    """
    pcos = SUPPORTED_EXTERNAL_DATASETS["pcosgen"]
    saadat = SUPPORTED_EXTERNAL_DATASETS["hanan_saadat"]

    assert pcos.default_orads_tier is None
    assert pcos.clinical_focus == ClinicalCategory.NORMAL_PHYSIOLOGICAL
    assert pcos.has_pixel_masks is False

    assert saadat.default_orads_tier is None
    assert saadat.clinical_focus == ClinicalCategory.NORMAL_PHYSIOLOGICAL

    # Dataset-level names and masks do not establish an O-RADS tier or pathology label.
    mmotu = SUPPORTED_EXTERNAL_DATASETS["mmotu"]
    ovatus = SUPPORTED_EXTERNAL_DATASETS["ovatus"]

    assert mmotu.has_pixel_masks is True
    assert mmotu.default_orads_tier is None
    assert mmotu.clinical_focus == ClinicalCategory.UNSPECIFIED_LESION
    assert ovatus.has_pixel_masks is True
    assert ovatus.default_orads_tier is None
    assert ovatus.clinical_focus == ClinicalCategory.UNSPECIFIED_LESION


def test_external_adapter_preprocessing_pipeline(tmp_path):
    """Test that external images are normalized to 512x512 Letterbox tensors."""
    # Create mock 2D ultrasound image (e.g. 600x800)
    mock_img = np.random.randint(50, 200, (600, 800), dtype=np.uint8)
    img_path = tmp_path / "mock_ultrasound.png"
    cv2.imwrite(str(img_path), mock_img)

    # Create mock mask
    mock_mask = np.zeros((600, 800), dtype=np.uint8)
    mock_mask[200:400, 300:500] = 255
    mask_path = tmp_path / "mock_ultrasound_mask.png"
    cv2.imwrite(str(mask_path), mock_mask)

    samples = [{
        "sample_id": "test_case_01",
        "image_path": str(img_path),
        "mask_path": str(mask_path),
        "orads_tier": 3,
    }]

    adapter = ExternalUltrasoundAdapter(
        samples=samples,
        dataset_key="mmotu",
        target_size=(512, 512),
        is_train=False,
    )

    assert len(adapter) == 1
    item = adapter[0]

    assert item["dataset_name"] == "MMOTU"
    assert item["image"].shape == (1, 512, 512)
    assert item["mask"].shape == (1, 512, 512)
    assert item["has_mask"] is True
    assert item["orads_tier"] == 3
    assert item["label"] is None


def test_mmotu_global_category_label_file_is_attached_without_orads_inference(tmp_path):
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    image_path = img_dir / "1.JPG"
    assert cv2.imwrite(str(image_path), np.full((80, 120), 90, dtype=np.uint8))
    label_file = tmp_path / "train_cls.txt"
    label_file.write_text("1.JPG 5\n", encoding="utf-8")

    summary = scan_external_dataset_directory(
        dataset_key="mmotu",
        images_dir=img_dir,
        labels_csv=[label_file],
    )

    sample = summary["samples"][0]
    assert sample["global_category_id"] == 5
    assert sample["global_category"] == "normal_ovary"
    assert sample["default_orads_tier"] is None
    assert summary["patient_level_independence_verified"] is False


def test_scan_external_dataset_directory(tmp_path):
    """Test CLI scanner function on a directory of mock images."""
    img_dir = tmp_path / "images"
    img_dir.mkdir()
    for i in range(3):
        img = np.zeros((100, 100), dtype=np.uint8)
        cv2.imwrite(str(img_dir / f"img_{i}.jpg"), img)

    manifest_file = tmp_path / "manifest.json"
    summary = scan_external_dataset_directory(
        dataset_key="pcosgen",
        images_dir=img_dir,
        output_manifest_path=manifest_file,
    )

    assert summary["total_valid_samples"] == 3
    assert summary["dataset_key"] == "pcosgen"
    assert manifest_file.exists()


def test_mmotu_scanner_prefers_binary_mask_variant(tmp_path):
    img_dir = tmp_path / "images"
    mask_dir = tmp_path / "masks"
    img_dir.mkdir()
    mask_dir.mkdir()
    cv2.imwrite(str(img_dir / "1.JPG"), np.full((40, 60), 90, dtype=np.uint8))
    canonical = np.zeros((40, 60), dtype=np.uint8)
    canonical[10:20, 15:25] = 64
    binary = np.zeros((40, 60), dtype=np.uint8)
    binary[10:20, 15:25] = 1
    cv2.imwrite(str(mask_dir / "1.PNG"), canonical)
    cv2.imwrite(str(mask_dir / "1_binary.PNG"), binary)

    summary = scan_external_dataset_directory(
        dataset_key="mmotu",
        images_dir=img_dir,
        masks_dir=mask_dir,
    )

    assert summary["samples"][0]["mask_path"] == str((mask_dir / "1_binary.PNG").resolve())
