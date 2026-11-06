"""
Advanced Loss Functions for Ovarian Ultrasound Lesion Segmentation.
Combines Focal Tversky Loss (for boundary & false negative penalty),
Soft Dice Loss (for spatial overlap), and BCEWithLogitsLoss.
"""

import torch
import torch.nn as nn


class SoftDiceLoss(nn.Module):
    def __init__(self, smooth: float = 1.0):
        super().__init__()
        self.smooth = smooth

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probabilities = torch.sigmoid(logits).flatten(1)
        truth = targets.flatten(1)
        intersection = (probabilities * truth).sum(dim=1)
        denominator = probabilities.sum(dim=1) + truth.sum(dim=1)
        dice = (2.0 * intersection + self.smooth) / (denominator + self.smooth)
        return (1.0 - dice).mean()


class FocalTverskyLoss(nn.Module):
    """
    Focal Tversky Loss.
    alpha: Weight for False Positives (FP)
    beta: Weight for False Negatives (FN). Set beta > alpha to penalize missed lesions.
    gamma: Focusing parameter to concentrate on hard-to-segment boundaries.
    """

    def __init__(self, alpha: float = 0.3, beta: float = 0.7, gamma: float = 0.75, smooth: float = 1e-6):
        super().__init__()
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.smooth = smooth

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probabilities = torch.sigmoid(logits).flatten(1)
        truth = targets.flatten(1)
        true_positive = (probabilities * truth).sum(dim=1)
        false_positive = (probabilities * (1.0 - truth)).sum(dim=1)
        false_negative = ((1.0 - probabilities) * truth).sum(dim=1)

        tversky = (true_positive + self.smooth) / (
            true_positive + self.alpha * false_positive + self.beta * false_negative + self.smooth
        )
        focal_tversky = (1.0 - tversky).clamp_min(0.0) ** self.gamma
        return focal_tversky.mean()


class AdvancedHybridLoss(nn.Module):
    """
    Hybrid Clinical Loss for Medical Ultrasound:
    - 0.5 Focal Tversky Loss (beta=0.7 heavily penalizes missing small follicles < 30 mm)
    - 0.3 Soft Dice Loss (global overlap)
    - 0.2 BCEWithLogitsLoss (pixel-level calibration)
    """

    def __init__(
        self,
        tversky_weight: float = 0.5,
        dice_weight: float = 0.3,
        bce_weight: float = 0.2,
        alpha: float = 0.3,
        beta: float = 0.7,
        gamma: float = 0.75,
    ):
        super().__init__()
        self.tversky_weight = tversky_weight
        self.dice_weight = dice_weight
        self.bce_weight = bce_weight
        self.focal_tversky = FocalTverskyLoss(alpha=alpha, beta=beta, gamma=gamma)
        self.soft_dice = SoftDiceLoss()
        self.bce = nn.BCEWithLogitsLoss()

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        loss_ft = self.focal_tversky(logits, targets)
        loss_dice = self.soft_dice(logits, targets)
        loss_bce = self.bce(logits, targets)
        return self.tversky_weight * loss_ft + self.dice_weight * loss_dice + self.bce_weight * loss_bce


class ComboLoss(nn.Module):
    """Preserved baseline Combo Loss (BCE + Dice)."""

    def __init__(self, bce_weight: float = 0.5, dice_weight: float = 0.5):
        super().__init__()
        self.bce = nn.BCEWithLogitsLoss()
        self.dice = SoftDiceLoss()
        self.bce_weight = bce_weight
        self.dice_weight = dice_weight

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        return self.bce_weight * self.bce(logits, targets) + self.dice_weight * self.dice(logits, targets)
