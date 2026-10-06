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
