"""
Standard U-Net Baseline Architecture for Medical Ultrasound Lesion Segmentation.
Serves as the rigorous ablation baseline for Attention U-Net.
Author: Nguyen Huu Dung (MIS 65A - NEU)
Reference: Ronneberger et al., "U-Net: Convolutional Networks for Biomedical Image Segmentation" (MICCAI 2015).
"""

import torch
import torch.nn as nn
from backend.models.attention_unet import ConvBlock


class StandardUNet(nn.Module):
    """
    Standard 4-level U-Net architecture with direct skip connections.
    Uses identical ConvBlock, channel dimensions, and depths as AttentionUNet
    to serve as a strict, scientific head-to-head ablation baseline.
    """

    def __init__(self, in_channels: int = 1, num_classes: int = 1, base_filters: int = 32):
        super().__init__()
        self.in_channels = in_channels
        self.num_classes = num_classes
        self.base_filters = base_filters

        # Encoder Levels (Contracting Path)
        self.conv1 = ConvBlock(in_channels, base_filters)         # -> 32
        self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2)

        self.conv2 = ConvBlock(base_filters, base_filters * 2)     # -> 64
        self.pool2 = nn.MaxPool2d(kernel_size=2, stride=2)

        self.conv3 = ConvBlock(base_filters * 2, base_filters * 4) # -> 128
        self.pool3 = nn.MaxPool2d(kernel_size=2, stride=2)

        self.conv4 = ConvBlock(base_filters * 4, base_filters * 8) # -> 256
        self.pool4 = nn.MaxPool2d(kernel_size=2, stride=2)

        # Bottleneck (Bridge)
        self.conv5 = ConvBlock(base_filters * 8, base_filters * 16) # -> 512

        # Decoder Levels (Expansive Path with Direct Skip Connections)
        self.up5 = nn.ConvTranspose2d(base_filters * 16, base_filters * 8, kernel_size=2, stride=2)
        self.dconv5 = ConvBlock(base_filters * 16, base_filters * 8)

        self.up4 = nn.ConvTranspose2d(base_filters * 8, base_filters * 4, kernel_size=2, stride=2)
        self.dconv4 = ConvBlock(base_filters * 8, base_filters * 4)

        self.up3 = nn.ConvTranspose2d(base_filters * 4, base_filters * 2, kernel_size=2, stride=2)
        self.dconv3 = ConvBlock(base_filters * 4, base_filters * 2)

        self.up2 = nn.ConvTranspose2d(base_filters * 2, base_filters, kernel_size=2, stride=2)
        self.dconv2 = ConvBlock(base_filters * 2, base_filters)

        # Final Classifier Head
        self.out_conv = nn.Conv2d(base_filters, num_classes, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Encoder
        x1 = self.conv1(x)       # (B, 32, H, W)
        p1 = self.pool1(x1)      # (B, 32, H/2, W/2)

        x2 = self.conv2(p1)      # (B, 64, H/2, W/2)
        p2 = self.pool2(x2)      # (B, 64, H/4, W/4)

        x3 = self.conv3(p2)      # (B, 128, H/4, W/4)
        p3 = self.pool3(x3)      # (B, 128, H/8, W/8)

        x4 = self.conv4(p3)      # (B, 256, H/8, W/8)
        p4 = self.pool4(x4)      # (B, 256, H/16, W/16)

        # Bottleneck
        x5 = self.conv5(p4)      # (B, 512, H/16, W/16)

        # Decoder with Direct Concatenation
        d5 = self.up5(x5)
        d5 = torch.cat([x4, d5], dim=1)
        d5 = self.dconv5(d5)

        d4 = self.up4(d5)
        d4 = torch.cat([x3, d4], dim=1)
        d4 = self.dconv4(d4)

        d3 = self.up3(d4)
        d3 = torch.cat([x2, d3], dim=1)
        d3 = self.dconv3(d3)

        d2 = self.up2(d3)
        d2 = torch.cat([x1, d2], dim=1)
        d2 = self.dconv2(d2)

        out = self.out_conv(d2)  # Logits: (B, 1, H, W)
        return out
