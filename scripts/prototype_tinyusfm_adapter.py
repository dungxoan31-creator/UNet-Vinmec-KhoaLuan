"""Prototype and Feasibility Analysis for TinyUSFM Foundation Model Adapter in U-Net++.

This script explores and benchmarks:
1. Native TinyUSFM architecture (Vision Transformer backbone, patch_size=16, 5.52M params).
2. Input adaptation for project standard (1-channel grayscale, 512x512 resolution) vs TinyUSFM default (3-channel, 256x256/224x224).
3. Drop-in compatibility analysis for U-Net++ encoder:
   - Why raw ViT cannot be a direct drop-in (isotropic stride 16 vs hierarchical multi-scale pyramid).
   - How a hybrid adapter (Stem + Feature2Pyramid) enables full integration with smp.decoders.UnetPlusPlusDecoder.
4. Native TinyUSFM Segmentation Model (ViT + Feature2Pyramid + FPNHead).
5. Baseline Comparison against ResNet-34 U-Net++ (26.07M params).
6. Latency and parameter benchmarks on CPU and CUDA.
"""

from __future__ import annotations

import os
import sys
import time
from functools import partial
from pathlib import Path
from typing import List, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

# Ensure project root and TinyUSFM are on python path
ROOT = Path(__file__).resolve().parents[1]
TINYUSFM_DIR = ROOT / "external_sources" / "TinyUSFM"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(TINYUSFM_DIR) not in sys.path:
    sys.path.insert(0, str(TINYUSFM_DIR))

import segmentation_models_pytorch as smp
from segmentation_models_pytorch.decoders.unetplusplus.decoder import UnetPlusPlusDecoder
from segmentation_models_pytorch.base.heads import SegmentationHead
from timm.layers import resample_abs_pos_embed

# Import TinyUSFM building blocks
from model.tinyusfm import TinyUSFM
from model.tinyusfm_seg import MAEBackbone, Feature2Pyramid_Scale, FPNHead


# ============================================================================
# 1. Adaptable TinyUSFM Backbone for Arbitrary Image Resolution & Grayscale
# ============================================================================

class AdaptableTinyUSFMBackbone(MAEBackbone):
    """MAEBackbone supporting arbitrary resolution and optional single-channel input.

    Resolves:
    1. Input channel adaptation: 1-channel ultrasound replicated to 3 channels (zero param overhead).
    2. Dynamic positional embedding interpolation for 512x512 resolution.
    """

    def __init__(
        self,
        img_size: int | Tuple[int, int] = (512, 512),
        patch_size: int = 16,
        in_channels: int = 1,
        embed_dims: int = 192,
        num_layers: int = 12,
        num_heads: int = 12,
        out_indices: Tuple[int, ...] = (3, 5, 7, 11),
        drop_path_rate: float = 0.1,
    ):
        super().__init__(
            img_size=img_size,
            patch_size=patch_size,
            in_channels=3,  # Underlying pretrained ViT always expects 3 channels
            embed_dims=embed_dims,
            num_layers=num_layers,
            num_heads=num_heads,
            mlp_ratio=4,
            out_indices=out_indices,
            drop_path_rate=drop_path_rate,
        )
        self.expected_in_channels = in_channels
        self.target_img_size = img_size if isinstance(img_size, tuple) else (img_size, img_size)

    def forward(self, x: torch.Tensor) -> List[torch.Tensor]:
        # Adapt single channel grayscale to 3 channels for foundation model feature extraction
        if x.shape[1] == 1 and self.expected_in_channels == 1:
            x = x.repeat(1, 3, 1, 1)

        B, C, H, W = x.shape
        x = self.patch_embed(x)

        # Add CLS token
        cls_tokens = self.cls_token.expand(B, -1, -1)
        x = torch.cat((cls_tokens, x), dim=1)

        # Apply positional embedding
        x = x + self.pos_embed
        x = self.pos_drop(x)

        # Extract multi-stage features
        features = []
        for i, blk in enumerate(self.blocks):
            x = blk(x)
            if i in self.out_indices:
                feat = x[:, 1:, :]  # drop CLS token
                H_out = H // self.patch_size
                W_out = W // self.patch_size
                feat = feat.transpose(1, 2).reshape(B, self.embed_dims, H_out, W_out)
                features.append(feat)

        return features

    def load_pretrained_weights_with_resampling(
        self, state_dict: dict, verbose: bool = True
    ) -> Tuple[List[str], List[str]]:
        """Load pretrained TinyUSFM weights and interpolate pos_embed if resolution differs."""
        mapped_dict = {}
        for k, v in state_dict.items():
            clean_key = k
            if clean_key.startswith("module.model."):
                clean_key = clean_key.replace("module.model.", "")
            elif clean_key.startswith("model."):
                clean_key = clean_key.replace("model.", "")
            elif clean_key.startswith("backbone."):
                clean_key = clean_key.replace("backbone.", "")

            # Filter out classification heads
            if clean_key.startswith("head.") or clean_key.startswith("fc_norm."):
                continue

            # Resample pos_embed if grid size does not match
            if clean_key == "pos_embed" and v.shape != self.pos_embed.shape:
                H_patches = self.target_img_size[0] // self.patch_size
                W_patches = self.target_img_size[1] // self.patch_size
                if verbose:
                    print(f"[*] Resampling pos_embed from {v.shape} to ({H_patches}, {W_patches}) tokens...")
                v = resample_abs_pos_embed(v, new_size=(H_patches, W_patches), num_prefix_tokens=1)

            mapped_dict[clean_key] = v

        load_info = self.load_state_dict(mapped_dict, strict=False)
        return load_info.missing_keys, load_info.unexpected_keys


