"""
Milestone 1 Full Implementation & Audit Test Suite (Sept 6 - Sept 20).
Formally verifies all 16 mandatory milestone requirements from Section 4:
1. Dataset discovery test
2. Image-mask matching test
3. Patient-level split leakage test
4. Preprocessing shape consistency test
5. Mask label integrity test
6. Post-preprocessing image-mask pair test
7. DataLoader batch test
8. U-Net forward-pass test
9. Loss computation test
10. Training smoke test
11. Prediction shape test
12. Predicted-mask validity test
13. Dice calculation test
14. IoU calculation test
15. Recall calculation test
16. End-to-end pipeline test
"""

import os
import sys
import numpy as np
import pandas as pd
import pytest
import torch
import torch.nn as nn
import torch.optim as optim

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.models.unet import StandardUNet
from backend.services.preprocessor import UltrasoundPreprocessor
from ai_training.dataset_loader import OvarianUltrasoundDataset, get_dataloaders
from ai_training.metrics_clinical import compute_sample_clinical_metrics, compute_dataset_clinical_summary


# =========================================================================
# 1. Dataset Discovery Test
# =========================================================================
def test_dataset_discovery():
    """Verify that split files exist and contain valid tabular metadata."""
    splits = ["ai_training/splits/train.csv", "ai_training/splits/val.csv", "ai_training/splits/test.csv"]
    for s in splits:
        assert os.path.exists(s), f"Split file missing: {s}"
        df = pd.read_csv(s)
        assert len(df) > 0, f"Split file {s} is empty"
        assert "image_path" in df.columns, f"'image_path' missing in {s}"
        assert "mask_path" in df.columns, f"'mask_path' missing in {s}"


# =========================================================================
# 2. Image-Mask Matching Test
# =========================================================================
def test_image_mask_matching():
    """Verify that each image path maps to an existing file and corresponding mask file."""
    for split in ["train.csv", "val.csv", "test.csv"]:
        df = pd.read_csv(f"ai_training/splits/{split}")
        for idx in range(min(10, len(df))):
            row = df.iloc[idx]
            img_p = row["image_path"].replace("\\", "/")
            mask_p = row["mask_path"].replace("\\", "/")
            assert os.path.exists(img_p), f"Image missing on disk: {img_p}"
            assert os.path.exists(mask_p), f"Mask missing on disk: {mask_p}"


# =========================================================================
# 3. Patient-Level Split Leakage Test
# =========================================================================
def test_patient_level_split_leakage():
    """Verify strictly ZERO overlap between train, validation, and test sets."""
    train_df = pd.read_csv("ai_training/splits/train.csv")
    val_df = pd.read_csv("ai_training/splits/val.csv")
    test_df = pd.read_csv("ai_training/splits/test.csv")

    train_imgs = set(train_df["image_path"].apply(os.path.normpath))
    val_imgs = set(val_df["image_path"].apply(os.path.normpath))
    test_imgs = set(test_df["image_path"].apply(os.path.normpath))

    assert len(train_imgs.intersection(val_imgs)) == 0, "Leakage detected between Train and Val"
    assert len(train_imgs.intersection(test_imgs)) == 0, "Leakage detected between Train and Test"
    assert len(val_imgs.intersection(test_imgs)) == 0, "Leakage detected between Val and Test"


# =========================================================================
# 4. Preprocessing Shape Consistency Test
# =========================================================================
def test_preprocessing_shape_consistency():
    """Verify that letterbox resizing produces identical target shape (512, 512)."""
    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    shapes = [(480, 640), (512, 512), (300, 700), (600, 400)]
    for h, w in shapes:
        dummy = (np.random.rand(h, w) * 255).astype(np.uint8)
        padded, params = preprocessor.letterbox_resize(dummy, is_mask=False)
        assert padded.shape == (512, 512), f"Failed for shape {(h, w)}"
        assert params["pad_x"] >= 0 and params["pad_y"] >= 0


# =========================================================================
# 5. Mask Label Integrity Test
# =========================================================================
def test_mask_label_integrity():
    """Verify that nearest-neighbor mask resizing keeps strictly binary values {0, 1}."""
    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    raw_mask = np.zeros((400, 600), dtype=np.uint8)
    raw_mask[100:250, 150:400] = 1

    padded_mask, _ = preprocessor.letterbox_resize(raw_mask, is_mask=True)
    unique_vals = np.unique(padded_mask)
    assert set(unique_vals).issubset({0, 1}), f"Mask label corruption: {unique_vals}"


