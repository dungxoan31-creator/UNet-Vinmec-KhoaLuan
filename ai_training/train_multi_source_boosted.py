"""Research-only staged ovarian ultrasound segmentation trainer.

Stage 1 can run from the locally available MMOTU OTU_2d train/validation
pairs. Vinmec co-training and target fine-tuning are refused unless the frozen
Vinmec images and masks are present and pass the repository integrity checks.
No patient-independent or clinical-performance claim is made from image-level
splits.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import random
import shutil
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import segmentation_models_pytorch as smp
import torch
from torch.utils.data import ConcatDataset, DataLoader, WeightedRandomSampler

from ai_training.dataset_loader import OvarianUltrasoundDataset, cv2_imread_unicode
from backend.core.dataset_paths import resolve_dataset_path
from scripts.prepare_mmotu_segmentation_splits import sha256_file

GRAY_MEAN = 0.449
GRAY_STD = 0.226


class AdvancedHybridLoss(torch.nn.Module):
    """0.5 Focal-Tversky + 0.3 soft Dice + 0.2 BCEWithLogits."""

    def __init__(self, alpha: float = 0.3, beta: float = 0.7, gamma: float = 0.75):
        super().__init__()
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.bce = torch.nn.BCEWithLogitsLoss()

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probabilities = torch.sigmoid(logits).flatten(1)
        truth = targets.flatten(1)
        true_positive = (probabilities * truth).sum(dim=1)
        false_positive = (probabilities * (1.0 - truth)).sum(dim=1)
        false_negative = ((1.0 - probabilities) * truth).sum(dim=1)
        tversky = (true_positive + 1e-6) / (
            true_positive + self.alpha * false_positive + self.beta * false_negative + 1e-6
        )
        focal_tversky_loss = ((1.0 - tversky).clamp_min(0.0) ** self.gamma).mean()
        dice = (2.0 * true_positive + 1e-6) / (
            probabilities.sum(dim=1) + truth.sum(dim=1) + 1e-6
        )
        dice_loss = (1.0 - dice).mean()
        bce_loss = self.bce(logits, targets)
        return 0.5 * focal_tversky_loss + 0.3 * dice_loss + 0.2 * bce_loss


def build_model(pretrained: bool = True) -> torch.nn.Module:
    return smp.UnetPlusPlus(
        encoder_name="resnet34",
        encoder_weights="imagenet" if pretrained else None,
        in_channels=1,
        classes=1,
        activation=None,
    )


def normalize_grayscale(images: torch.Tensor) -> torch.Tensor:
    return (images - GRAY_MEAN) / GRAY_STD


def segmentation_metrics(logits: torch.Tensor, targets: torch.Tensor) -> dict[str, list[float]]:
    predicted = torch.sigmoid(logits) >= 0.5
    truth = targets >= 0.5
    predicted = predicted.flatten(1)
    truth = truth.flatten(1)
    tp = (predicted & truth).sum(1).float()
    fp = (predicted & ~truth).sum(1).float()
    fn = (~predicted & truth).sum(1).float()
    tn = (~predicted & ~truth).sum(1).float()
    dice_denominator = 2 * tp + fp + fn
    union = tp + fp + fn
    values = {
        "dice": torch.where(dice_denominator == 0, 1.0, 2 * tp / dice_denominator.clamp_min(1)),
        "iou": torch.where(union == 0, 1.0, tp / union.clamp_min(1)),
        "recall": torch.where(tp + fn == 0, 1.0, tp / (tp + fn).clamp_min(1)),
        "precision": torch.where(tp + fp == 0, (tp + fn == 0).float(), tp / (tp + fp).clamp_min(1)),
        "specificity": torch.where(tn + fp == 0, 1.0, tn / (tn + fp).clamp_min(1)),
    }
    return {key: value.detach().float().cpu().tolist() for key, value in values.items()}


def _project_path(recorded: str) -> Path:
    return resolve_dataset_path(ROOT, recorded).resolve()


def _source_specific_path(recorded: str, source_name: str) -> Path:
    """Resolve without the legacy Vinmec-to-dataset/2d alias fallback."""
    path = Path(recorded)
    candidate = path.resolve() if path.is_absolute() else (ROOT / path).resolve()
    if not candidate.is_file():
        raise FileNotFoundError(
            f"Missing source-specific {source_name} file: {candidate}. "
            "Legacy path aliases are not accepted as source provenance."
        )
    return candidate


def _read_split_records(
    split_dir: Path,
    split_name: str,
    expected_count: int,
    require_hashes: bool = True,
    strict_source: str | None = None,
) -> list[dict[str, str]]:
    import csv

    csv_path = split_dir / f"{split_name}.csv"
    if not csv_path.is_file():
        raise FileNotFoundError(f"Missing {split_name} CSV: {csv_path}")
    with csv_path.open(newline="", encoding="utf-8-sig") as stream:
        records = list(csv.DictReader(stream))
    if len(records) != expected_count or not records:
        raise ValueError(f"{split_name} record count does not match manifest: {len(records)} != {expected_count}")
    image_hashes: set[str] = set()
    for row_number, row in enumerate(records, start=2):
        if strict_source:
            image_path = _source_specific_path(row["image_path"], f"{strict_source} image")
            mask_path = _source_specific_path(row["mask_path"], f"{strict_source} mask")
        else:
            image_path = _project_path(row["image_path"])
            mask_path = _project_path(row["mask_path"])
        if not image_path.is_file() or not mask_path.is_file():
            raise FileNotFoundError(f"Missing image/mask at {csv_path}:{row_number}")
        actual_image_hash = sha256_file(image_path)
        actual_mask_hash = sha256_file(mask_path)
        if require_hashes and (
            actual_image_hash != row.get("image_sha256") or actual_mask_hash != row.get("mask_sha256")
        ):
            raise ValueError(f"Source hash mismatch at {csv_path}:{row_number}")
        row["image_sha256"] = actual_image_hash
        row["mask_sha256"] = actual_mask_hash
        if actual_image_hash in image_hashes:
            raise ValueError(f"Duplicate image content within {split_name}: {row.get('case_id')}")
        image_hashes.add(actual_image_hash)
        image = cv2_imread_unicode(str(image_path))
        mask = cv2_imread_unicode(str(mask_path))
        if image is None or mask is None or image.ndim != 2 or mask.ndim != 2 or image.shape != mask.shape:
            raise ValueError(f"Unreadable or misaligned image/mask at {csv_path}:{row_number}")
        if not set(np.unique(mask).tolist()).issubset({0, 1, 255}):
            raise ValueError(f"Mask is not binary at {csv_path}:{row_number}")
    return records


def validate_mmotu_splits(split_dir: Path) -> dict:
    manifest_path = split_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("dataset") != "MMOTU OTU_2d" or manifest.get("split_level") != "image-level":
        raise ValueError("Stage 1 requires the verified image-level MMOTU OTU_2d split manifest")
    if manifest.get("vinmec_data_used") is not False or manifest.get("patient_level_independence_verified") is not False:
        raise ValueError("MMOTU split provenance has unexpected cohort or identity claims")
    counts = manifest.get("split_counts", {})
    if counts.get("train") != 1000 or counts.get("val") != 469:
        raise ValueError("Expected upstream MMOTU OTU_2d split sizes: 1000 train and 469 validation")
    train_rows = _read_split_records(split_dir, "train", counts["train"])
    val_rows = _read_split_records(split_dir, "val", counts["val"])
    train_hashes = {row["image_sha256"] for row in train_rows}
    val_hashes = {row["image_sha256"] for row in val_rows}
    if train_hashes & val_hashes:
        raise ValueError("Train and validation contain identical image SHA-256 values")
    for split in ("train", "val"):
        source = manifest["source_label_files"][split]
        label_path = ROOT / source["path"]
        if not label_path.is_file() or sha256_file(label_path) != source["sha256"]:
            raise ValueError(f"Source global-category label list changed for {split}")
    return {
        "split_level": "image-level",
        "patient_level_independence_verified": False,
        "train_count": len(train_rows),
        "validation_count": len(val_rows),
        "unique_train_images": len(train_hashes),
        "unique_validation_images": len(val_hashes),
        "cross_split_sha256_overlap": 0,
        "test_split_accessed": False,
        "vinmec_data_used": False,
    }


def run_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    criterion: AdvancedHybridLoss,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
    scaler: torch.amp.GradScaler | None = None,
    tta_horizontal_flip: bool = False,
) -> dict[str, float]:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    sample_count = 0
    metric_values: dict[str, list[float]] = {
        key: [] for key in ("dice", "iou", "recall", "precision", "specificity")
    }
    amp_enabled = device.type == "cuda"
    grad_context = torch.enable_grad if training else torch.no_grad
    with grad_context():
        for batch in loader:
            images = normalize_grayscale(batch["image"].to(device, non_blocking=True))
            masks = batch["mask"].to(device, non_blocking=True)
            if training:
                optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type=device.type, enabled=amp_enabled):
                logits = model(images)
                if tta_horizontal_flip and not training:
                    flipped_logits = model(torch.flip(images, dims=(3,)))
                    logits = (logits + torch.flip(flipped_logits, dims=(3,))) * 0.5
                loss = criterion(logits, masks)
            if training:
                assert scaler is not None
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            batch_size = images.shape[0]
            total_loss += loss.detach().float().item() * batch_size
            sample_count += batch_size
            for key, values in segmentation_metrics(logits.detach(), masks).items():
                metric_values[key].extend(values)
    return {
        "loss": total_loss / max(sample_count, 1),
        **{key: statistics.mean(values) for key, values in metric_values.items()},
    }


def train_stage1(
    split_dir: Path,
    output_dir: Path,
    epochs: int = 10,
    batch_size: int = 2,
    patience: int = 5,
    seed: int = 42,
) -> dict:
    split_dir = split_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    split_integrity = validate_mmotu_splits(split_dir)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    train_dataset = OvarianUltrasoundDataset(str(split_dir / "train.csv"), is_train=True, seed=seed)
    val_dataset = OvarianUltrasoundDataset(str(split_dir / "val.csv"), is_train=False)
    generator = torch.Generator().manual_seed(seed)
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
        generator=generator,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(pretrained=True).to(device)
    criterion = AdvancedHybridLoss().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    scaler = torch.amp.GradScaler(device.type, enabled=device.type == "cuda")
    best_path = output_dir / "boosted_unetplusplus_mmotu_stage1_best.pth"
    last_path = output_dir / "boosted_unetplusplus_mmotu_stage1_last.pth"
    history: list[dict] = []
    best_dice = -1.0
    best_epoch = 0
    no_improvement = 0
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        epoch_started = time.perf_counter()
        train_stats = run_epoch(model, train_loader, criterion, device, optimizer, scaler)
        val_stats = run_epoch(model, val_loader, criterion, device)
        scheduler.step()
        improved = val_stats["dice"] > best_dice + 1e-6
        if improved:
            best_dice = val_stats["dice"]
            best_epoch = epoch
            no_improvement = 0
            torch.save(model.state_dict(), best_path)
        else:
            no_improvement += 1
        torch.save(model.state_dict(), last_path)
        record = {
            "epoch": epoch,
            "train": train_stats,
            "validation": val_stats,
            "learning_rate_next_epoch": optimizer.param_groups[0]["lr"],
            "best_validation_dice_so_far": best_dice,
            "is_best": improved,
            "epoch_seconds": round(time.perf_counter() - epoch_started, 2),
        }
        history.append(record)
        (output_dir / "training_history.json").write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
        print(
            f"stage=1 epoch={epoch:02d}/{epochs} train_loss={train_stats['loss']:.4f} "
            f"train_dice={train_stats['dice']:.4f} val_loss={val_stats['loss']:.4f} "
            f"val_dice={val_stats['dice']:.4f} val_iou={val_stats['iou']:.4f} "
            f"val_recall={val_stats['recall']:.4f} best_val_dice={best_dice:.4f} "
            f"seconds={record['epoch_seconds']:.1f}",
            flush=True,
        )
        if no_improvement >= patience:
            print(f"stage=1 early_stop=validation_dice_plateau patience={patience}", flush=True)
            break

    result = {
        "stage": 1,
        "status": "completed",
        "purpose": "MMOTU 2D research pretraining only",
        "architecture": "U-Net++ with ResNet34 ImageNet encoder",
        "torch_version": torch.__version__,
        "segmentation_models_pytorch_version": importlib.metadata.version("segmentation-models-pytorch"),
        "loss": "0.5 Focal-Tversky(alpha=0.3,beta=0.7,gamma=0.75) + 0.3 SoftDice + 0.2 BCEWithLogits",
        "optimizer": "AdamW(lr=2e-4, weight_decay=1e-4)",
        "scheduler": "CosineAnnealingLR",
        "preprocessing": "grayscale Letterbox 512x512 + CLAHE clipLimit=2.0 + ImageNet grayscale normalization",
        "seed": seed,
        "device": str(device),
        "gpu_name": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
        "batch_size": batch_size,
        "epochs_requested": epochs,
        "epochs_completed": len(history),
        "early_stopping_patience": patience,
        "selection_metric": "mean per-image validation Dice at threshold 0.5",
        "split_integrity": split_integrity,
        "split_dir": str(split_dir),
        "train_csv_sha256": sha256_file(split_dir / "train.csv"),
        "validation_csv_sha256": sha256_file(split_dir / "val.csv"),
        "split_manifest_sha256": sha256_file(split_dir / "manifest.json"),
        "patient_level_independence_verified": False,
        "vinmec_fine_tuned": False,
        "test_split_accessed": False,
        "best_epoch": best_epoch,
        "best_validation": history[best_epoch - 1]["validation"],
        "best_checkpoint": str(best_path),
        "best_checkpoint_sha256": sha256_file(best_path),
        "last_checkpoint": str(last_path),
        "last_checkpoint_sha256": sha256_file(last_path),
        "duration_seconds": round(time.perf_counter() - started, 2),
        "history_path": str(output_dir / "training_history.json"),
        "clinical_use": "not validated; research only; not for diagnosis or treatment decisions",
    }
    (output_dir / "run_config.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return result


def validate_vinmec_train_val(split_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]], dict]:
    """Validate only Vinmec train and validation; never open the test partition."""
    manifest_path = split_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Vinmec split manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    counts = manifest.get("split_counts", {})
    if counts.get("train") != 661 or counts.get("val") != 541:
        raise ValueError("Unexpected frozen Vinmec image-level split counts")
    train_rows = _read_split_records(
        split_dir, "train", counts["train"], require_hashes=False, strict_source="Vinmec"
    )
    val_rows = _read_split_records(
        split_dir, "val", counts["val"], require_hashes=False, strict_source="Vinmec"
    )
    train_hashes = {row["image_sha256"] for row in train_rows}
    val_hashes = {row["image_sha256"] for row in val_rows}
    if train_hashes & val_hashes:
        raise ValueError("Vinmec training and validation have duplicate image SHA-256 values")
    return train_rows, val_rows, {
        "manifest_sha256": sha256_file(manifest_path),
        "train_csv_sha256": sha256_file(split_dir / "train.csv"),
        "validation_csv_sha256": sha256_file(split_dir / "val.csv"),
        "train_count": len(train_rows),
        "validation_count": len(val_rows),
        "train_validation_sha256_overlap": 0,
        "patient_level_independence_verified": False,
        "test_split_accessed": False,
    }


def _make_loaders(
    train_dataset,
    val_dataset,
    batch_size: int,
    seed: int,
    sampler=None,
) -> tuple[DataLoader, DataLoader]:
    generator = torch.Generator().manual_seed(seed)
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=sampler is None,
        sampler=sampler,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
        generator=generator,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=torch.cuda.is_available(),
    )
    return train_loader, val_loader


def _fit_finetuning_stage(
    *,
    stage_number: int,
    stage_name: str,
    model: torch.nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    scheduler,
    epochs: int,
    patience: int,
    device: torch.device,
    output_dir: Path,
    provenance: dict,
    tta_horizontal_flip: bool = False,
    checkpoint_name: str | None = None,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    best_path = output_dir / (checkpoint_name or f"boosted_unetplusplus_stage{stage_number}_best.pth")
    last_path = output_dir / f"boosted_unetplusplus_stage{stage_number}_last.pth"
    criterion = AdvancedHybridLoss().to(device)
    scaler = torch.amp.GradScaler(device.type, enabled=device.type == "cuda")
    history: list[dict] = []
    best_dice = -1.0
    best_epoch = 0
    no_improvement = 0
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        epoch_started = time.perf_counter()
        train_stats = run_epoch(model, train_loader, criterion, device, optimizer, scaler)
        val_stats = run_epoch(
            model,
            val_loader,
            criterion,
            device,
            tta_horizontal_flip=tta_horizontal_flip,
        )
        scheduler.step()
        improved = val_stats["dice"] > best_dice + 1e-6
        if improved:
            best_dice = val_stats["dice"]
            best_epoch = epoch
            no_improvement = 0
            torch.save(model.state_dict(), best_path)
        else:
            no_improvement += 1
        torch.save(model.state_dict(), last_path)
        record = {
            "epoch": epoch,
            "train": train_stats,
            "validation": val_stats,
            "learning_rates_next_epoch": [group["lr"] for group in optimizer.param_groups],
            "best_validation_dice_so_far": best_dice,
            "tta_horizontal_flip": tta_horizontal_flip,
            "is_best": improved,
            "epoch_seconds": round(time.perf_counter() - epoch_started, 2),
        }
        history.append(record)
        (output_dir / "training_history.json").write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
        print(
            f"stage={stage_number} epoch={epoch:02d}/{epochs} train_dice={train_stats['dice']:.4f} "
            f"val_dice={val_stats['dice']:.4f} val_iou={val_stats['iou']:.4f} "
            f"val_recall={val_stats['recall']:.4f} best_val_dice={best_dice:.4f} "
            f"seconds={record['epoch_seconds']:.1f}",
            flush=True,
        )
        if no_improvement >= patience:
            print(f"stage={stage_number} early_stop=validation_dice_plateau patience={patience}", flush=True)
            break

    result = {
        "stage": stage_number,
        "stage_name": stage_name,
        "status": "completed",
        "architecture": "U-Net++ with ResNet34 ImageNet encoder",
        "loss": "0.5 Focal-Tversky(alpha=0.3,beta=0.7,gamma=0.75) + 0.3 SoftDice + 0.2 BCEWithLogits",
        "optimizer": [
            {
                "group": index,
                "initial_learning_rate": group.get("initial_lr", group["lr"]),
                "final_learning_rate": group["lr"],
                "parameter_count": sum(p.numel() for p in group["params"]),
            }
            for index, group in enumerate(optimizer.param_groups)
        ],
        "epochs_requested": epochs,
        "epochs_completed": len(history),
        "early_stopping_patience": patience,
        "selection_metric": "mean per-image validation Dice at threshold 0.5",
        "validation_tta_horizontal_flip": tta_horizontal_flip,
        "device": str(device),
        "gpu_name": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
        "patient_level_independence_verified": False,
        "test_split_accessed": False,
        "best_epoch": best_epoch,
        "best_validation": history[best_epoch - 1]["validation"],
        "best_checkpoint": str(best_path),
        "best_checkpoint_sha256": sha256_file(best_path),
        "last_checkpoint": str(last_path),
        "last_checkpoint_sha256": sha256_file(last_path),
        "duration_seconds": round(time.perf_counter() - started, 2),
        "history_path": str(output_dir / "training_history.json"),
        "provenance": provenance,
        "clinical_use": "not validated; research only; not for diagnosis or treatment decisions",
    }
    (output_dir / "run_config.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2), flush=True)
    return result


def train_stage2(
    stage1_checkpoint: Path,
    mmotu_split_dir: Path,
    vinmec_split_dir: Path,
    output_dir: Path,
    epochs: int = 15,
    batch_size: int = 2,
    patience: int = 5,
    seed: int = 42,
) -> dict:
    mmotu_integrity = validate_mmotu_splits(mmotu_split_dir)
    mmotu_train_rows = _read_split_records(mmotu_split_dir, "train", 1000)
    vinmec_train_rows, vinmec_val_rows, vinmec_integrity = validate_vinmec_train_val(vinmec_split_dir)
    mmotu_train_hashes = {row["image_sha256"] for row in mmotu_train_rows}
    vinmec_train_hashes = {row["image_sha256"] for row in vinmec_train_rows}
    vinmec_val_hashes = {row["image_sha256"] for row in vinmec_val_rows}
    if mmotu_train_hashes & (vinmec_train_hashes | vinmec_val_hashes):
        raise ValueError("MMOTU training images overlap Vinmec train/validation by SHA-256")
    mmotu_train = OvarianUltrasoundDataset(
        str(mmotu_split_dir / "train.csv"),
        is_train=True,
        seed=seed,
        rotation_limit=15,
        elastic_probability=0.2,
    )
    vinmec_train = OvarianUltrasoundDataset(
        str(vinmec_split_dir / "train.csv"),
        is_train=True,
        seed=seed + 1,
        rotation_limit=15,
        elastic_probability=0.2,
    )
    vinmec_val = OvarianUltrasoundDataset(str(vinmec_split_dir / "val.csv"), is_train=False)
    combined = ConcatDataset((mmotu_train, vinmec_train))
    per_source_count = max(len(mmotu_train), len(vinmec_train))
    sample_weights = torch.cat(
        (
            torch.full((len(mmotu_train),), 1.0 / len(mmotu_train), dtype=torch.double),
            torch.full((len(vinmec_train),), 1.0 / len(vinmec_train), dtype=torch.double),
        )
    )
    sampler = WeightedRandomSampler(
        sample_weights,
        num_samples=2 * per_source_count,
        replacement=True,
        generator=torch.Generator().manual_seed(seed),
    )
    train_loader, val_loader = _make_loaders(combined, vinmec_val, batch_size, seed, sampler=sampler)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(pretrained=False).to(device)
    state_dict = torch.load(stage1_checkpoint, map_location=device, weights_only=True)
    model.load_state_dict(state_dict, strict=True)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    return _fit_finetuning_stage(
        stage_number=2,
        stage_name="balanced MMOTU + Vinmec image-level co-training",
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        optimizer=optimizer,
        scheduler=scheduler,
        epochs=epochs,
        patience=patience,
        device=device,
        output_dir=output_dir,
        provenance={
            "stage1_checkpoint_sha256": sha256_file(stage1_checkpoint),
            "mmotu_split_integrity": mmotu_integrity,
            "vinmec_split_integrity": vinmec_integrity,
            "train_source_sampling": "equal expected draws from MMOTU train and Vinmec train",
            "train_augmentation": "horizontal flip, affine rotation +/-15 degrees, mild elastic transform",
            "validation_source": "Vinmec validation only",
            "cross_source_sha256_overlap": 0,
            "test_split_accessed": False,
        },
    )


def train_stage3(
    stage2_checkpoint: Path,
    vinmec_split_dir: Path,
    output_dir: Path,
    epochs: int = 25,
    batch_size: int = 2,
    patience: int = 6,
    seed: int = 42,
) -> dict:
    _, _, vinmec_integrity = validate_vinmec_train_val(vinmec_split_dir)
    vinmec_train = OvarianUltrasoundDataset(
        str(vinmec_split_dir / "train.csv"),
        is_train=True,
        seed=seed,
        rotation_limit=15,
        elastic_probability=0.2,
    )
    vinmec_val = OvarianUltrasoundDataset(str(vinmec_split_dir / "val.csv"), is_train=False)
    train_loader, val_loader = _make_loaders(vinmec_train, vinmec_val, batch_size, seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(pretrained=False).to(device)
    state_dict = torch.load(stage2_checkpoint, map_location=device, weights_only=True)
    model.load_state_dict(state_dict, strict=True)
    optimizer = torch.optim.AdamW(
        (
            {"params": model.encoder.parameters(), "lr": 5e-6},
            {
                "params": list(model.decoder.parameters()) + list(model.segmentation_head.parameters()),
                "lr": 5e-5,
            },
        ),
        weight_decay=1e-4,
    )
    warmup_epochs = 3

    def warmup_cosine(epoch: int) -> float:
        if epoch < warmup_epochs:
            return (epoch + 1) / warmup_epochs
        progress = min(1.0, (epoch - warmup_epochs + 1) / max(epochs - warmup_epochs, 1))
        cosine = 0.5 * (1.0 + np.cos(np.pi * progress))
        return 0.02 + 0.98 * float(cosine)

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, warmup_cosine)
    result = _fit_finetuning_stage(
        stage_number=3,
        stage_name="Vinmec-only target fine-tuning",
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        optimizer=optimizer,
        scheduler=scheduler,
        epochs=epochs,
        patience=patience,
        device=device,
        output_dir=output_dir,
        provenance={
            "stage2_checkpoint_sha256": sha256_file(stage2_checkpoint),
            "vinmec_split_integrity": vinmec_integrity,
            "training_source": "Vinmec train only",
            "train_augmentation": "horizontal flip, affine rotation +/-15 degrees, mild elastic transform",
            "validation_source": "Vinmec validation only",
            "encoder_learning_rate": 5e-6,
            "decoder_learning_rate": 5e-5,
            "warmup_epochs": warmup_epochs,
            "scheduler": "3-epoch linear warmup followed by cosine decay",
            "test_split_accessed": False,
        },
        tta_horizontal_flip=True,
        checkpoint_name="boosted_unetplusplus_multi_source_best.pth",
    )
    requested_checkpoint = ROOT / "checkpoints/boosted_unetplusplus_multi_source_best.pth"
    requested_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(result["best_checkpoint"]), requested_checkpoint)
    result["requested_checkpoint_copy"] = str(requested_checkpoint)
    result["requested_checkpoint_copy_sha256"] = sha256_file(requested_checkpoint)
    (output_dir / "run_config.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("1", "2", "3", "all"), default="all")
    parser.add_argument(
        "--split-dir", type=Path, default=ROOT / "ai_training/splits/mmotu_2d_official_2026-10-27"
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "checkpoints/boosted_unetplusplus_multi_source_2026-10-27",
    )
    parser.add_argument("--stage2-checkpoint", type=Path, default=None)
    parser.add_argument("--stage3-checkpoint", type=Path, default=None)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--skip-stage1", action="store_true", help="Reuse the existing verified Stage 1 checkpoint")
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    args.output_dir = args.output_dir.resolve()
    mmotu_split_dir = args.split_dir.resolve()
    vinmec_split_dir = ROOT / "ai_training/splits/unified_vinmec_clean_2026-10-06"
    stage1_dir = args.output_dir / "stage1_mmotu"
    stage2_dir = args.output_dir / "stage2_co_train"
    stage3_dir = args.output_dir / "stage3_vinmec_finetune"
    stage1_path = stage1_dir / "boosted_unetplusplus_mmotu_stage1_best.pth"
    stage2_path = stage2_dir / "boosted_unetplusplus_stage2_best.pth"
    if args.stage in {"1", "all"}:
        if args.skip_stage1:
            if not stage1_path.is_file() or not (stage1_dir / "run_config.json").is_file():
                raise FileNotFoundError("--skip-stage1 requires a Stage 1 checkpoint and run_config.json")
            print(f"stage=1 status=reused checkpoint={stage1_path}", flush=True)
        else:
            train_stage1(
                mmotu_split_dir,
                stage1_dir,
                epochs=args.epochs or 10,
                batch_size=args.batch_size,
                patience=args.patience,
                seed=args.seed,
            )
    if args.stage in {"2", "3", "all"}:
        try:
            validate_vinmec_train_val(vinmec_split_dir)
        except (FileNotFoundError, ValueError) as exc:
            status = {
                "pipeline_status": "partial" if args.stage == "all" else "blocked",
                "stage_1_status": "completed" if stage1_path.is_file() else "not_run",
                "stage_2_status": "blocked_missing_or_invalid_vinmec_train_val",
                "stage_3_status": "blocked_missing_or_invalid_vinmec_train_val",
                "blocked_reason": str(exc),
                "vinmec_test_split_accessed": False,
            }
            args.output_dir.mkdir(parents=True, exist_ok=True)
            (args.output_dir / "pipeline_status.json").write_text(
                json.dumps(status, indent=2) + "\n", encoding="utf-8"
            )
            print("stage=2 status=blocked reason=missing_or_invalid_vinmec_train_val", flush=True)
            print("stage=3 status=blocked reason=missing_or_invalid_vinmec_train_val", flush=True)
            print(json.dumps(status, indent=2), flush=True)
            if args.stage != "all":
                raise SystemExit(2)
            return
    if args.stage == "2":
        if not stage1_path.is_file():
            raise FileNotFoundError(f"Stage 2 requires Stage 1 checkpoint: {stage1_path}")
        train_stage2(
            stage1_path, mmotu_split_dir, vinmec_split_dir, stage2_dir,
            epochs=args.epochs or 15, batch_size=args.batch_size, patience=args.patience, seed=args.seed,
        )
    elif args.stage == "3":
        checkpoint = args.stage3_checkpoint or args.stage2_checkpoint or stage2_path
        if not checkpoint.is_file():
            raise FileNotFoundError(f"Stage 3 requires Stage 2 checkpoint: {checkpoint}")
        train_stage3(
            checkpoint, vinmec_split_dir, stage3_dir,
            epochs=args.epochs or 25, batch_size=args.batch_size, patience=args.patience, seed=args.seed,
        )
    elif args.stage == "all":
        stage1_result = json.loads((stage1_dir / "run_config.json").read_text(encoding="utf-8"))
        try:
            stage2_result = train_stage2(
                stage1_path, mmotu_split_dir, vinmec_split_dir, stage2_dir,
                epochs=args.epochs or 15, batch_size=args.batch_size, patience=args.patience, seed=args.seed,
            )
            stage3_result = train_stage3(
                Path(stage2_result["best_checkpoint"]), vinmec_split_dir, stage3_dir,
                epochs=args.epochs or 25, batch_size=args.batch_size, patience=args.patience, seed=args.seed,
            )
            status = {
                "pipeline_status": "completed",
                "stages": [stage1_result, stage2_result, stage3_result],
                "vinmec_test_split_accessed": False,
            }
        except (FileNotFoundError, ValueError) as exc:
            status = {
                "pipeline_status": "partial",
                "stage_1_status": "completed",
                "stage_2_status": "blocked_missing_or_invalid_vinmec_train_val",
                "stage_3_status": "blocked_missing_or_invalid_vinmec_train_val",
                "blocked_reason": str(exc),
                "vinmec_test_split_accessed": False,
            }
        (args.output_dir / "pipeline_status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
        print(f"pipeline_status={status['pipeline_status']}", flush=True)
    if args.stage == "1":
        status = {
            "pipeline_status": "stage_1_completed",
            "stage_2_status": "not_run",
            "stage_3_status": "not_run",
            "vinmec_test_split_accessed": False,
        }
        (args.output_dir / "pipeline_status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
