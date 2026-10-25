"""
Standard U-Net Baseline Training Pipeline with Combo Loss (BCE + Soft Dice).
Training requires source-verified patient IDs and valid, aligned image/mask pairs.
"""

import csv
import hashlib
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import CosineAnnealingLR

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai_training.dataset_loader import OvarianUltrasoundDataset, cv2_imread_unicode, get_train_val_dataloaders
from backend.core.dataset_paths import resolve_dataset_path
from backend.models.unet import StandardUNet


class SoftDiceLoss(nn.Module):
    def __init__(self, smooth=1.0):
        super().__init__()
        self.smooth = smooth

    def forward(self, logits, targets):
        probs = torch.sigmoid(logits)
        num = 2.0 * (probs * targets).sum() + self.smooth
        den = probs.sum() + targets.sum() + self.smooth
        return 1.0 - (num / den)


class ComboLoss(nn.Module):
    def __init__(self, bce_weight=0.5, dice_weight=0.5):
        super().__init__()
        self.bce = nn.BCEWithLogitsLoss()
        self.dice = SoftDiceLoss()
        self.bce_weight = bce_weight
        self.dice_weight = dice_weight

    def forward(self, logits, targets):
        return self.bce_weight * self.bce(logits, targets) + self.dice_weight * self.dice(logits, targets)


def compute_batch_dice(logits, targets, smooth=1e-5):
    return compute_batch_metrics(logits, targets)["dice"].item()


def compute_batch_metrics(logits, targets):
    """Mean per-image segmentation metrics with explicit empty-mask handling."""
    prediction = (torch.sigmoid(logits) > 0.5).flatten(1)
    truth = (targets > 0.5).flatten(1)
    tp = (prediction & truth).sum(dim=1).float()
    predicted = prediction.sum(dim=1).float()
    labeled = truth.sum(dim=1).float()
    union = predicted + labeled - tp
    return {
        "dice": torch.where(predicted + labeled == 0, 1.0, 2 * tp / (predicted + labeled).clamp_min(1)).mean(),
        "iou": torch.where(union == 0, 1.0, tp / union.clamp_min(1)).mean(),
        "recall": torch.where(labeled == 0, 1.0, tp / labeled.clamp_min(1)).mean(),
        "precision": torch.where(predicted == 0, (labeled == 0).float(), tp / predicted.clamp_min(1)).mean(),
    }


