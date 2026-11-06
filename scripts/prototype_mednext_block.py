"""
MedNeXt 2D Convolutional Inverted Bottleneck Block & Architecture Adapter
Ported from MIC-DKFZ/MedNeXt (Apache-2.0)
Specialized for 2D Ultrasound Ovarian Lesion Segmentation with Large Kernel (7x7) Depthwise Convolutions.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class MedNeXtBlock2D(nn.Module):
    """
    2D ConvNeXt-style block for medical imaging:
    1. 7x7 Depthwise Convolution (large receptive field for acoustic texture)
    2. GroupNorm (channel-wise normalized)
    3. 1x1 Inverted Bottleneck Expansion (expansion ratio exp_r=4)
    4. GELU Activation
    5. Global Response Normalization (GRN) to prevent feature collapse
    6. 1x1 Compression & Residual Connection
    """

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        exp_r: int = 4,
        kernel_size: int = 7,
        do_res: bool = True,
        grn: bool = True,
    ):
        super().__init__()
        self.do_res = do_res and (in_channels == out_channels)
        self.in_channels = in_channels
        self.out_channels = out_channels

        # 1. Depthwise Convolution with Large 7x7 Kernel
        self.dw_conv = nn.Conv2d(
            in_channels=in_channels,
            out_channels=in_channels,
            kernel_size=kernel_size,
            stride=1,
            padding=kernel_size // 2,
            groups=in_channels,
            bias=True,
        )

        # 2. Group Normalization
        self.norm = nn.GroupNorm(num_groups=in_channels, num_channels=in_channels)

        # 3. Expansion Conv 1x1
        expanded_dim = exp_r * in_channels
        self.pw_conv1 = nn.Conv2d(in_channels, expanded_dim, kernel_size=1, stride=1, padding=0)
        self.act = nn.GELU()

        # 4. Global Response Normalization (GRN)
        self.grn = grn
        if grn:
            self.grn_gamma = nn.Parameter(torch.zeros(1, expanded_dim, 1, 1), requires_grad=True)
            self.grn_beta = nn.Parameter(torch.zeros(1, expanded_dim, 1, 1), requires_grad=True)

        # 5. Compression Conv 1x1
        self.pw_conv2 = nn.Conv2d(expanded_dim, out_channels, kernel_size=1, stride=1, padding=0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        x1 = self.dw_conv(x)
        x1 = self.norm(x1)
        x1 = self.pw_conv1(x1)
        x1 = self.act(x1)

        if self.grn:
            gx = torch.norm(x1, p=2, dim=(-2, -1), keepdim=True)
            nx = gx / (gx.mean(dim=1, keepdim=True) + 1e-6)
            x1 = self.grn_gamma * (x1 * nx) + self.grn_beta + x1

        x1 = self.pw_conv2(x1)
        if self.do_res:
            x1 = residual + x1
        return x1


class MedNeXtUNet2D(nn.Module):
    """
    U-Net architecture with MedNeXt Large Kernel (7x7) Inverted Bottleneck blocks.
    Receptive field is expanded to capture diffuse ovarian margins and subtle acoustic shadowing.
    """

    def __init__(self, in_channels: int = 1, num_classes: int = 1, base_filters: int = 32):
        super().__init__()
        # Encoder
        self.init_conv = nn.Sequential(
            nn.Conv2d(in_channels, base_filters, kernel_size=3, padding=1),
            nn.BatchNorm2d(base_filters),
            nn.ReLU(inplace=True),
        )
        self.enc1 = MedNeXtBlock2D(base_filters, base_filters, kernel_size=7)
        self.down1 = nn.Conv2d(base_filters, base_filters * 2, kernel_size=2, stride=2)

        self.enc2 = MedNeXtBlock2D(base_filters * 2, base_filters * 2, kernel_size=7)
        self.down2 = nn.Conv2d(base_filters * 2, base_filters * 4, kernel_size=2, stride=2)

        self.enc3 = MedNeXtBlock2D(base_filters * 4, base_filters * 4, kernel_size=7)
        self.down3 = nn.Conv2d(base_filters * 4, base_filters * 8, kernel_size=2, stride=2)

        # Bottleneck with MedNeXt
        self.bottleneck = nn.Sequential(
            MedNeXtBlock2D(base_filters * 8, base_filters * 8, kernel_size=7),
            MedNeXtBlock2D(base_filters * 8, base_filters * 8, kernel_size=7),
        )

        # Decoder
        self.up3 = nn.ConvTranspose2d(base_filters * 8, base_filters * 4, kernel_size=2, stride=2)
        self.dec3 = MedNeXtBlock2D(base_filters * 8, base_filters * 4, kernel_size=7, do_res=False)

        self.up2 = nn.ConvTranspose2d(base_filters * 4, base_filters * 2, kernel_size=2, stride=2)
        self.dec2 = MedNeXtBlock2D(base_filters * 4, base_filters * 2, kernel_size=7, do_res=False)

        self.up1 = nn.ConvTranspose2d(base_filters * 2, base_filters, kernel_size=2, stride=2)
        self.dec1 = MedNeXtBlock2D(base_filters * 2, base_filters, kernel_size=7, do_res=False)

        self.head = nn.Conv2d(base_filters, num_classes, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e0 = self.init_conv(x)
        e1 = self.enc1(e0)
        d1 = self.down1(e1)

        e2 = self.enc2(d1)
        d2 = self.down2(e2)

        e3 = self.enc3(d2)
        d3 = self.down3(e3)

        b = self.bottleneck(d3)

        u3 = self.up3(b)
        c3 = torch.cat([u3, e3], dim=1)
        d_out3 = self.dec3(c3)

        u2 = self.up2(d_out3)
        c2 = torch.cat([u2, e2], dim=1)
        d_out2 = self.dec2(c2)

        u1 = self.up1(d_out2)
        c1 = torch.cat([u1, e1], dim=1)
        d_out1 = self.dec1(c1)

        logits = self.head(d_out1)
        return logits


if __name__ == "__main__":
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Testing MedNeXt2D on {device}...")
    model = MedNeXtUNet2D(in_channels=1, num_classes=1, base_filters=32).to(device)
    dummy_input = torch.randn(2, 1, 512, 512, device=device)
    with torch.no_grad():
        out = model(dummy_input)
    print(f"MedNeXtUNet2D output shape: {out.shape}")
    num_params = sum(p.numel() for p in model.parameters())
    print(f"Total MedNeXt parameters: {num_params:,}")
    assert out.shape == (2, 1, 512, 512)
    print("MedNeXt verification SUCCESS!")
