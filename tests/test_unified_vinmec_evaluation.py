import json

import numpy as np
import pytest
import torch

import scripts.evaluate_unified_vinmec as evaluator
from scripts.evaluate_unified_vinmec import summarize_samples


def test_summary_keeps_empty_masks_separate_from_lesion_segmentation_metrics():
    samples = [
        {"dice": 0.5, "iou": 0.3, "recall": 0.6, "precision": 0.7, "specificity": 0.8, "is_empty": False},
        {"dice": 0.0, "iou": 0.0, "recall": 1.0, "precision": 0.0, "specificity": 0.9, "is_empty": True},
    ]
    summary = summarize_samples(samples)
    assert summary["total_cases_evaluated"] == 2
    assert summary["lesion_cases_count"] == 1
    assert summary["empty_mask_cases_count"] == 1
    assert summary["foreground_dice_mean"] == 0.5
    assert summary["empty_mask_specificity"] == 0.9


def test_evaluation_writes_only_to_requested_output_and_preserves_split_index(tmp_path, monkeypatch):
    root = tmp_path
    split_dir = root / "splits"
    split_dir.mkdir()
    dataset_dir = root / "dataset"
    dataset_dir.mkdir()
    image_path = dataset_dir / "image.png"
    mask_path = dataset_dir / "mask.png"
    import cv2

    cv2.imwrite(str(image_path), np.zeros((16, 16), dtype=np.uint8))
    cv2.imwrite(str(mask_path), np.zeros((16, 16), dtype=np.uint8))
    (split_dir / "test.csv").write_text("case_id,image_path,mask_path\ncase-a,image.png,mask.png\n")
    original_index = "canonical index must remain untouched\n"
    original_samples = (
        "sample_id,case_id,image_path,mask_path,source_datasets,image_sha256\n"
        "case-a,case-a,dataset/image.png,dataset/mask.png,Mock,sha-case-a\n"
    )
    (root / "dataset" / "index.csv").write_text(original_index)
    (split_dir / "all_samples.csv").write_text(original_samples)

    checkpoint_dir = root / "checkpoints" / "candidate"
    checkpoint_dir.mkdir(parents=True)
    checkpoint = checkpoint_dir / "best.pth"
    checkpoint.write_bytes(b"checkpoint")
    (checkpoint_dir / "run_config.json").write_text(json.dumps({"best_epoch": 7}))

    class FakeDataset:
        def __init__(self, *_args, **_kwargs):
            pass

        def __len__(self):
            return 1

        def __getitem__(self, _index):
            return {
                "image": torch.zeros(1, 16, 16),
                "mask": torch.zeros(1, 16, 16),
                "case_id": "case-a",
                "image_path": str(image_path),
            }

    class FakeModel(torch.nn.Module):
        def load_state_dict(self, _state, strict=True):
            assert strict is True

        def forward(self, images):
            return torch.full_like(images, -10.0)

    class FakeLoader:
        def __init__(self, *_args, **_kwargs):
            pass

        def __iter__(self):
            yield {
                "image": torch.zeros(1, 1, 16, 16),
                "mask": torch.zeros(1, 1, 16, 16),
                "case_id": ["case-a"],
            }

    monkeypatch.setattr(evaluator, "OvarianUltrasoundDataset", FakeDataset)
    monkeypatch.setattr(evaluator, "DataLoader", FakeLoader)
    monkeypatch.setattr(evaluator, "StandardUNet", lambda **_kwargs: FakeModel())
    monkeypatch.setattr(torch, "load", lambda *_args, **_kwargs: {})
    output_dir = root / "evaluation" / "milestone_3"

    summary = evaluator.evaluate(root, split_dir, checkpoint, output_dir)

    assert summary["checkpoint"] == "checkpoints/candidate/best.pth"
    assert (output_dir / "predictions" / "case-a.png").is_file()
    assert (output_dir / "test_summary.json").is_file()
    assert (root / "dataset" / "index.csv").read_text() == original_index
    assert (split_dir / "all_samples.csv").read_text() == original_samples


def test_evaluation_refuses_to_overwrite_existing_artifacts(tmp_path):
    output_dir = tmp_path / "evaluation" / "locked"
    output_dir.mkdir(parents=True)
    (output_dir / "test_summary.json").write_text("historical evidence")

    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        evaluator.evaluate(tmp_path, tmp_path / "splits", tmp_path / "candidate.pth", output_dir)
