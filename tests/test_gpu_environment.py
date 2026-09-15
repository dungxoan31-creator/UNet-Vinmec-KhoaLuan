"""
Unit test for PyTorch CUDA Environment & Tensor Allocation on RTX 3050.
"""

import pytest
import torch

def test_pytorch_cuda_available():
    assert torch.cuda.is_available(), "PyTorch CUDA must be available on RTX 3050 system."

def test_rtx_3050_device():
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available")
    name = torch.cuda.get_device_name(0)
    assert "RTX 3050" in name or "GeForce" in name, f"Expected RTX 3050, found: {name}"

def test_amp_fp16_allocation():
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available")
    x = torch.randn(2, 1, 512, 512, device="cuda")
    conv = torch.nn.Conv2d(1, 32, kernel_size=3, padding=1).cuda()
    with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
        y = conv(x)
    assert y.shape == (2, 32, 512, 512)
    assert y.is_cuda
