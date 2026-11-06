"""
Unit tests for ai_training.loss module (AdvancedHybridLoss, FocalTverskyLoss, SoftDiceLoss).
Verifies differentiability, finite gradients, and boundary cases.
"""

import torch

from ai_training.loss import AdvancedHybridLoss, ComboLoss, FocalTverskyLoss, SoftDiceLoss


def test_soft_dice_loss_bounds():
    loss_fn = SoftDiceLoss()
    logits = torch.full((2, 1, 32, 32), 10.0)  # Very confident positive
    targets = torch.ones((2, 1, 32, 32))
    perfect_loss = loss_fn(logits, targets)
    assert 0.0 <= perfect_loss.item() < 0.05

    # Completely wrong prediction
    wrong_loss = loss_fn(-logits, targets)
    assert wrong_loss.item() > 0.90


def test_focal_tversky_loss_penalizes_false_negatives():
    # beta=0.7 penalizes FN more than FP (alpha=0.3)
    loss_fn = FocalTverskyLoss(alpha=0.3, beta=0.7, gamma=0.75)

    # Partial overlap scenario:
    # Case 1: Has False Negatives (Target has 20 positive pixels, model predicts 10)
    targets_fn = torch.zeros((1, 1, 16, 16))
    targets_fn[:, :, 0:4, 0:5] = 1.0  # 20 target pixels
    logits_fn = torch.full((1, 1, 16, 16), -5.0)
    logits_fn[:, :, 0:2, 0:5] = 5.0   # 10 predicted pixels (10 TP, 10 FN, 0 FP)

    # Case 2: Has False Positives (Target has 10 positive pixels, model predicts 20)
    targets_fp = torch.zeros((1, 1, 16, 16))
    targets_fp[:, :, 0:2, 0:5] = 1.0  # 10 target pixels
    logits_fp = torch.full((1, 1, 16, 16), -5.0)
    logits_fp[:, :, 0:4, 0:5] = 5.0   # 20 predicted pixels (10 TP, 0 FN, 10 FP)

    loss_fn_val = loss_fn(logits_fn, targets_fn)
    loss_fp_val = loss_fn(logits_fp, targets_fp)

    assert torch.isfinite(loss_fn_val)
    assert torch.isfinite(loss_fp_val)
    # Because beta=0.7 > alpha=0.3, the penalty for FN is strictly higher than for FP!
    assert loss_fn_val.item() > loss_fp_val.item()


def test_advanced_hybrid_loss_differentiability():
    loss_fn = AdvancedHybridLoss()
    logits = torch.randn((2, 1, 64, 64), requires_grad=True)
    targets = torch.randint(0, 2, (2, 1, 64, 64)).float()

    loss = loss_fn(logits, targets)
    assert torch.isfinite(loss)
    loss.backward()

    assert logits.grad is not None
    assert torch.isfinite(logits.grad).all()


def test_combo_loss_backward_compatibility():
    loss_fn = ComboLoss(bce_weight=0.5, dice_weight=0.5)
    logits = torch.randn((2, 1, 32, 32), requires_grad=True)
    targets = torch.randint(0, 2, (2, 1, 32, 32)).float()

    loss = loss_fn(logits, targets)
    assert torch.isfinite(loss)
    loss.backward()
    assert logits.grad is not None
