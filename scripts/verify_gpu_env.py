"""
Hardware & GPU Environment Verification for NVIDIA GeForce RTX 3050.
Author: Nguyen Huu Dung (MIS 65A - NEU)
"""

import sys
import torch

def check_env():
    print("=" * 60)
    print("       GPU & PYTORCH CUDA ENVIRONMENT VERIFICATION        ")
    print("=" * 60)
    print(f"[ENV] Python: {sys.version}")
    print(f"[ENV] PyTorch Version: {torch.__version__}")
    cuda_avail = torch.cuda.is_available()
    print(f"[ENV] CUDA Available: {cuda_avail}")
    
    if not cuda_avail:
        print("[ERROR] CUDA is not available. Please verify NVIDIA driver and PyTorch CUDA build.")
        return False
        
    device_count = torch.cuda.device_count()
    device_name = torch.cuda.get_device_name(0)
    capability = torch.cuda.get_device_capability(0)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    
    print(f"[ENV] Device Count: {device_count}")
    print(f"[ENV] Device 0: {device_name}")
    print(f"[ENV] Compute Capability: {capability[0]}.{capability[1]}")
    print(f"[ENV] Total VRAM: {vram_gb:.2f} GB")
    
    # Test tensor allocation on GPU
    try:
        x = torch.randn(2, 1, 512, 512, device="cuda")
        with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
            conv = torch.nn.Conv2d(1, 32, kernel_size=3, padding=1).cuda()
            y = conv(x)
        print(f"[ENV] Tensor Allocation & AMP fp16 Forward: PASS (Output: {y.shape})")
        print("=" * 60)
        return True
    except Exception as e:
        print(f"[ERROR] GPU Execution failed: {e}")
        return False

if __name__ == "__main__":
    success = check_env()
    sys.exit(0 if success else 1)
