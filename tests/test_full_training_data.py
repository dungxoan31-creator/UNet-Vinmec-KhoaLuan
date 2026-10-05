from pathlib import Path

import cv2
import numpy as np
import pytest

from ai_training.train_full_unet import discover_pairs


def test_discover_pairs_uses_every_available_subset(tmp_path: Path):
    groups = (
        ("Vinmec_2D/train/train_image", "Vinmec_2D/train/train_label/label"),
        ("Vinmec_2D/test/image", "Vinmec_2D/test/label/black_write"),
        ("Vinmec_CEUS/image", "Vinmec_CEUS/label"),
    )
    for index, (image_dir, mask_dir) in enumerate(groups):
        image_path = tmp_path / image_dir / f"{index}.JPG"
        mask_path = tmp_path / mask_dir / f"{index}.PNG"
        image_path.parent.mkdir(parents=True)
        mask_path.parent.mkdir(parents=True)
        cv2.imwrite(str(image_path), np.zeros((8, 12), dtype=np.uint8))
        cv2.imwrite(str(mask_path), np.full((8, 12), 255, dtype=np.uint8))

    pairs = discover_pairs(tmp_path)

    assert len(pairs) == 3
    assert {item[0] for item in pairs} == {"Vinmec_2D_train_0", "Vinmec_2D_test_1", "Vinmec_CEUS_2"}


def test_discover_pairs_rejects_missing_mask(tmp_path: Path):
    image_path = tmp_path / "Vinmec_2D/train/train_image/1.JPG"
    image_path.parent.mkdir(parents=True)
    cv2.imwrite(str(image_path), np.zeros((8, 12), dtype=np.uint8))

    with pytest.raises(ValueError, match="mask"):
        discover_pairs(tmp_path)