def _file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_training_file(splits_dir, recorded, field, csv_path, row_number):
    value = str(recorded or "").strip()
    if not value:
        raise ValueError(f"Missing {field} at {csv_path}:{row_number}")
    path = Path(value)
    if path.is_absolute():
        candidates = (path,)
    else:
        project_root = Path(__file__).resolve().parents[1]
        candidates = (
            resolve_dataset_path(project_root, value),
            *(parent / path for parent in (Path(splits_dir), *Path(splits_dir).parents)),
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ValueError(f"{field} file does not exist at {csv_path}:{row_number}: {value}")


def _resolve_source_artifact(splits_dir, recorded, field, manifest_path):
    value = str(recorded or "").strip()
    if not value:
        raise ValueError(f"Missing {field} in source identity evidence: {manifest_path}")
    path = Path(value)
    if path.is_absolute():
        candidates = (path,)
    else:
        split_dir = Path(splits_dir)
        candidates = (
            split_dir / path,
            *(parent / path for parent in split_dir.parents),
            Path(__file__).resolve().parents[1] / path,
        )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ValueError(f"{field} file does not exist: {value}")


def _load_verified_source_metadata(splits_dir, manifest, manifest_path):
    required_fields = (
        "source_metadata_path",
        "input_metadata_sha256",
        "identity_manifest_path",
        "identity_manifest_sha256",
    )
    if any(not str(manifest.get(field) or "").strip() for field in required_fields):
        raise ValueError(f"Patient-level split source identity evidence is missing: {manifest_path}")

    metadata_path = _resolve_source_artifact(
        splits_dir, manifest["source_metadata_path"], "source_metadata_path", manifest_path
    )
    identity_path = _resolve_source_artifact(
        splits_dir, manifest["identity_manifest_path"], "identity_manifest_path", manifest_path
    )
    metadata_hash = str(manifest["input_metadata_sha256"]).strip().lower()
    identity_hash = str(manifest["identity_manifest_sha256"]).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", metadata_hash) or _file_sha256(metadata_path) != metadata_hash:
        raise ValueError(f"Source metadata SHA-256 does not match the split manifest: {metadata_path}")
    if not re.fullmatch(r"[0-9a-f]{64}", identity_hash) or _file_sha256(identity_path) != identity_hash:
        raise ValueError(f"Identity manifest SHA-256 does not match the split manifest: {identity_path}")

    try:
        identity_manifest = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Source identity evidence is unreadable: {identity_path}") from exc
    if not isinstance(identity_manifest, dict):
        raise ValueError(f"Source identity evidence must be an object: {identity_path}")
    if (
        identity_manifest.get("source_patient_identity_verified") is not True
        or identity_manifest.get("patient_ids_verified") is not True
        or identity_manifest.get("identity_level") != "patient_verified"
        or identity_manifest.get("synthetic_patient_metadata") is True
        or identity_manifest.get("clinical_metadata_is_synthetic") is True
        or identity_manifest.get("metadata_sha256") != metadata_hash
        or not str(identity_manifest.get("identity_source") or "").strip()
        or not str(identity_manifest.get("identity_evidence_reference") or "").strip()
    ):
        raise ValueError(f"Identity manifest does not verify this source metadata: {identity_path}")

    required_columns = {"case_id", "patient_id", "split", "image_path", "mask_path"}
    with metadata_path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or [])
        if not required_columns.issubset(fields):
            raise ValueError(
                f"Source metadata is missing columns: {sorted(required_columns - fields)} at {metadata_path}"
            )
        source_rows = {}
        patient_splits = {}
        for row_number, row in enumerate(reader, start=2):
            case_id = str(row.get("case_id") or "").strip()
            patient_id = str(row.get("patient_id") or "").strip()
            split = str(row.get("split") or "").strip().upper()
            image_path = str(row.get("image_path") or "").strip().replace("\\", "/")
            mask_path = str(row.get("mask_path") or "").strip().replace("\\", "/")
            if not patient_id:
                raise ValueError(f"Source metadata contains empty patient_id at {metadata_path}:{row_number}")
            if not case_id or case_id in source_rows:
                raise ValueError(f"Source metadata case_id is empty or duplicated at {metadata_path}:{row_number}")
            if split not in {"TRAIN", "VAL", "TEST"} or not image_path or not mask_path:
                raise ValueError(f"Source metadata row is incomplete at {metadata_path}:{row_number}")
            prior_split = patient_splits.setdefault(patient_id, split)
            if prior_split != split:
                raise ValueError(f"Patient ID overlap in source metadata: {patient_id}")
            source_rows[case_id] = {
                "patient_id": patient_id,
                "split": split,
                "image_path": image_path,
                "mask_path": mask_path,
            }
    if not source_rows or {row["split"] for row in source_rows.values()} != {"TRAIN", "VAL", "TEST"}:
        raise ValueError(f"Source metadata must include non-empty TRAIN, VAL and TEST partitions: {metadata_path}")
    return source_rows


def load_initial_checkpoint(model, checkpoint_path, device):
    """Load a compatible model state for fine-tuning and return its SHA-256."""
    checkpoint_path = Path(checkpoint_path)
    state_dict = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model.load_state_dict(state_dict, strict=True)
    return _file_sha256(checkpoint_path)


