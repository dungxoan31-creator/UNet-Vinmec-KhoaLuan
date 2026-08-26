"""
Custom Medical Image Segmentation Loss Functions:
- Dice Loss
- Focal Loss
- Combo Loss (Dice + BCE + Focal)
"""

import torch
import torch.nn.functional as F
from torch import nn


class DiceLoss(nn.Module):
    def __init__(self, smooth=1e-6):
        super().__init__()
        self.smooth = smooth

    def forward(self, pred, target):
        # pred: raw logits or sigmoid probabilities (B, 1, H, W)
        if pred.dim() > 2 and (pred.min() < 0 or pred.max() > 1):
            pred = torch.sigmoid(pred)

        pred_flat = pred.contiguous().view(-1)
        target_flat = target.contiguous().view(-1)

        intersection = (pred_flat * target_flat).sum()
        dice = (2.0 * intersection + self.smooth) / (pred_flat.sum() + target_flat.sum() + self.smooth)
        return 1.0 - dice


class FocalLoss(nn.Module):
    def __init__(self, alpha=0.8, gamma=2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, pred, target):
        bce_loss = F.binary_cross_entropy_with_logits(pred, target, reduction="none")
        pt = torch.exp(-bce_loss)
        focal_loss = self.alpha * ((1 - pt) ** self.gamma) * bce_loss
        return focal_loss.mean()


class ComboLoss(nn.Module):
    """
    Combined Loss for Ultrasound Segmentation to handle class imbalance (small lesion vs background)
    and sharp boundary delineation.
    Combo Loss = alpha * DiceLoss + beta * FocalLoss + gamma * BCELoss
    """

    def __init__(self, alpha=0.5, beta=0.3, gamma=0.2, smooth=1e-6):
        super().__init__()
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.dice_loss = DiceLoss(smooth=smooth)
        self.focal_loss = FocalLoss()
        self.bce_loss = nn.BCEWithLogitsLoss()

    def forward(self, pred, target):
        l_dice = self.dice_loss(pred, target)
        l_focal = self.focal_loss(pred, target)
        l_bce = self.bce_loss(pred, target)

        total_loss = (self.alpha * l_dice) + (self.beta * l_focal) + (self.gamma * l_bce)
        return total_loss
