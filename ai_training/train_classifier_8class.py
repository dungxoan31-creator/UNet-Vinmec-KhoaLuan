"""Train an image-level MMOTU 8-class research classifier.

The labels are the official MMOTU global category annotations. They are image-level
reference labels, not a patient-level diagnosis or an independently verified
histopathology endpoint. The official MMOTU train/val split is retained; patient
identities are unavailable, so results must not be described as patient-independent.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import f1_score
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision.models import ResNet34_Weights, resnet34

from ai_training.mmotu_label_schema import MMOTU_8_CLASSES

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_class_labels(labels_path: Path, images_dir: Path) -> list[dict[str, Any]]:
    """Read official ``filename class_id`` labels and bind each label to an image."""
    labels_path = Path(labels_path)
    images_dir = Path(images_dir)
    if not labels_path.is_file():
        raise FileNotFoundError(f"MMOTU label file not found: {labels_path}")
    if not images_dir.is_dir():
        raise FileNotFoundError(f"MMOTU image directory not found: {images_dir}")

    records: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for line_number, line in enumerate(labels_path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split()
        if len(fields) != 2:
            raise ValueError(f"Expected '<filename> <class_id>' at {labels_path}:{line_number}")
        filename, raw_class_id = fields
        if Path(filename).name != filename or filename in {".", ".."}:
            raise ValueError(f"Label filename must be a simple file name at {labels_path}:{line_number}")
        try:
            class_id = int(raw_class_id)
        except ValueError as exc:
            raise ValueError(f"Invalid class ID at {labels_path}:{line_number}: {raw_class_id}") from exc
        if not 0 <= class_id < len(MMOTU_8_CLASSES):
            raise ValueError(f"Class ID out of range at {labels_path}:{line_number}: {class_id}")
        normalized_name = filename.casefold()
        if normalized_name in seen_names:
            raise ValueError(f"Duplicate image label at {labels_path}:{line_number}: {filename}")
        seen_names.add(normalized_name)
        image_path = images_dir / filename
        if not image_path.is_file():
            raise FileNotFoundError(f"Labeled MMOTU image does not exist: {image_path}")
        records.append(
            {
                "image_id": filename,
                "image_path": image_path.resolve(),
                "label": class_id,
                "label_name": MMOTU_8_CLASSES[class_id],
                "image_sha256": _sha256_file(image_path),
            }
        )
    if not records:
        raise ValueError(f"No image labels were found in {labels_path}")
    return records


def validate_image_level_partitions(train_records: list[dict[str, Any]], val_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify image identity separation and label coverage without requiring patient IDs."""
    train_names = {record["image_id"].casefold() for record in train_records}
    val_names = {record["image_id"].casefold() for record in val_records}
    if train_names & val_names:
        raise ValueError("MMOTU train/validation filename overlap detected")
    train_hashes = {record["image_sha256"] for record in train_records}
    val_hashes = {record["image_sha256"] for record in val_records}
    if train_hashes & val_hashes:
        raise ValueError("MMOTU train/validation image-content overlap detected")

    train_counts = Counter(record["label"] for record in train_records)
    val_counts = Counter(record["label"] for record in val_records)
    missing_train = [class_id for class_id in range(len(MMOTU_8_CLASSES)) if not train_counts[class_id]]
    missing_val = [class_id for class_id in range(len(MMOTU_8_CLASSES)) if not val_counts[class_id]]
    if missing_train or missing_val:
        raise ValueError(
            "Every class must be present in both image-level partitions; "
            f"missing train={missing_train}, validation={missing_val}"
        )
    return {
        "train_counts": {MMOTU_8_CLASSES[index]: train_counts[index] for index in range(len(MMOTU_8_CLASSES))},
        "validation_counts": {MMOTU_8_CLASSES[index]: val_counts[index] for index in range(len(MMOTU_8_CLASSES))},
        "train_validation_filename_overlap": 0,
        "train_validation_image_hash_overlap": 0,
        "split_level": "image-level",
        "patient_identity_available": False,
        "patient_level_independence_verified": False,
    }