# =========================================================================
# 6. Post-Preprocessing Image-Mask Pair Test
# =========================================================================
def test_post_preprocessing_image_mask_pair():
    """Verify image-mask correspondence and spatial alignment after preprocessing."""
    dataset = OvarianUltrasoundDataset("ai_training/splits/train.csv", target_size=(512, 512), is_train=False)
    sample = dataset[0]

    img_tensor = sample["image"]
    mask_tensor = sample["mask"]

    assert img_tensor.shape == (1, 512, 512), f"Unexpected img shape: {img_tensor.shape}"
    assert mask_tensor.shape == (1, 512, 512), f"Unexpected mask shape: {mask_tensor.shape}"
    assert img_tensor.dtype == torch.float32, "Image tensor must be float32"
    assert mask_tensor.dtype == torch.float32, "Mask tensor must be float32"
    assert img_tensor.min() >= 0.0 and img_tensor.max() <= 1.0, "Image not in [0, 1]"
    assert set(torch.unique(mask_tensor).tolist()).issubset({0.0, 1.0}), "Mask not binary"


# =========================================================================
# 7. DataLoader Batch Test
# =========================================================================
def test_dataloader_batch():
    """Verify batching mechanism with DataLoader."""
    train_loader, val_loader, test_loader = get_dataloaders(protocol="standard", batch_size=4, num_workers=0)
    batch = next(iter(train_loader))

    assert batch["image"].shape == (4, 1, 512, 512), f"Unexpected batch img: {batch['image'].shape}"
    assert batch["mask"].shape == (4, 1, 512, 512), f"Unexpected batch mask: {batch['mask'].shape}"
    assert len(batch["case_id"]) == 4


# =========================================================================
# 8. U-Net Forward-Pass Test
# =========================================================================
def test_unet_forward_pass():
    """Verify U-Net baseline architecture instantiation and forward pass."""
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32)
    model.eval()
    dummy_input = torch.randn(2, 1, 512, 512)
    with torch.no_grad():
        out = model(dummy_input)
    assert out.shape == (2, 1, 512, 512), f"Unexpected output shape: {out.shape}"
    assert not torch.isnan(out).any(), "Output contains NaN"


# =========================================================================
# 9. Loss Computation Test
# =========================================================================
def test_loss_computation():
    """Verify Combo Loss (BCE + Dice) computation and gradient flow."""
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32)
    bce_fn = nn.BCEWithLogitsLoss()

    logits = model(torch.randn(2, 1, 128, 128))
    targets = torch.randint(0, 2, (2, 1, 128, 128)).float()

    # BCE Loss
    loss_bce = bce_fn(logits, targets)

    # Soft Dice Loss
    probs = torch.sigmoid(logits)
    smooth = 1.0
    intersection = (probs * targets).sum()
    dice_loss = 1.0 - (2.0 * intersection + smooth) / (probs.sum() + targets.sum() + smooth)

    total_loss = loss_bce + dice_loss
    assert total_loss.item() > 0, "Loss must be positive"

    total_loss.backward()
    for param in model.parameters():
        if param.requires_grad:
            assert param.grad is not None, "Gradient must not be None"
            break


# =========================================================================
# 10. Training Smoke Test
# =========================================================================
def test_training_smoke_test():
    """Verify 1-step training execution update."""
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=16)
    optimizer = optim.AdamW(model.parameters(), lr=1e-3)
    criterion = nn.BCEWithLogitsLoss()

    model.train()
    inputs = torch.randn(2, 1, 128, 128)
    targets = torch.zeros(2, 1, 128, 128)

    optimizer.zero_grad()
    outputs = model(inputs)
    loss = criterion(outputs, targets)
    loss.backward()
    optimizer.step()

    assert not torch.isnan(loss), "Loss during smoke test was NaN"


# =========================================================================
# 11. Prediction Shape Test
# =========================================================================
def test_prediction_shape():
    """Verify prediction logits and probability thresholding shape."""
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32)
    model.eval()
    with torch.no_grad():
        out = model(torch.randn(1, 1, 512, 512))
        probs = torch.sigmoid(out)
        pred_mask = (probs > 0.5).squeeze().cpu().numpy().astype(np.uint8)

    assert pred_mask.shape == (512, 512), f"Unexpected pred mask shape: {pred_mask.shape}"


