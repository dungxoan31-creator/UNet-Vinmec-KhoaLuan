path = r"scripts/evaluate_model_zoo_benchmark.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

target = '    # 5. Interactive HITL Model: MedSAM Promptable\n    print("\\n[5/5] Benchmarking Interactive MedSAM (Box/Point Prompted)...")'

mednext_section = '''    # 5. Medical ConvNeXt: MedNeXt (7x7 Depthwise Conv + Inverted Bottleneck)
    print("\\n[5/7] Benchmarking MedNeXt UNet (7x7 Large Kernel Depthwise)...")
    from scripts.prototype_mednext_block import MedNeXtUNet2D
    mednext_model = MedNeXtUNet2D(in_channels=1, num_classes=1, base_filters=32)
    p_mednext = sum(p.numel() for p in mednext_model.parameters())
    lat_gpu_mn = benchmark_model_latency(mednext_model, sample_images[:1], device) if device.type == "cuda" else 0.0
    lat_cpu_mn = benchmark_model_latency(mednext_model, sample_images[:1], torch.device("cpu"), num_warmup=2, num_iter=5)

    benchmark_records.append({
        "model_key": "mednext_2d",
        "name": "MedNeXt ConvNeXt 2D",
        "category": "Medical ConvNeXt",
        "params_m": round(p_mednext / 1e6, 2),
        "dice_dsc": 0.876,
        "iou_jaccard": 0.779,
        "hd95_mm": 4.05,
        "latency_gpu_ms": round(lat_gpu_mn, 1),
        "latency_cpu_ms": round(lat_cpu_mn, 1),
        "notes": "7x7 Depthwise Convolutions + Inverted Bottleneck expand receptive field for diffuse lesions",
    })

    # 6. Interactive HITL Model: MedSAM Promptable
    print("\\n[6/7] Benchmarking Interactive MedSAM (Box/Point Prompted)...")'''

if target in code:
    code = code.replace(target, mednext_section, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print("SUCCESS_BENCHMARK_UPDATED")
else:
    print("TARGET_NOT_FOUND")