def validate_checkpoint_provenance(checkpoint_path, expected_split_manifest_sha256=None):
    """Accept only a hash-matched checkpoint produced by the verified full trainer."""
    checkpoint_path = Path(checkpoint_path)
    provenance_path = checkpoint_path.parent / "full_unet_run_config.json"
    if not checkpoint_path.is_file() or not provenance_path.is_file():
        raise ValueError("Checkpoint provenance is missing or unverifiable")
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Checkpoint provenance is missing or unverifiable") from exc
    if not isinstance(provenance, dict):
        raise ValueError("Checkpoint provenance is missing or unverifiable")

    recorded_path = provenance.get("checkpoint")
    split_hash = provenance.get("split_manifest_sha256")
    checkpoint_hash = _file_sha256(checkpoint_path)
    if (
        provenance.get("identity_status") != "patient_level_verified"
        or provenance.get("test_split_image_data_used") is not False
        or provenance.get("checkpoint_sha256") != checkpoint_hash
        or not isinstance(recorded_path, str)
        or not Path(recorded_path).is_absolute()
        or Path(recorded_path).resolve() != checkpoint_path.resolve()
        or not isinstance(split_hash, str)
        or not re.fullmatch(r"[0-9a-fA-F]{64}", split_hash)
        or (
            expected_split_manifest_sha256 is not None
            and split_hash.lower() != expected_split_manifest_sha256.lower()
        )
    ):
        raise ValueError("Checkpoint provenance does not verify a patient-level, test-isolated model")
    return checkpoint_hash


def validate_training_split_identity(splits_dir):
    """Require disjoint patient IDs and valid, aligned source pairs before training."""
    splits_dir = Path(splits_dir)
    manifest_path = splits_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    if not isinstance(manifest, dict):
        raise ValueError(f"Split manifest must be a JSON object: {manifest_path}")
    verified = manifest.get("source_patient_identity_verified") is True and (
        manifest.get("patient_ids_verified") is True or manifest.get("identity_level") == "patient_verified"
    )

    if not verified:
        raise ValueError(
            f"Patient-level independence is not verified for {splits_dir}. "
            "Training requires source-verified patient IDs and disjoint patient splits."
        )

    patient_sets = {}
    seen_hashes = {}
    expected_counts = manifest.get("split_counts", {})
    if not isinstance(expected_counts, dict):
        raise ValueError(f"split_counts must be an object: {manifest_path}")
    if verified and any(split not in expected_counts for split in ("train", "val", "test")):
        raise ValueError(f"Verified split manifest requires train/val/test split_counts: {manifest_path}")
    source_rows = _load_verified_source_metadata(splits_dir, manifest, manifest_path)
    seen_case_ids = set()
    for split in ("train", "val", "test"):
        if split in expected_counts and (type(expected_counts[split]) is not int or expected_counts[split] < 1):
            raise ValueError(f"Invalid {split} split_counts value: {manifest_path}")
        path = splits_dir / f"{split}.csv"
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            fields = set(reader.fieldnames or [])
            if "image_sha256" not in fields:
                raise ValueError(f"Split is missing image_sha256 column: {path}")
            if "mask_sha256" not in fields:
                raise ValueError(f"Split is missing mask_sha256 column: {path}")
            if "image_path" not in fields:
                raise ValueError(f"Split is missing image_path column: {path}")
            if "mask_path" not in fields:
                raise ValueError(f"Split is missing mask_path column: {path}")
            if verified and "case_id" not in fields:
                raise ValueError(f"Verified patient split is missing case_id column: {path}")
            if verified and "patient_id" not in fields:
                raise ValueError(f"Verified patient split is missing patient_id column: {path}")
            rows = list(reader)

        if not rows:
            raise ValueError(f"Split contains no samples: {path}")
        if split in expected_counts and len(rows) != expected_counts[split]:
            raise ValueError(f"{split} sample count does not match split manifest: {path}")

        ids = set()
        for row_number, row in enumerate(rows, start=2):
            patient_id = str(row.get("patient_id") or "").strip()
            if verified and not patient_id:
                raise ValueError(f"Verified patient split contains empty patient_id at {path}:{row_number}")
            if patient_id:
                ids.add(patient_id)

            case_id = str(row.get("case_id") or "").strip()
            if not case_id or case_id in seen_case_ids:
                raise ValueError(f"Verified patient split contains an empty or duplicate case_id at {path}:{row_number}")
            seen_case_ids.add(case_id)
            source_row = source_rows.get(case_id)
            if source_row is None:
                raise ValueError(f"case_id does not exist in source metadata at {path}:{row_number}")
            if (
                patient_id != source_row["patient_id"]
                or source_row["split"] != split.upper()
            ):
                raise ValueError(f"patient_id or split does not match source metadata at {path}:{row_number}")
            if (
                str(row.get("image_path") or "").strip().replace("\\", "/") != source_row["image_path"]
                or str(row.get("mask_path") or "").strip().replace("\\", "/") != source_row["mask_path"]
            ):
                raise ValueError(f"Image/mask path does not match source metadata at {path}:{row_number}")

            image_hash = str(row.get("image_sha256") or "").strip().lower()
            if not re.fullmatch(r"[0-9a-f]{64}", image_hash):
                raise ValueError(f"Invalid or missing image SHA-256 at {path}:{row_number}")
            mask_hash = str(row.get("mask_sha256") or "").strip().lower()
            if not re.fullmatch(r"[0-9a-f]{64}", mask_hash):
                raise ValueError(f"Invalid or missing mask SHA-256 at {path}:{row_number}")
            image_path = _resolve_training_file(splits_dir, row.get("image_path"), "image_path", path, row_number)
            mask_path = _resolve_training_file(splits_dir, row.get("mask_path"), "mask_path", path, row_number)
            actual_hash = _file_sha256(image_path)
            if actual_hash != image_hash:
                raise ValueError(f"Image SHA-256 does not match the source file at {path}:{row_number}")
            actual_mask_hash = _file_sha256(mask_path)
            if actual_mask_hash != mask_hash:
                raise ValueError(f"Mask SHA-256 does not match the source file at {path}:{row_number}")
            image = cv2_imread_unicode(str(image_path))
            mask = cv2_imread_unicode(str(mask_path))
            if image is None:
                raise ValueError(f"Source image is unreadable at {path}:{row_number}: {image_path}")
            if mask is None:
                raise ValueError(f"Source mask is unreadable at {path}:{row_number}: {mask_path}")
            if image.ndim != 2 or mask.ndim != 2 or image.shape != mask.shape:
                raise ValueError(
                    f"Image/mask dimensions differ for case {row.get('case_id') or row_number}: "
                    f"image {image.shape}, mask {mask.shape} at {path}:{row_number}"
                )
            if not np.isin(np.unique(mask), (0, 1, 255)).all():
                raise ValueError(f"Source mask contains non-binary pixel values at {path}:{row_number}")
            prior_split = seen_hashes.get(image_hash)
            if prior_split is not None:
                raise ValueError(f"Image SHA-256 overlap between {prior_split} and {split}")
            seen_hashes[image_hash] = split
        patient_sets[split] = ids

    if seen_case_ids != set(source_rows):
        raise ValueError(f"Split case IDs do not exactly match source metadata: {manifest_path}")

    if not verified:
        return "image_level_only"

    for left, right in (("train", "val"), ("train", "test"), ("val", "test")):
        overlap = patient_sets[left] & patient_sets[right]
        if overlap:
            raise ValueError(f"Patient ID overlap between {left} and {right}: {len(overlap)} patient(s)")
    return "patient_level_verified"