def build_classifier_model(
    num_classes: int = len(MMOTU_8_CLASSES),
    in_channels: int = 3,
    pretrained: bool = True,
) -> nn.Module:
    if num_classes < 2:
        raise ValueError("num_classes must be at least 2")
    if in_channels not in (1, 3):
        raise ValueError("The MMOTU classifier accepts one grayscale or three color channels")
    weights = ResNet34_Weights.DEFAULT if pretrained else None
    model = resnet34(weights=weights)
    if in_channels == 1:
        original = model.conv1
        replacement = nn.Conv2d(
            1,
            original.out_channels,
            kernel_size=original.kernel_size,
            stride=original.stride,
            padding=original.padding,
            bias=False,
        )
        if pretrained:
            with torch.no_grad():
                replacement.weight.copy_(original.weight.mean(dim=1, keepdim=True))
        model.conv1 = replacement
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    return model


class MMOTUClassificationDataset(Dataset):
    def __init__(self, records: list[dict[str, Any]], image_size: int = 384, is_train: bool = False):
        if image_size < 64:
            raise ValueError("image_size must be at least 64 pixels")
        self.records = records
        self.image_size = image_size
        self.is_train = is_train
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    def __len__(self) -> int:
        return len(self.records)

    def _load_image(self, path: Path) -> np.ndarray:
        image_bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image_bgr is None:
            raise ValueError(f"Could not decode MMOTU image: {path}")
        if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
            raise ValueError(f"Expected a 3-channel color image: {path}")

        # Apply CLAHE to luminance only so Doppler color information is retained.
        lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
        lab[:, :, 0] = self.clahe.apply(lab[:, :, 0])
        image_rgb = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

        height, width = image_rgb.shape[:2]
        scale = min(self.image_size / width, self.image_size / height)
        new_width = max(1, int(round(width * scale)))
        new_height = max(1, int(round(height * scale)))
        interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
        resized = cv2.resize(image_rgb, (new_width, new_height), interpolation=interpolation)
        canvas = np.zeros((self.image_size, self.image_size, 3), dtype=np.uint8)
        x_offset = (self.image_size - new_width) // 2
        y_offset = (self.image_size - new_height) // 2
        canvas[y_offset : y_offset + new_height, x_offset : x_offset + new_width] = resized
        if self.is_train:
            if random.random() < 0.5:
                canvas = cv2.flip(canvas, 1)
            contrast = random.uniform(0.95, 1.05)
            brightness = random.uniform(-4.0, 4.0)
            canvas = np.clip(canvas.astype(np.float32) * contrast + brightness, 0, 255).astype(np.uint8)
        return canvas

    def __getitem__(self, index: int) -> dict[str, Any]:
        record = self.records[index]
        image = self._load_image(Path(record["image_path"]))
        tensor = torch.from_numpy(image.transpose(2, 0, 1).copy()).float().div_(255.0)
        mean = torch.tensor(IMAGENET_MEAN, dtype=tensor.dtype).view(3, 1, 1)
        std = torch.tensor(IMAGENET_STD, dtype=tensor.dtype).view(3, 1, 1)
        tensor = (tensor - mean) / std
        return {
            "image": tensor,
            "target": torch.tensor(record["label"], dtype=torch.long),
            "image_id": record["image_id"],
        }