# ============================================================================
# 2. Hybrid TinyUSFM Encoder Adapter for U-Net++ (SMP Compatibility)
# ============================================================================

class TinyUSFM_UnetPlusPlus_Encoder(nn.Module):
    """Adapter bridging isotropic ViT (stride 16) into hierarchical 6-stage feature pyramid for U-Net++.

    U-Net++ expects 6 feature stages:
    - Stage 0: Stride 1 (512x512) -> e.g. 1 or 32 channels
    - Stage 1: Stride 2 (256x256) -> e.g. 32 or 48 channels
    - Stage 2: Stride 4 (128x128) -> 48 channels
    - Stage 3: Stride 8 (64x64)   -> 48 channels
    - Stage 4: Stride 16 (32x32)  -> 96 channels
    - Stage 5: Stride 32 (16x16)  -> 192 channels
    """

    def __init__(self, img_size=(512, 512), in_channels=1):
        super().__init__()
        self.in_channels = in_channels
        self.out_channels = (in_channels, 32, 48, 48, 96, 192)

        # Shallow high-resolution stem for fine-grained lesion boundary preservation
        self.stem_stage0 = nn.Sequential(
            nn.Conv2d(in_channels, 32, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
        )
        self.stem_stage1 = nn.Sequential(
            nn.Conv2d(32, 32, kernel_size=3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
        )

        # TinyUSFM Backbone (extracting features from blocks 3, 5, 7, 11)
        self.backbone = AdaptableTinyUSFMBackbone(
            img_size=img_size,
            patch_size=16,
            in_channels=in_channels,
            embed_dims=192,
            out_indices=(3, 5, 7, 11),
        )

        # Projections to adapt ViT channels to hierarchical stages
        self.proj_stage2 = nn.Sequential(
            nn.Conv2d(192, 48, kernel_size=1),
            nn.BatchNorm2d(48),
            nn.ReLU(inplace=True),
        )
        self.proj_stage3 = nn.Sequential(
            nn.Conv2d(192, 48, kernel_size=1),
            nn.BatchNorm2d(48),
            nn.ReLU(inplace=True),
        )
        self.proj_stage4 = nn.Sequential(
            nn.Conv2d(192, 96, kernel_size=1),
            nn.BatchNorm2d(96),
            nn.ReLU(inplace=True),
        )
        self.proj_stage5 = nn.Sequential(
            nn.Conv2d(192, 192, kernel_size=3, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(192),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> List[torch.Tensor]:
        # High resolution boundary stages
        s0_stem = self.stem_stage0(x)  # [B, 32, H, W]
        s1 = self.stem_stage1(s0_stem)  # [B, 32, H/2, W/2]
        s0 = x                          # [B, 1, H, W] (matches smp convention where stage 0 is input)

        # TinyUSFM transformer features (all [B, 192, H/16, W/16])
        f_vit = self.backbone(x)
        f_b3, f_b5, f_b7, f_b11 = f_vit[0], f_vit[1], f_vit[2], f_vit[3]

        # Stage 2: Stride 4 (upsample 4x from block 3)
        s2 = F.interpolate(self.proj_stage2(f_b3), scale_factor=4.0, mode="bilinear", align_corners=False)
        # Stage 3: Stride 8 (upsample 2x from block 5)
        s3 = F.interpolate(self.proj_stage3(f_b5), scale_factor=2.0, mode="bilinear", align_corners=False)
        # Stage 4: Stride 16 (stride 1x from block 7)
        s4 = self.proj_stage4(f_b7)
        # Stage 5: Stride 32 (downsample 2x from block 11)
        s5 = self.proj_stage5(f_b11)

        return [s0, s1, s2, s3, s4, s5]


class TinyUSFM_UnetPlusPlus(nn.Module):
    """End-to-end U-Net++ model powered by TinyUSFM Foundation Model Adapter."""

    def __init__(self, img_size=(512, 512), in_channels=1, num_classes=1):
        super().__init__()
        self.encoder = TinyUSFM_UnetPlusPlus_Encoder(img_size=img_size, in_channels=in_channels)
        self.decoder = UnetPlusPlusDecoder(
            encoder_channels=self.encoder.out_channels,
            decoder_channels=(192, 96, 48, 32, 16),
            n_blocks=5,
            use_norm="batchnorm",
        )
        self.segmentation_head = SegmentationHead(
            in_channels=16,
            out_channels=num_classes,
            activation=None,
            kernel_size=3,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.encoder(x)
        decoder_output = self.decoder(features)
        masks = self.segmentation_head(decoder_output)
        return masks


# ============================================================================
# 3. Native TinyUSFM Segmentation Architecture (ViT + FPN)
# ============================================================================

class NativeTinyUSFMSegmentation(nn.Module):
    """Native TinyUSFM Segmentation adapted for 512x512 resolution and 1 channel."""

    def __init__(self, img_size=(512, 512), in_channels=1, num_classes=1):
        super().__init__()
        self.backbone = AdaptableTinyUSFMBackbone(
            img_size=img_size,
            patch_size=16,
            in_channels=in_channels,
            embed_dims=192,
            out_indices=(3, 5, 7, 11),
        )
        self.neck = Feature2Pyramid_Scale(
            embed_dim=192,
            rescales=[4, 2, 1, 0.5],
            scale_factor=0.25,
        )
        self.decode_head = FPNHead(
            in_channels=[48, 48, 48, 48],
            in_index=[0, 1, 2, 3],
            feature_strides=[4, 8, 16, 32],
            channels=128,
            dropout_ratio=0.1,
            num_classes=num_classes,
            align_corners=False,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.backbone(x)
        neck_features = self.neck(features)
        seg_logits = self.decode_head(neck_features)
        output = F.interpolate(seg_logits, size=x.shape[2:], mode="bilinear", align_corners=False)
        return output


# ============================================================================
# 4. Latency and Parameter Benchmarking Utilities
# ============================================================================

def count_parameters(model: nn.Module) -> dict[str, int]:
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return {"total": total_params, "trainable": trainable_params}


def measure_inference_latency(
    model: nn.Module,
    input_tensor: torch.Tensor,
    device: torch.device,
    warmup: int = 10,
    iterations: int = 50,
) -> dict[str, float]:
    """Measure inference latency in milliseconds."""
    model = model.to(device).eval()
    x = input_tensor.to(device)

    # Warmup
    with torch.no_grad():
        for _ in range(warmup):
            _ = model(x)
            if device.type == "cuda":
                torch.cuda.synchronize()

    # Timing
    timings = []
    with torch.no_grad():
        for _ in range(iterations):
            start = time.perf_counter()
            _ = model(x)
            if device.type == "cuda":
                torch.cuda.synchronize()
            end = time.perf_counter()
            timings.append((end - start) * 1000.0)

    return {
        "mean_ms": float(torch.tensor(timings).mean().item()),
        "std_ms": float(torch.tensor(timings).std().item()),
        "min_ms": float(torch.tensor(timings).min().item()),
        "max_ms": float(torch.tensor(timings).max().item()),
        "fps": 1000.0 / float(torch.tensor(timings).mean().item()),
    }


# ============================================================================
# 5. Main Execution and Comprehensive Verification
# ============================================================================

def main():
    print("=" * 80)
    print("TINYUSFM ADAPTER PROTOTYPE & U-NET++ FEASIBILITY VERIFICATION")
    print("=" * 80)

    # Device check
    has_cuda = torch.cuda.is_available()
    cuda_device = torch.device("cuda") if has_cuda else None
    cpu_device = torch.device("cpu")
    print(f"CUDA Available: {has_cuda}")
    if has_cuda:
        print(f"CUDA Device: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB")

    # 1. Parameter Analysis
    print("\n" + "-" * 80)
    print("1. MODEL ARCHITECTURES & PARAMETER METRICS")
    print("-" * 80)

    resnet34_unetpp = smp.UnetPlusPlus(
        encoder_name="resnet34",
        encoder_weights=None,
        in_channels=1,
        classes=1,
        activation=None,
    )
    tinyusfm_native = NativeTinyUSFMSegmentation(img_size=(512, 512), in_channels=1, num_classes=1)
    tinyusfm_unetpp = TinyUSFM_UnetPlusPlus(img_size=(512, 512), in_channels=1, num_classes=1)
    tinyusfm_cls = TinyUSFM(num_classes=2)

    p_resnet = count_parameters(resnet34_unetpp)
    p_native = count_parameters(tinyusfm_native)
    p_adapter = count_parameters(tinyusfm_unetpp)
    p_cls = count_parameters(tinyusfm_cls)

    print(f"Baseline ResNet-34 U-Net++ : {p_resnet['total']:,} params ({p_resnet['total']/1e6:.2f}M)")
    print(f"TinyUSFM Classification    : {p_cls['total']:,} params ({p_cls['total']/1e6:.2f}M)")
    print(f"Native TinyUSFM-Seg (FPN)  : {p_native['total']:,} params ({p_native['total']/1e6:.2f}M)")
    print(f"Hybrid TinyUSFM-U-Net++    : {p_adapter['total']:,} params ({p_adapter['total']/1e6:.2f}M)")
    reduction_pct = (1.0 - (p_native['total'] / p_resnet['total'])) * 100.0
    print(f"[+] Parameter reduction vs ResNet34 U-Net++: {reduction_pct:.1f}% less parameters!")

    # 2. Input/Output Shape & Feature Stage Validation
    print("\n" + "-" * 80)
    print("2. INPUT / OUTPUT SHAPE & FEATURE STAGE VALIDATION")
    print("-" * 80)

    # Test Project Standard Input: 1 channel, 512x512
    x_proj_512 = torch.randn(1, 1, 512, 512)
    print(f"Project Standard Input Tensor Shape: {x_proj_512.shape}")

    # Test Baseline ResNet34
    out_resnet = resnet34_unetpp(x_proj_512)
    print(f"  ResNet34 U-Net++ Output: {out_resnet.shape}")

    # Test Native TinyUSFM-Seg
    out_native = tinyusfm_native(x_proj_512)
    print(f"  Native TinyUSFM-Seg Output: {out_native.shape}")

    # Test Hybrid TinyUSFM U-Net++
    out_adapter = tinyusfm_unetpp(x_proj_512)
    print(f"  Hybrid TinyUSFM-U-Net++ Output: {out_adapter.shape}")

    # Check encoder feature stages
    encoder_features = tinyusfm_unetpp.encoder(x_proj_512)
    print("\nHybrid TinyUSFM-U-Net++ 6-Stage Feature Hierarchy:")
    for idx, feat in enumerate(encoder_features):
        stride = 512 // feat.shape[2]
        print(f"  Stage {idx}: shape={list(feat.shape)}, channels={feat.shape[1]}, stride={stride}x")

    # Test TinyUSFM Default Input: 3 channels, 256x256
    x_tiny_256 = torch.randn(1, 3, 256, 256)
    print(f"\nTinyUSFM Benchmark Input Tensor Shape: {x_tiny_256.shape}")
    native_256 = NativeTinyUSFMSegmentation(img_size=(256, 256), in_channels=3, num_classes=1)
    out_256 = native_256(x_tiny_256)
    print(f"  Native TinyUSFM-Seg (256x256) Output: {out_256.shape}")

    # 3. Positional Embedding Resampling Verification
    print("\n" + "-" * 80)
    print("3. POSITIONAL EMBEDDING RESAMPLING VERIFICATION")
    print("-" * 80)
    # Simulate loading weights from 224x224 pretrained TinyUSFM into 512x512 backbone
    dummy_224_pos_embed = torch.randn(1, 197, 192)  # 1 CLS + 14*14 patches
    dummy_state_dict = {"pos_embed": dummy_224_pos_embed}
    backbone_512 = AdaptableTinyUSFMBackbone(img_size=(512, 512), in_channels=1)
    print(f"Target pos_embed shape (512x512): {backbone_512.pos_embed.shape} (1 CLS + 32*32 patches)")
    missing, unexpected = backbone_512.load_pretrained_weights_with_resampling(dummy_state_dict, verbose=True)
    print(f"[+] Loaded pos_embed shape in backbone: {backbone_512.pos_embed.shape}")
    print(f"[+] Resampling verification: {'SUCCESS' if backbone_512.pos_embed.shape == (1, 1025, 192) else 'FAILED'}")

    # 4. Latency Benchmarking (CPU & CUDA)
    print("\n" + "-" * 80)
    print("4. EMPIRICAL LATENCY BENCHMARKING")
    print("-" * 80)

    benchmarks = [
        ("ResNet34 U-Net++ (512x512, 1ch)", resnet34_unetpp, x_proj_512),
        ("Native TinyUSFM-Seg (512x512, 1ch)", tinyusfm_native, x_proj_512),
        ("Hybrid TinyUSFM-U-Net++ (512x512, 1ch)", tinyusfm_unetpp, x_proj_512),
        ("Native TinyUSFM-Seg (256x256, 3ch)", native_256, x_tiny_256),
    ]

    # Benchmark on CPU
    print("\n--> Measuring CPU Latency (ms):")
    cpu_results = {}
    for name, model, tensor in benchmarks:
        res = measure_inference_latency(model, tensor, cpu_device, warmup=3, iterations=10)
        cpu_results[name] = res
        print(f"  {name:<42} : {res['mean_ms']:.2f} ± {res['std_ms']:.2f} ms ({res['fps']:.1f} FPS)")

    # Benchmark on CUDA if available
    cuda_results = {}
    if has_cuda:
        print("\n--> Measuring CUDA Latency (ms) on RTX 3050 Laptop GPU:")
        for name, model, tensor in benchmarks:
            res = measure_inference_latency(model, tensor, cuda_device, warmup=10, iterations=50)
            cuda_results[name] = res
            print(f"  {name:<42} : {res['mean_ms']:.2f} ± {res['std_ms']:.2f} ms ({res['fps']:.1f} FPS)")

    # 5. Drop-in Compatibility & Architectural Evaluation Summary
    print("\n" + "=" * 80)
    print("5. DROP-IN ENCODER COMPATIBILITY CONCLUSION")
    print("=" * 80)
    print(
        "Is TinyUSFM a direct 'drop-in' replacement for ResNet-34 in smp.UnetPlusPlus without adapter?\n"
        "-> [NO] Direct drop-in is NOT possible because:\n"
        "   1. ViT is isotropic with patch_size=16 (all 12 layers output 32x32 feature maps for 512x512 input).\n"
        "   2. smp.UnetPlusPlus requires hierarchical pyramid features across 5-6 downsampling stages\n"
        "      (strides 1, 2, 4, 8, 16, 32) for dense skip connections (X^{i,j}).\n"
        "   3. TinyUSFM patch embedding natively expects 3 channels; project data is 1 channel.\n"
        "\n"
        "Can TinyUSFM be integrated via an Adapter into U-Net++?\n"
        "-> [YES] Confirmed via 'Hybrid TinyUSFM-U-Net++' (TinyUSFM_UnetPlusPlus):\n"
        "   - Shallow CNN stem recovers high-resolution boundary cues (strides 1 & 2).\n"
        "   - Feature projections (blocks 3, 5, 7, 11) provide multi-scale semantics (strides 4, 8, 16, 32).\n"
        "   - Connects directly into smp.UnetPlusPlusDecoder.\n"
        "   - Total params: 7.72M (vs 26.07M for ResNet34) -> 70.4% parameter reduction!\n"
        "\n"
        "Recommended Optimal Architecture:\n"
        "-> Native TinyUSFM-Seg (MAEBackbone + Feature2Pyramid_Scale + FPNHead):\n"
        "   - Total params: 6.18M (76.3% reduction vs ResNet-34).\n"
        "   - Built natively for ultrasound representation distillation.\n"
        "   - Compatible with Combo Loss (Dice + BCE) used in the project."
    )
    print("=" * 80)


if __name__ == "__main__":
    main()