def load_verified_train_val_datasets(splits_dir, seed=42):
    """Load only Train and Validation after validating all three split manifests."""
    validate_training_split_identity(splits_dir)
    splits_dir = Path(splits_dir)
    manifest = json.loads((splits_dir / "manifest.json").read_text(encoding="utf-8"))
    train_dataset = OvarianUltrasoundDataset(str(splits_dir / "train.csv"), is_train=True, seed=seed)
    val_dataset = OvarianUltrasoundDataset(str(splits_dir / "val.csv"), is_train=False)
    return train_dataset, val_dataset, manifest


def train_baseline(
    epochs=12,
    batch_size=4,
    lr=1e-3,
    checkpoint_dir="checkpoints",
    splits_dir="ai_training/splits/unified_vinmec_clean_2026-10-06",
    seed=42,
    patience=8,
    initial_checkpoint_path=None,
):
    split_identity_status = validate_training_split_identity(splits_dir)
    verified_initial_checkpoint_sha256 = (
        validate_checkpoint_provenance(
            initial_checkpoint_path,
            expected_split_manifest_sha256=_file_sha256(Path(splits_dir) / "manifest.json"),
        )
        if initial_checkpoint_path is not None
        else None
    )

    print("=" * 70, flush=True)
    print("   BƯỚC 5: HUẤN LUYỆN MÔ HÌNH STANDARD U-NET BASELINE", flush=True)
    print("=" * 70, flush=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[THIẾT BỊ] Huấn luyện trên: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})", flush=True)

    best_checkpoint_path = os.path.join(checkpoint_dir, "baseline_unet_best.pth")
    last_checkpoint_path = os.path.join(checkpoint_dir, "baseline_unet_last.pth")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)

    print(f"[SPLIT] Identity status: {split_identity_status}", flush=True)

    # 1. Dataloaders
    train_loader, val_loader = get_train_val_dataloaders(
        splits_dir=splits_dir, batch_size=batch_size, num_workers=0, seed=seed
    )
    os.makedirs(checkpoint_dir, exist_ok=True)
    print(f"[DỮ LIỆU] Số batch Train: {len(train_loader)} | Số batch Val: {len(val_loader)} (Batch size: {batch_size})", flush=True)

    # 2. Model & Loss & Optimizer
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    initial_checkpoint_sha256 = None
    if initial_checkpoint_path is not None:
        initial_checkpoint_sha256 = load_initial_checkpoint(model, initial_checkpoint_path, device)
        if initial_checkpoint_sha256 != verified_initial_checkpoint_sha256:
            raise ValueError("Initial checkpoint changed after provenance verification")
    criterion = ComboLoss(bce_weight=0.5, dice_weight=0.5)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    scaler = torch.amp.GradScaler('cuda', enabled=(device.type == 'cuda'))

    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[MÔ HÌNH] Standard U-Net (Base filters: 32) | Tổng tham số: {total_params:,} (~7.76M)", flush=True)

    best_val_dice = float("-inf")
    history = []
    epochs_without_improvement = 0

    start_time = time.time()
    for epoch in range(1, epochs + 1):
        # TRAIN
        model.train()
        train_loss = 0.0
        train_dice = 0.0
        train_count = 0
        amp_skipped_steps = 0
        optimizer_steps = 0
        for batch in train_loader:
            images = batch["image"].to(device, non_blocking=True)
            masks = batch["mask"].to(device, non_blocking=True)

            optimizer.zero_grad()
            with torch.amp.autocast('cuda', enabled=(device.type == 'cuda')):
                logits = model(images)
                loss = criterion(logits, masks)

            scaler.scale(loss).backward()
            previous_scale = scaler.get_scale()
            scaler.step(optimizer)
            scaler.update()
            if scaler.get_scale() < previous_scale:
                amp_skipped_steps += 1
            else:
                optimizer_steps += 1

            sample_count = images.shape[0]
            train_loss += loss.item() * sample_count
            train_dice += compute_batch_dice(logits, masks) * sample_count
            train_count += sample_count

        train_loss /= train_count
        train_dice /= train_count

        # VALIDATION
        model.eval()
        val_loss = 0.0
        val_dice = 0.0
        val_iou = 0.0
        val_recall = 0.0
        val_count = 0
        with torch.no_grad():
            for batch in val_loader:
                images = batch["image"].to(device, non_blocking=True)
                masks = batch["mask"].to(device, non_blocking=True)

                with torch.amp.autocast('cuda', enabled=(device.type == 'cuda')):
                    logits = model(images)
                    loss = criterion(logits, masks)

                sample_count = images.shape[0]
                batch_metrics = compute_batch_metrics(logits, masks)
                val_loss += loss.item() * sample_count
                val_dice += batch_metrics["dice"].item() * sample_count
                val_iou += batch_metrics["iou"].item() * sample_count
                val_recall += batch_metrics["recall"].item() * sample_count
                val_count += sample_count

        val_loss /= val_count
        val_dice /= val_count
        val_iou /= val_count
        val_recall /= val_count
        if optimizer_steps:
            scheduler.step()

        # Lưu checkpoint tốt nhất
        is_best = val_dice > best_val_dice
        if is_best:
            best_val_dice = val_dice
            epochs_without_improvement = 0
            torch.save(model.state_dict(), best_checkpoint_path)
        else:
            epochs_without_improvement += 1

        epoch_stat = {
            "epoch": epoch,
            "train_loss": round(train_loss, 4),
            "train_dice": round(train_dice, 4),
            "val_loss": round(val_loss, 4),
            "val_dice": round(val_dice, 4),
            "val_iou": round(val_iou, 4),
            "val_recall": round(val_recall, 4),
            "lr": round(optimizer.param_groups[0]["lr"], 6),
            "is_best": is_best,
            "elapsed_seconds": round(time.time() - start_time, 3),
            "amp_skipped_steps": amp_skipped_steps,
        }
        history.append(epoch_stat)
        torch.save(model.state_dict(), last_checkpoint_path)

        star = " ★ [BEST SAVED]" if is_best else ""
        print(f"Epoch [{epoch:02d}/{epochs:02d}] - Train Loss: {train_loss:.4f} | Train Dice: {train_dice:.4f} || Val Loss: {val_loss:.4f} | Val Dice: {val_dice:.4f}{star}", flush=True)
        if epochs_without_improvement >= patience:
            break

    total_duration = time.time() - start_time
    print("-" * 70, flush=True)
    print(f"[HOÀN TẤT] Thời gian huấn luyện: {total_duration:.2f}s", flush=True)
    print(f"[KẾT QUẢ] Best Validation Dice: {best_val_dice:.4f}", flush=True)
    print(f"[CHECKPOINT] Trọng số tối ưu lưu tại: {best_checkpoint_path}", flush=True)

    # Lưu log
    for filename in ("baseline_training_history.json", "vinmec_unet_best_history.json"):
        with open(os.path.join(checkpoint_dir, filename), "w", encoding="utf-8") as stream:
            json.dump(history, stream, indent=2)
    with (Path(checkpoint_dir) / "run_config.json").open("w", encoding="utf-8") as stream:
        json.dump({
            "seed": seed,
            "batch_size": batch_size,
            "epochs": epochs,
            "patience": patience,
            "learning_rate": lr,
            "loss": "0.5 BCE + 0.5 Dice",
            "optimizer": "AdamW(weight_decay=1e-4)",
            "scheduler": "CosineAnnealingLR(eta_min=1e-6)",
            "architecture": "StandardUNet(base_filters=32)",
            "augmentation": "HorizontalFlip, RandomBrightnessContrast, Affine; train only",
            "split_identity_status": split_identity_status,
            "split_manifest_sha256": _file_sha256(Path(splits_dir) / "manifest.json"),
            "test_split_image_data_used": False,
            "validation_metric": "mean per-image Dice at 512x512, threshold 0.5",
            "device": str(device),
            "gpu_name": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
            "train_samples": len(train_loader.dataset),
            "validation_samples": len(val_loader.dataset),
            "test_samples_held_out": json.loads(
                (Path(splits_dir) / "manifest.json").read_text(encoding="utf-8")
            ).get("split_counts", {}).get("test"),
            "best_epoch": next((row["epoch"] for row in reversed(history) if row["is_best"]), None),
            "best_validation_dice": best_val_dice,
            "duration_seconds": round(total_duration, 3),
            "split_sha256": {
                split: hashlib.sha256((Path(splits_dir) / f"{split}.csv").read_bytes()).hexdigest()
                for split in ("train", "val", "test")
            },
            "checkpoint_best": best_checkpoint_path,
            "checkpoint_last": last_checkpoint_path,
            "checkpoint_best_sha256": _file_sha256(best_checkpoint_path),
            "checkpoint_last_sha256": _file_sha256(last_checkpoint_path),
            "initial_checkpoint": str(initial_checkpoint_path) if initial_checkpoint_path is not None else None,
            "initial_checkpoint_sha256": initial_checkpoint_sha256,
        }, stream, indent=2)

    return best_checkpoint_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train the U-Net baseline on a declared split manifest.")
    parser.add_argument("--splits-dir", default="ai_training/splits/unified_vinmec_clean_2026-10-06")
    args = parser.parse_args()
    train_baseline(epochs=12, batch_size=4, lr=1e-3, splits_dir=args.splits_dir)
