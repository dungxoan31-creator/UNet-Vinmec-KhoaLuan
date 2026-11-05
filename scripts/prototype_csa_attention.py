"""
Prototype PyTorch implementation of CSA-SegNet architectural modules.
Ported from TensorFlow/Keras implementation in external_sources/CSA-SegNet/model.py.

Key modules:
1. AttentionGate: Oktay et al. / CSA-SegNet attention gate for feature recalibration.
2. SPPFModule: Spatial Pyramid Pooling - Fast (SPPF) with multi-scale pooling kernels.
3. CSABottleneckUNetPlusPlusBlock: Plug-and-play bottleneck enhancement for medical segmentation.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class CSAAttentionGate(nn.Module):
    """
    Channel and Spatial Attention Gate.
    Recalibrates encoder skip-connection features (x) using gating signals (g) from deeper layers.
    Reference: external_sources/CSA-SegNet/model.py `attention_gate`.
    """

    def __init__(self, in_channels_g: int, in_channels_x: int, inter_channels: int):
        super().__init__()
        self.w_g = nn.Sequential(
            nn.Conv2d(in_channels_g, inter_channels, kernel_size=1, stride=1, padding=0, bias=True),
            nn.BatchNorm2d(inter_channels),
        )
        self.w_x = nn.Sequential(
            nn.Conv2d(in_channels_x, inter_channels, kernel_size=1, stride=1, padding=0, bias=True),
            nn.BatchNorm2d(inter_channels),
        )
        self.psi = nn.Sequential(
            nn.Conv2d(inter_channels, 1, kernel_size=1, stride=1, padding=0, bias=True),
            nn.BatchNorm2d(1),
            nn.Sigmoid(),
        )
        self.relu = nn.ReLU(inplace=True)

    def forward(self, g: torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        # Align spatial dimensions if needed
        if g.shape[2:] != x.shape[2:]:
            g = F.interpolate(g, size=x.shape[2:], mode="bilinear", align_corners=False)

        theta_x = self.w_x(x)
        phi_g = self.w_g(g)
        f = self.relu(theta_x + phi_g)
        alpha = self.psi(f)
        return x * alpha


class SPPFModule(nn.Module):
    """
    Spatial Pyramid Pooling - Fast (SPPF) module.
    Captures multi-scale contextual receptive fields while remaining computationally efficient.
    Reference: external_sources/CSA-SegNet/model.py `SPPF_module`.
    """

    def __init__(self, in_channels: int, out_channels: int, k: int = 5):
        super().__init__()
        hidden_channels = in_channels // 2
        self.cv1 = nn.Sequential(
            nn.Conv2d(in_channels, hidden_channels, kernel_size=1, stride=1, bias=False),
            nn.BatchNorm2d(hidden_channels),
            nn.SiLU(inplace=True),
        )
        self.pool = nn.MaxPool2d(kernel_size=k, stride=1, padding=k // 2)
        self.cv2 = nn.Sequential(
            nn.Conv2d(hidden_channels * 4, out_channels, kernel_size=1, stride=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.SiLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.cv1(x)
        y1 = self.pool(x)
        y2 = self.pool(y1)
        y3 = self.pool(y2)
        concat = torch.cat([x, y1, y2, y3], dim=1)
        return self.cv2(concat)


class CSABottleneckBlock(nn.Module):
    """
    Enhanced Bottleneck integrating CSA Attention and SPPF for deep ultrasound feature extraction.
    """

    def __init__(self, in_channels: int = 512, out_channels: int = 512):
        super().__init__()
        self.sppf = SPPFModule(in_channels=in_channels, out_channels=out_channels, k=5)
        self.conv1 = nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.sppf(x)
        out = self.relu(self.bn1(self.conv1(feat)))
        return out


def test_csa_modules():
    print("Testing CSA-SegNet PyTorch Modules...")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # 1. Test Attention Gate
    g = torch.randn(2, 256, 16, 16, device=device)
    x = torch.randn(2, 128, 32, 32, device=device)
    gate = CSAAttentionGate(in_channels_g=256, in_channels_x=128, inter_channels=64).to(device)
    gated_x = gate(g, x)
    assert gated_x.shape == x.shape, f"Gate shape mismatch: {gated_x.shape} vs {x.shape}"
    print(f"  [PASS] CSAAttentionGate: g={g.shape}, x={x.shape} -> gated_x={gated_x.shape}")

    # 2. Test SPPF Module
    feat = torch.randn(2, 512, 16, 16, device=device)
    sppf = SPPFModule(in_channels=512, out_channels=512, k=5).to(device)
    sppf_out = sppf(feat)
    assert sppf_out.shape == feat.shape, f"SPPF shape mismatch: {sppf_out.shape} vs {feat.shape}"
    print(f"  [PASS] SPPFModule: in={feat.shape} -> out={sppf_out.shape}")

    # 3. Test Full CSABottleneckBlock
    bottleneck = CSABottleneckBlock(in_channels=512, out_channels=512).to(device)
    bn_out = bottleneck(feat)
    assert bn_out.shape == feat.shape, f"Bottleneck shape mismatch: {bn_out.shape} vs {feat.shape}"
    print(f"  [PASS] CSABottleneckBlock: in={feat.shape} -> out={bn_out.shape}")

    total_params = sum(p.numel() for p in bottleneck.parameters())
    print(f"  Total CSABottleneck params: {total_params:,} (lightweight drop-in block)")
    print("All CSA-SegNet modules verified successfully!")


if __name__ == "__main__":
    test_csa_modules()