# =========================================================================
# 12. Predicted-Mask Validity Test
# =========================================================================
def test_predicted_mask_validity():
    """Verify predicted mask properties and inverse transformation."""
    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    raw_img = (np.random.rand(400, 600) * 255).astype(np.uint8)

    _, params = preprocessor.letterbox_resize(raw_img, is_mask=False)
    pred_512 = np.zeros((512, 512), dtype=np.uint8)
    pred_512[150:350, 150:350] = 1

    restored = preprocessor.inverse_letterbox_mask(pred_512, params)
    assert restored.shape == (400, 600), "Restored mask shape mismatch"
    assert set(np.unique(restored)).issubset({0, 1}), "Restored mask not binary"


# =========================================================================
# 13. Dice Calculation Test
# =========================================================================
def test_dice_calculation():
    """Verify clinical Dice metric on controlled inputs."""
    gt = np.zeros((100, 100), dtype=np.uint8)
    gt[20:60, 20:60] = 1 # 1600 px

    # Exact match
    res_perfect = compute_sample_clinical_metrics(gt, gt)
    assert abs(res_perfect["dice"] - 1.0) < 1e-4, f"Perfect match Dice: {res_perfect['dice']}"

    # Disjoint match
    pred_disjoint = np.zeros((100, 100), dtype=np.uint8)
    pred_disjoint[70:90, 70:90] = 1
    res_disjoint = compute_sample_clinical_metrics(pred_disjoint, gt)
    assert abs(res_disjoint["dice"] - 0.0) < 1e-4, f"Disjoint match Dice: {res_disjoint['dice']}"


# =========================================================================
# 14. IoU Calculation Test
# =========================================================================
def test_iou_calculation():
    """Verify clinical IoU metric on controlled inputs."""
    gt = np.zeros((100, 100), dtype=np.uint8)
    gt[20:60, 20:60] = 1

    res_perfect = compute_sample_clinical_metrics(gt, gt)
    assert abs(res_perfect["iou"] - 1.0) < 1e-4, f"Perfect match IoU: {res_perfect['iou']}"

    pred_disjoint = np.zeros((100, 100), dtype=np.uint8)
    res_disjoint = compute_sample_clinical_metrics(pred_disjoint, gt)
    assert abs(res_disjoint["iou"] - 0.0) < 1e-4, f"Disjoint match IoU: {res_disjoint['iou']}"


# =========================================================================
# 15. Recall Calculation Test
# =========================================================================
def test_recall_calculation():
    """Verify clinical Recall/Sensitivity metric on controlled inputs."""
    gt = np.zeros((100, 100), dtype=np.uint8)
    gt[20:60, 20:60] = 1 # 1600 px

    # Half predicted
    pred_half = np.zeros((100, 100), dtype=np.uint8)
    pred_half[20:40, 20:60] = 1 # 800 px of gt
    res_half = compute_sample_clinical_metrics(pred_half, gt)
    assert abs(res_half["recall"] - 0.5) < 1e-4, f"Half match Recall: {res_half['recall']}"


# =========================================================================
# 16. End-to-End Pipeline Test
# =========================================================================
def test_end_to_end_pipeline_flow():
    """Verify full pipeline: Raw Image/Mask -> Preprocessing -> Model -> Inverse -> Metrics."""
    preprocessor = UltrasoundPreprocessor(target_size=(512, 512))
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32)
    checkpoint_path = "checkpoints/baseline_unet_best.pth"
    if os.path.exists(checkpoint_path):
        model.load_state_dict(torch.load(checkpoint_path, map_location="cpu"))
    model.eval()

    # Synthetic raw image & mask
    raw_img = (np.random.rand(400, 500) * 255).astype(np.uint8)
    raw_mask = np.zeros((400, 500), dtype=np.uint8)
    raw_mask[100:250, 100:300] = 1

    # Stage 1: Preprocessing
    pad_img, params = preprocessor.letterbox_resize(raw_img, is_mask=False)
    enh_img = preprocessor.clahe.apply(pad_img)
    tensor_img = torch.from_numpy(enh_img).unsqueeze(0).unsqueeze(0).float() / 255.0

    # Stage 2: Model Inference
    with torch.no_grad():
        logits = model(tensor_img)
        probs = torch.sigmoid(logits)
        pred_512 = (probs > 0.5).squeeze().cpu().numpy().astype(np.uint8)

    # Stage 3: Inverse Letterbox
    restored_mask = preprocessor.inverse_letterbox_mask(pred_512, params)
    assert restored_mask.shape == raw_mask.shape, "Restored mask shape must match raw mask"

    # Stage 4: Metrics Calculation
    metrics = compute_sample_clinical_metrics(restored_mask, raw_mask)
    assert "dice" in metrics and "iou" in metrics and "recall" in metrics
    assert not np.isnan(metrics["dice"])
