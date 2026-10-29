"""Train Standard U-Net on an image-level Train/Validation split."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import torch
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

from ai_training.train_baseline_unet import ComboLoss, compute_batch_dice, load_train_val_datasets
from backend.models.unet import StandardUNet


def train_full(split_dir: Path, output_dir: Path, epochs: int = 12, batch_size: int = 2) -> Path:
    if epochs < 1 or batch_size < 1:
        raise ValueError("Epochs and batch size must be positive")

    split_dir = Path(split_dir)
    train_dataset, val_dataset, manifest = load_train_val_datasets(split_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=0)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    criterion = ComboLoss(bce_weight=0.5, dice_weight=0.5)
    optimizer = AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    history_path = output_dir / "full_unet_training_history.json"
    latest = output_dir / "full_unet_latest.pth"
    final = output_dir / "full_unet_final.pth"
    history = []
    best_val_dice = float("-inf")
    started = time.time()
    print(
        f"Training {len(train_dataset)} image-level training pairs on {device}; "
        f"validation pairs={len(val_dataset)}, {epochs} epochs, batch size {batch_size}",
        flush=True,
    )

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss_sum = train_dice_sum = 0.0
        optimizer_steps = 0
        for batch in train_loader:
            images = batch["image"].to(device)
            masks = batch["mask"].to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
                logits = model(images)
                loss = criterion(logits, masks)
            scaler.scale(loss).backward()
            previous_scale = scaler.get_scale()
            scaler.step(optimizer)
            scaler.update()
            optimizer_steps += scaler.get_scale() >= previous_scale
            count = images.shape[0]
            train_loss_sum += loss.item() * count
            train_dice_sum += compute_batch_dice(logits.detach(), masks) * count

        model.eval()
        val_dice_sum = 0.0
        with torch.no_grad():
            for batch in val_loader:
                images = batch["image"].to(device)
                masks = batch["mask"].to(device)
                with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
                    logits = model(images)
                val_dice_sum += compute_batch_dice(logits, masks) * images.shape[0]

        if optimizer_steps:
            scheduler.step()
        train_loss = train_loss_sum / len(train_dataset)
        train_dice = train_dice_sum / len(train_dataset)
        val_dice = val_dice_sum / len(val_dataset)
        improved = val_dice > best_val_dice
        if improved:
            best_val_dice = val_dice
            torch.save(model.state_dict(), latest)
        record = {
            "epoch": epoch,
            "train_loss": train_loss,
            "train_dice": train_dice,
            "val_dice": val_dice,
            "is_best": improved,
        }
        history.append(record)
        history_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
        print(
            f"Epoch {epoch}/{epochs}: loss={train_loss:.4f}, "
            f"train_dice={train_dice:.4f}, val_dice={val_dice:.4f}",
            flush=True,
        )

    if not latest.is_file():
        raise RuntimeError("Validation did not produce a selectable checkpoint")
    latest.replace(final)
    digest = hashlib.sha256(final.read_bytes()).hexdigest()
    manifest_path = split_dir / "manifest.json"
    run_config = {
        "architecture": "Standard U-Net (base_filters=32)",
        "identity_status": "image_level_verified",
        "split_level": "image-level",
        "patient_level_independence_verified": False,
        "split_dir": str(split_dir.resolve()),
        "split_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "train_count": len(train_dataset),
        "validation_count": len(val_dataset),
        "test_split_image_data_used": False,
        "selection_metric": "validation Dice",
        "best_validation_dice": best_val_dice,
        "checkpoint": str(final.resolve()),
        "checkpoint_sha256": digest,
        "duration_seconds": round(time.time() - started, 2),
    }
    (output_dir / "full_unet_run_config.json").write_text(
        json.dumps(run_config, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Finished in {(time.time() - started) / 60:.1f} min; checkpoint={final}; sha256={digest}", flush=True)
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--split-dir",
        type=Path,
        default=Path("ai_training/splits/unified_vinmec_clean_2026-10-06"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("checkpoints/full_unet"))
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=2)
    args = parser.parse_args()
    train_full(args.split_dir, args.output_dir, args.epochs, args.batch_size)