def compute_multiclass_metrics(logits: torch.Tensor, targets: torch.Tensor) -> dict[str, Any]:
    predictions = torch.argmax(logits, dim=1).detach().cpu().numpy().astype(np.int64)
    truth = targets.detach().cpu().numpy().astype(np.int64)
    labels = list(range(len(MMOTU_8_CLASSES)))
    if truth.size == 0:
        raise ValueError("Cannot calculate metrics for an empty sample set")
    per_class: dict[str, dict[str, int | float]] = {}
    confusion = np.zeros((len(labels), len(labels)), dtype=np.int64)
    for actual, predicted in zip(truth, predictions, strict=True):
        confusion[actual, predicted] += 1
    for class_id, class_name in enumerate(MMOTU_8_CLASSES):
        tp = int(confusion[class_id, class_id])
        support = int(confusion[class_id, :].sum())
        predicted_count = int(confusion[:, class_id].sum())
        precision = tp / predicted_count if predicted_count else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[class_name] = {
            "support": support,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    return {
        "accuracy": round(float(np.mean(predictions == truth)), 4),
        "macro_f1": round(float(f1_score(truth, predictions, labels=labels, average="macro", zero_division=0)), 4),
        "balanced_accuracy": round(
            float(np.mean([per_class[name]["recall"] for name in MMOTU_8_CLASSES])), 4
        ),
        "per_class": per_class,
        "confusion_matrix": confusion.tolist(),
        "sample_count": int(truth.size),
    }


def _set_batch_norm_eval(model: nn.Module) -> None:
    # Small batches are expected on the available 4 GB GPU; retain pretrained running stats.
    for module in model.modules():
        if isinstance(module, nn.modules.batchnorm._BatchNorm):
            module.eval()


def _run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None = None,
    scaler: torch.amp.GradScaler | None = None,
) -> tuple[float, dict[str, Any], list[dict[str, Any]]]:
    training = optimizer is not None
    model.train(training)
    if training:
        _set_batch_norm_eval(model)
    total_loss = 0.0
    all_logits: list[torch.Tensor] = []
    all_targets: list[torch.Tensor] = []
    predictions_rows: list[dict[str, Any]] = []
    context = torch.enable_grad if training else torch.no_grad
    with context():
        for batch in loader:
            images = batch["image"].to(device, non_blocking=True)
            targets = batch["target"].to(device, non_blocking=True)
            if training:
                optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
                logits = model(images)
                loss = criterion(logits, targets)
            if training:
                assert scaler is not None and optimizer is not None
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            total_loss += float(loss.detach().item()) * images.shape[0]
            all_logits.append(logits.detach().float().cpu())
            all_targets.append(targets.detach().cpu())
            probabilities = torch.softmax(logits.detach().float(), dim=1).cpu()
            predicted_classes = probabilities.argmax(dim=1)
            for row_index, image_id in enumerate(batch["image_id"]):
                predicted = int(predicted_classes[row_index])
                actual = int(targets[row_index].detach().cpu())
                predictions_rows.append(
                    {
                        "image_id": image_id,
                        "target_id": actual,
                        "target_category": MMOTU_8_CLASSES[actual],
                        "predicted_id": predicted,
                        "predicted_category": MMOTU_8_CLASSES[predicted],
                        "predicted_probability": float(probabilities[row_index, predicted]),
                    }
                )
    joined_logits = torch.cat(all_logits)
    joined_targets = torch.cat(all_targets)
    return total_loss / len(loader.dataset), compute_multiclass_metrics(joined_logits, joined_targets), predictions_rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty predictions file: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def train_classifier(
    images_dir: Path,
    train_labels: Path,
    val_labels: Path,
    output_dir: Path,
    epochs: int = 30,
    batch_size: int = 4,
    learning_rate: float = 1e-4,
    patience: int = 8,
    image_size: int = 384,
    seed: int = 42,
    pretrained: bool = True,
    head_learning_rate: float | None = None,
    balanced_sampling: bool = False,
    selection_metric: str = "macro_f1",
    freeze_encoder: bool = False,
) -> dict[str, Any]:
    if min(epochs, batch_size, patience) < 1 or learning_rate <= 0 or (head_learning_rate is not None and head_learning_rate <= 0):
        raise ValueError("epochs, batch_size, patience and learning rates must be positive")
    if selection_metric not in {"accuracy", "macro_f1"}:
        raise ValueError("selection_metric must be 'accuracy' or 'macro_f1'")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.benchmark = True

    train_records = parse_class_labels(train_labels, images_dir)
    val_records = parse_class_labels(val_labels, images_dir)
    split_audit = validate_image_level_partitions(train_records, val_records)
    train_dataset = MMOTUClassificationDataset(train_records, image_size=image_size, is_train=True)
    val_dataset = MMOTUClassificationDataset(val_records, image_size=image_size, is_train=False)
    train_counts = Counter(record["label"] for record in train_records)
    class_weights = torch.tensor(
        [len(train_records) / (len(MMOTU_8_CLASSES) * train_counts[index]) for index in range(len(MMOTU_8_CLASSES))],
        dtype=torch.float32,
    )

    generator = torch.Generator().manual_seed(seed)
    sampler = None
    if balanced_sampling:
        sample_weights = torch.tensor(
            [1.0 / train_counts[record["label"]] for record in train_records], dtype=torch.double
        )
        sampler = WeightedRandomSampler(
            sample_weights,
            num_samples=len(train_records),
            replacement=True,
            generator=generator,
        )
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
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_classifier_model(pretrained=pretrained).to(device)
    if freeze_encoder:
        for name, parameter in model.named_parameters():
            parameter.requires_grad = name.startswith("fc.")
    criterion = nn.CrossEntropyLoss(weight=None if balanced_sampling else class_weights.to(device))
    if head_learning_rate is None:
        optimizer = torch.optim.AdamW(
            [parameter for parameter in model.parameters() if parameter.requires_grad],
            lr=learning_rate,
            weight_decay=1e-4,
        )
    else:
        encoder_parameters = [
            parameter
            for name, parameter in model.named_parameters()
            if parameter.requires_grad and not name.startswith("fc.")
        ]
        head_parameters = [parameter for parameter in model.fc.parameters() if parameter.requires_grad]
        parameter_groups = []
        if encoder_parameters:
            parameter_groups.append({"params": encoder_parameters, "lr": learning_rate})
        if head_parameters:
            parameter_groups.append({"params": head_parameters, "lr": head_learning_rate})
        optimizer = torch.optim.AdamW(
            parameter_groups,
            lr=learning_rate,
            weight_decay=1e-4,
        )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode="max", factor=0.3, patience=3)
    scaler = torch.amp.GradScaler(device.type, enabled=device.type == "cuda")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    best_path = output_dir / "mmotu_resnet34_8class_best.pth"
    last_path = output_dir / "mmotu_resnet34_8class_last.pth"
    best_selection_score = -1.0
    best_epoch = 0
    epochs_without_improvement = 0
    history: list[dict[str, Any]] = []
    started = time.perf_counter()
    print(
        f"Image-level MMOTU training: train={len(train_dataset)}, validation={len(val_dataset)}, "
        f"device={device}, gpu={torch.cuda.get_device_name(0) if device.type == 'cuda' else 'none'}, "
        f"batch={batch_size}, image_size={image_size}, balanced_sampling={balanced_sampling}, "
        f"encoder_lr={learning_rate}, head_lr={head_learning_rate or learning_rate}, "
        f"selection_metric={selection_metric}, freeze_encoder={freeze_encoder}",
        flush=True,
    )

    for epoch in range(1, epochs + 1):
        train_loss, train_metrics, _ = _run_epoch(model, train_loader, criterion, device, optimizer, scaler)
        val_loss, val_metrics, val_predictions = _run_epoch(model, val_loader, criterion, device)
        selection_score = val_metrics[selection_metric]
        scheduler.step(selection_score)
        improved = selection_score > best_selection_score
        if improved:
            best_selection_score = selection_score
            best_epoch = epoch
            epochs_without_improvement = 0
            torch.save(model.state_dict(), best_path)
            (output_dir / "validation_metrics.json").write_text(
                json.dumps(val_metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            _write_csv(output_dir / "validation_predictions.csv", val_predictions)
        else:
            epochs_without_improvement += 1
        torch.save(model.state_dict(), last_path)
        record = {
            "epoch": epoch,
            "train_loss": train_loss,
            "train_accuracy": train_metrics["accuracy"],
            "train_macro_f1": train_metrics["macro_f1"],
            "validation_loss": val_loss,
            "validation_accuracy": val_metrics["accuracy"],
            "validation_macro_f1": val_metrics["macro_f1"],
            "validation_balanced_accuracy": val_metrics["balanced_accuracy"],
            "learning_rate": optimizer.param_groups[0]["lr"],
            "is_best": improved,
        }
        history.append(record)
        (output_dir / "training_history.json").write_text(
            json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(
            f"epoch={epoch:02d}/{epochs} train_loss={train_loss:.4f} "
            f"train_macro_f1={train_metrics['macro_f1']:.4f} "
            f"val_macro_f1={val_metrics['macro_f1']:.4f} val_acc={val_metrics['accuracy']:.4f} "
            f"best_{selection_metric}={best_selection_score:.4f}",
            flush=True,
        )
        if epochs_without_improvement >= patience:
            break

    if best_epoch == 0 or not best_path.is_file():
        raise RuntimeError("Training ended without producing a validation-selected checkpoint")
    duration_seconds = round(time.perf_counter() - started, 2)
    run_config = {
        "task": "MMOTU 2D image-level 8-class global category classification",
        "intended_use": "research only; not a clinical diagnosis or care recommendation",
        "architecture": "ResNet34",
        "pretrained_imagenet": pretrained,
        "encoder_frozen": freeze_encoder,
        "input": {
            "channels": 3,
            "image_size": [image_size, image_size],
            "color": "RGB; CLAHE applied to luminance channel to preserve Doppler chroma",
            "resize": "aspect-preserving letterbox",
            "normalization": {"mean": IMAGENET_MEAN, "std": IMAGENET_STD},
            "manual_masks_used": False,
        },
        "class_id_to_name": {str(index): name for index, name in enumerate(MMOTU_8_CLASSES)},
        "inverse_frequency_weights": {
            MMOTU_8_CLASSES[index]: float(class_weights[index]) for index in range(len(MMOTU_8_CLASSES))
        },
        "loss_class_weights": None if balanced_sampling else {
            MMOTU_8_CLASSES[index]: float(class_weights[index]) for index in range(len(MMOTU_8_CLASSES))
        },
        "split": split_audit,
        "train_label_file": str(Path(train_labels).resolve()),
        "train_label_file_sha256": _sha256_file(Path(train_labels)),
        "validation_label_file": str(Path(val_labels).resolve()),
        "validation_label_file_sha256": _sha256_file(Path(val_labels)),
        "train_count": len(train_records),
        "validation_count": len(val_records),
        "validation_role": "model selection partition; not an independent or patient-level clinical test",
        "test_split_used": False,
        "patient_identity_available": False,
        "patient_level_independence_verified": False,
        "seed": seed,
        "device": str(device),
        "gpu_name": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
        "batch_size": batch_size,
        "epochs_requested": epochs,
        "epochs_completed": len(history),
        "best_epoch": best_epoch,
        "best_selection_metric": selection_metric,
        "best_selection_score": best_selection_score,
        "best_validation_accuracy": json.loads((output_dir / "validation_metrics.json").read_text(encoding="utf-8"))["accuracy"],
        "best_validation_macro_f1": json.loads((output_dir / "validation_metrics.json").read_text(encoding="utf-8"))["macro_f1"],
        "best_validation_metrics": json.loads((output_dir / "validation_metrics.json").read_text(encoding="utf-8")),
        "optimizer": "AdamW",
        "loss": "CrossEntropyLoss" if balanced_sampling else "class-weighted CrossEntropyLoss",
        "sampling_strategy": "weighted_random_sampler_with_replacement" if balanced_sampling else "shuffle",
        "encoder_learning_rate": learning_rate,
        "classifier_head_learning_rate": head_learning_rate or learning_rate,
        "selection_metric": f"validation {selection_metric}",
        "duration_seconds": duration_seconds,
        "best_checkpoint": str(best_path.resolve()),
        "best_checkpoint_sha256": _sha256_file(best_path),
        "last_checkpoint": str(last_path.resolve()),
        "last_checkpoint_sha256": _sha256_file(last_path),
    }
    (output_dir / "run_config.json").write_text(
        json.dumps(run_config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(run_config, indent=2, ensure_ascii=False), flush=True)
    return run_config


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train an image-level MMOTU 8-class research classifier using official global category labels."
    )
    parser.add_argument("--images-dir", type=Path, default=ROOT / "dataset/2d/images")
    parser.add_argument("--train-labels", type=Path, default=ROOT / "metadata/mmotu_2d_train_cls.txt")
    parser.add_argument("--val-labels", type=Path, default=ROOT / "metadata/mmotu_2d_val_cls.txt")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "checkpoints/mmotu_8class_classifier_2026-10-27")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--head-learning-rate", type=float, default=None)
    parser.add_argument("--balanced-sampling", action="store_true", help="Balance classes with a weighted image sampler")
    parser.add_argument("--selection-metric", choices=("accuracy", "macro_f1"), default="macro_f1")
    parser.add_argument("--freeze-encoder", action="store_true", help="Train only the final classifier layer")
    parser.add_argument("--patience", type=int, default=8)
    parser.add_argument("--image-size", type=int, default=384)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-pretrained", action="store_true", help="Initialize ResNet34 randomly instead of ImageNet weights")
    args = parser.parse_args()
    train_classifier(
        images_dir=args.images_dir,
        train_labels=args.train_labels,
        val_labels=args.val_labels,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        patience=args.patience,
        image_size=args.image_size,
        seed=args.seed,
        pretrained=not args.no_pretrained,
        head_learning_rate=args.head_learning_rate,
        balanced_sampling=args.balanced_sampling,
        selection_metric=args.selection_metric,
        freeze_encoder=args.freeze_encoder,
    )


if __name__ == "__main__":
    main()
