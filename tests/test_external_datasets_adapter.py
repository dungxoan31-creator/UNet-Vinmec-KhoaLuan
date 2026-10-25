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


def test_clinical_guardrail_physiological_vs_neoplasm():
    """
    CRITICAL CLINICAL GUARDRAIL:
    HananSaadat & PCOSGen represent normal physiological follicles and PCOS (<30mm).
    They must be strictly mapped to O-RADS 1 and NOT treated as neoplastic tumor masks.
    """
    pcos = SUPPORTED_EXTERNAL_DATASETS["pcosgen"]
    saadat = SUPPORTED_EXTERNAL_DATASETS["hanan_saadat"]

    assert pcos.default_orads_tier == 1
    assert pcos.clinical_focus == ClinicalCategory.NORMAL_PHYSIOLOGICAL
    assert pcos.has_pixel_masks is False

    assert saadat.default_orads_tier == 1
    assert saadat.clinical_focus == ClinicalCategory.NORMAL_PHYSIOLOGICAL

    # MMOTU and OvaTUS are true neoplasm segmentation datasets
    mmotu = SUPPORTED_EXTERNAL_DATASETS["mmotu"]
    ovatus = SUPPORTED_EXTERNAL_DATASETS["ovatus"]

    assert mmotu.has_pixel_masks is True
    assert mmotu.default_orads_tier >= 2
    assert ovatus.has_pixel_masks is True
    assert ovatus.default_orads_tier >= 2


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
