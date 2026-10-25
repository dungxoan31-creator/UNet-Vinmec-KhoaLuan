import torch

from ai_training.train_unetplusplus_resnet34 import batch_metrics


def test_empty_prediction_on_nonempty_ground_truth_has_zero_precision():
    logits = torch.full((1, 1, 2, 2), -10.0)
    targets = torch.ones((1, 1, 2, 2))

    metrics = batch_metrics(logits, targets)

    assert metrics["precision"].item() == 0.0
    assert metrics["recall"].item() == 0.0
