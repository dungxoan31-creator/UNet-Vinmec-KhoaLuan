from pathlib import Path

import cv2
import numpy as np

from ai_training.metrics_clinical import compute_dataset_clinical_summary
from evaluation.evaluate_external_vinmec import binary_prediction, select_unseen_pairs


def test_select_unseen_pairs_excludes_renamed_training_image(tmp_path: Path):
    source_images = tmp_path / "source/images"
    source_masks = tmp_path / "source/labels"
    training_images = tmp_path / "training"
    for folder in (source_images, source_masks, training_images):
        folder.mkdir(parents=True)

    seen = np.full((12, 16), 40, dtype=np.uint8)
    unseen = np.full((12, 16), 90, dtype=np.uint8)
    cv2.imwrite(str(training_images / "renamed.JPG"), seen)
    cv2.imwrite(str(source_images / "1.JPG"), seen)
    cv2.imwrite(str(source_images / "2.JPG"), unseen)
    for name in ("1", "2"):
        cv2.imwrite(str(source_masks / f"{name}.PNG"), np.full((12, 16), 255, dtype=np.uint8))

    pairs = select_unseen_pairs(source_images, source_masks, [training_images])

    assert [image.name for image, _ in pairs] == ["2.JPG"]


def test_empty_mask_specificity_is_unavailable_without_empty_cases():
    metrics = compute_dataset_clinical_summary(
        [{"is_empty": False, "dice": 0.5, "iou": 0.333, "recall": 0.5, "precision": 0.5, "specificity": 0.9}]
    )

    assert metrics["normal_cases_count"] == 0
    assert metrics["specificity_normal_cases"] is None


def test_binary_prediction_threshold_controls_false_positives():
    probability = np.array([[0.2, 0.6, 0.9]], dtype=np.float32)
    assert binary_prediction(probability, 0.5).tolist() == [[0, 1, 1]]
    assert binary_prediction(probability, 0.7).tolist() == [[0, 0, 1]]
