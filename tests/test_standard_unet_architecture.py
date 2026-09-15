"""
Unit tests for Standard U-Net Baseline Architecture & Parameter Comparison with Attention U-Net.
"""

import torch
import pytest
from backend.models.unet import StandardUNet
from backend.models.attention_unet import AttentionUNet

def test_standard_unet_forward_shape():
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32)
    model.eval()
    x = torch.randn(2, 1, 512, 512)
    with torch.no_grad():
        out = model(x)
    assert out.shape == (2, 1, 512, 512), f"Expected shape (2, 1, 512, 512), got {out.shape}"

def test_parameter_ablation_comparison():
    unet = StandardUNet(in_channels=1, num_classes=1, base_filters=32)
    attn_unet = AttentionUNet(in_channels=1, num_classes=1, base_filters=32)

    unet_params = sum(p.numel() for p in unet.parameters() if p.requires_grad)
    attn_params = sum(p.numel() for p in attn_unet.parameters() if p.requires_grad)

    print(f"\n[Ablation Parameter Analysis]")
    print(f"Standard U-Net:  {unet_params:,} parameters")
    print(f"Attention U-Net: {attn_params:,} parameters")
    print(f"Difference (AGs): {attn_params - unet_params:,} parameters (+{((attn_params - unet_params)/unet_params)*100:.2f}%)")

    # Standard U-Net MUST have fewer parameters than Attention U-Net due to absence of Attention Gates
    assert unet_params < attn_params
    assert unet_params > 5_000_000, "Base filter 32 U-Net should have > 5M params"
