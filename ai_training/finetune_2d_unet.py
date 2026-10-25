"""Fine-tune Standard U-Net using Train and Validation from a verified patient split."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import torch
from torch.optim import AdamW
from torch.utils.data import DataLoader

from ai_training.train_baseline_unet import (
    ComboLoss,
    compute_batch_dice,
    load_verified_train_val_datasets,
    validate_checkpoint_provenance,
)
from backend.models.unet import StandardUNet


def finetune(split_dir: Path, checkpoint: Path, output_dir: Path, epochs: int = 3) -> Path:
    if epochs < 1:
        raise ValueError("Epochs must be positive")

    split_dir = Path(split_dir)
    train_dataset, val_dataset, manifest = load_verified_train_val_datasets(split_dir)
    manifest_path = split_dir / "manifest.json"
    split_manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    initial_checkpoint_sha256 = validate_checkpoint_provenance(
        checkpoint, expected_split_manifest_sha256=split_manifest_sha256
    )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    torch.manual_seed(42)
    train_loader = DataLoader(train_dataset, batch_size=2, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=2, shuffle=False, num_workers=0)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    model.load_state_dict(torch.load(checkpoint, map_location=device, weights_only=True), strict=True)
    optimizer = AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)
    criterion = ComboLoss(bce_weight=0.5, dice_weight=0.5)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    history = []
    best_val_dice = float("-inf")
    latest = output_dir / "finetune_2d_latest.pth"
    final = output_dir / "finetune_2d_final.pth"
    started = time.time()
    print(
        f"Fine-tuning {len(train_dataset)} patient-verified training pairs; "
        f"validation pairs={len(val_dataset)}, epochs={epochs} on {device}",
        flush=True,
    )

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss_sum = train_dice_sum = 0.0
        for batch in train_loader:
            images = batch["image"].to(device)
            masks = batch["mask"].to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
                logits = model(images)
                loss = criterion(logits, masks)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
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

        train_loss = train_loss_sum / len(train_dataset)
        train_dice = train_dice_sum / len(train_dataset)
        val_dice = val_dice_sum / len(val_dataset)
        improved = val_dice > best_val_dice
        if improved:
            best_val_dice = val_dice
            torch.save(model.state_dict(), latest)
        history.append(
            {
                "epoch": epoch,
                "train_loss": train_loss,
                "train_dice": train_dice,
                "val_dice": val_dice,
                "is_best": improved,
            }
        )
        (output_dir / "finetune_2d_history.json").write_text(
            json.dumps(history, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"Epoch {epoch}/{epochs}: train_loss={train_loss:.4f}, "
            f"train_dice={train_dice:.4f}, val_dice={val_dice:.4f}",
            flush=True,
        )

    if not latest.is_file():
        raise RuntimeError("Validation did not produce a selectable checkpoint")
    latest.replace(final)
    final_sha256 = hashlib.sha256(final.read_bytes()).hexdigest()
    run_config = {
        "architecture": "Standard U-Net (base_filters=32), fine-tuned",
        "identity_status": "patient_level_verified",
        "split_dir": str(split_dir.resolve()),
        "split_manifest_sha256": split_manifest_sha256,
        "train_count": len(train_dataset),
        "validation_count": len(val_dataset),
        "test_split_image_data_used": False,
        "selection_metric": "validation Dice",
        "best_validation_dice": best_val_dice,
        "initial_checkpoint_sha256": initial_checkpoint_sha256,
        "checkpoint": str(final.resolve()),
        "checkpoint_sha256": final_sha256,
        "duration_seconds": round(time.time() - started, 2),
    }
    (output_dir / "finetune_2d_run_config.json").write_text(
        json.dumps(run_config, indent=2) + "\n", encoding="utf-8"
    )
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--split-dir",
        type=Path,
        default=Path("ai_training/splits/unified_vinmec_clean_2026-10-06"),
    )
    parser.add_argument("--checkpoint", type=Path, default=Path("checkpoints/full_unet/full_unet_final.pth"))
    parser.add_argument("--output-dir", type=Path, default=Path("checkpoints/finetune_2d"))
    parser.add_argument("--epochs", type=int, default=3)
    args = parser.parse_args()
    finetune(args.split_dir, args.checkpoint, args.output_dir, args.epochs)
