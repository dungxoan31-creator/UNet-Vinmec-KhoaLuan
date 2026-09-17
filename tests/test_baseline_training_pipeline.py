"""
Unit tests for Task 6: Baseline Training Pipeline with AMP fp16 and Hybrid Loss.
"""

import os
import sys
import torch
import torch.nn as nn
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models.unet import StandardUNet


def test_training_step_amp():
    """Verify single forward-backward training step using PyTorch AMP fp16."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))

    x = torch.randn(2, 1, 512, 512, device=device)
    y = torch.randint(0, 2, (2, 1, 512, 512), dtype=torch.float32, device=device)

    optimizer.zero_grad()
    with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
        out = model(x)
        bce = nn.functional.binary_cross_entropy_with_logits(out, y)
        probs = torch.sigmoid(out)
        dice_loss = 1.0 - (2.0 * (probs * y).sum() + 1e-6) / (probs.sum() + y.sum() + 1e-6)
        loss = 0.5 * bce + 0.5 * dice_loss

    scaler.scale(loss).backward()
    scaler.step(optimizer)
    scaler.update()

    assert not torch.isnan(loss), "Training loss returned NaN!"
    assert loss.item() > 0, "Loss must be positive"


def test_checkpoint_saving_and_loading(tmp_path):
    """Verify model state_dict can be saved and restored correctly."""
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32)
    save_file = tmp_path / "test_unet.pth"

    torch.save(model.state_dict(), save_file)
    assert save_file.exists()

    new_model = StandardUNet(in_channels=1, num_classes=1, base_filters=32)
    new_model.load_state_dict(torch.load(save_file, weights_only=True))

    x = torch.randn(1, 1, 512, 512)
    with torch.no_grad():
        out1 = model(x)
        out2 = new_model(x)

    assert torch.allclose(out1, out2, atol=1e-5), "Reloaded model outputs differ from original!"
