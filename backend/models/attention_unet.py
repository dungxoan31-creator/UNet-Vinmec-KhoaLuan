"""
Attention U-Net implementation for Medical Ultrasound Image Segmentation.
Author: Nguyen Huu Dung (MIS 65A - NEU)
"""

import torch
import torch.nn.functional as F
from torch import nn


class ConvBlock(nn.Module):
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.conv(x)


class AttentionBlock(nn.Module):
    """
    Attention Gate (AG) mechanism to suppress irrelevant regions (speckle noise/normal tissue)
    and highlight salient lesion features.
    """

    def __init__(self, f_g, f_l, f_int):
        super().__init__()
        self.w_g = nn.Sequential(
            nn.Conv2d(f_g, f_int, kernel_size=1, stride=1, padding=0, bias=True), nn.BatchNorm2d(f_int)
        )

        self.w_x = nn.Sequential(
            nn.Conv2d(f_l, f_int, kernel_size=1, stride=1, padding=0, bias=True), nn.BatchNorm2d(f_int)
        )

        self.psi = nn.Sequential(
            nn.Conv2d(f_int, 1, kernel_size=1, stride=1, padding=0, bias=True), nn.BatchNorm2d(1), nn.Sigmoid()
        )

        self.relu = nn.ReLU(inplace=True)

    def forward(self, g, x):
        g1 = self.w_g(g)
        x1 = self.w_x(x)

        # Align spatial dimensions if needed
        if g1.size()[2:] != x1.size()[2:]:
            g1 = F.interpolate(g1, size=x1.size()[2:], mode="bilinear", align_corners=True)

        psi = self.relu(g1 + x1)
        psi = self.psi(psi)
        return x * psi


class AttentionUNet(nn.Module):
    def __init__(self, in_channels=1, num_classes=1, base_filters=32):
        super().__init__()

        # Encoder (Downsampling)
        self.conv1 = ConvBlock(in_channels, base_filters)
        self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2)

        self.conv2 = ConvBlock(base_filters, base_filters * 2)
        self.pool2 = nn.MaxPool2d(kernel_size=2, stride=2)

        self.conv3 = ConvBlock(base_filters * 2, base_filters * 4)
        self.pool3 = nn.MaxPool2d(kernel_size=2, stride=2)

        self.conv4 = ConvBlock(base_filters * 4, base_filters * 8)
        self.pool4 = nn.MaxPool2d(kernel_size=2, stride=2)

        # Bottleneck
        self.bottleneck = ConvBlock(base_filters * 8, base_filters * 16)

        # Decoder (Upsampling) + Attention Gates
        self.up4 = nn.ConvTranspose2d(base_filters * 16, base_filters * 8, kernel_size=2, stride=2)
        self.att4 = AttentionBlock(f_g=base_filters * 8, f_l=base_filters * 8, f_int=base_filters * 4)
        self.up_conv4 = ConvBlock(base_filters * 16, base_filters * 8)

        self.up3 = nn.ConvTranspose2d(base_filters * 8, base_filters * 4, kernel_size=2, stride=2)
        self.att3 = AttentionBlock(f_g=base_filters * 4, f_l=base_filters * 4, f_int=base_filters * 2)
        self.up_conv3 = ConvBlock(base_filters * 8, base_filters * 4)

        self.up2 = nn.ConvTranspose2d(base_filters * 4, base_filters * 2, kernel_size=2, stride=2)
        self.att2 = AttentionBlock(f_g=base_filters * 2, f_l=base_filters * 2, f_int=base_filters)
        self.up_conv2 = ConvBlock(base_filters * 4, base_filters * 2)

        self.up1 = nn.ConvTranspose2d(base_filters * 2, base_filters, kernel_size=2, stride=2)
        self.att1 = AttentionBlock(f_g=base_filters, f_l=base_filters, f_int=base_filters // 2)
        self.up_conv1 = ConvBlock(base_filters * 2, base_filters)

        # Output Layer
        self.out_conv = nn.Conv2d(base_filters, num_classes, kernel_size=1)

    def forward(self, x):
        # Encoder
        x1 = self.conv1(x)
        p1 = self.pool1(x1)

        x2 = self.conv2(p1)
        p2 = self.pool2(x2)

        x3 = self.conv3(p2)
        p3 = self.pool3(x3)

        x4 = self.conv4(p3)
        p4 = self.pool4(x4)

        # Bottleneck
        b = self.bottleneck(p4)

        # Decoder with Attention
        d4 = self.up4(b)
        x4_att = self.att4(g=d4, x=x4)
        d4 = torch.cat((x4_att, d4), dim=1)
        d4 = self.up_conv4(d4)

        d3 = self.up3(d4)
        x3_att = self.att3(g=d3, x=x3)
        d3 = torch.cat((x3_att, d3), dim=1)
        d3 = self.up_conv3(d3)

        d2 = self.up2(d3)
        x2_att = self.att2(g=d2, x=x2)
        d2 = torch.cat((x2_att, d2), dim=1)
        d2 = self.up_conv2(d2)

        d1 = self.up1(d2)
        x1_att = self.att1(g=d1, x=x1)
        d1 = torch.cat((x1_att, d1), dim=1)
        d1 = self.up_conv1(d1)

        out = self.out_conv(d1)
        return out


def build_model(in_channels=1, num_classes=1, pretrained_weights_path=None):
    model = AttentionUNet(in_channels=in_channels, num_classes=num_classes)
    if pretrained_weights_path:
        model.load_state_dict(torch.load(pretrained_weights_path, map_location="cpu"))
        print(f"Loaded pretrained weights from {pretrained_weights_path}")
    return model
