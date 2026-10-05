"""Fine-tune the full-data U-Net on its 2D ultrasound training images."""

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

import torch
from torch.optim import AdamW
from torch.utils.data import DataLoader

from ai_training.dataset_loader import OvarianUltrasoundDataset
from ai_training.train_baseline_unet import ComboLoss, compute_batch_dice
from backend.models.unet import StandardUNet


def select_2d_rows(manifest: Path) -> list[dict[str, str]]:
    with manifest.open(newline="", encoding="utf-8") as stream:
        rows = [row for row in csv.DictReader(stream) if row["case_id"].startswith("Vinmec_2D_")]
    if not rows:
        raise ValueError("No 2D image-mask pairs in manifest")
    return rows


def finetune(manifest: Path, checkpoint: Path, output_dir: Path, epochs: int = 3) -> Path:
    if epochs < 1:
        raise ValueError("Epochs must be positive")
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = select_2d_rows(manifest)
    selected_manifest = output_dir / "finetune_2d_manifest.csv"
    with selected_manifest.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("case_id", "image_path", "mask_path"))
        writer.writeheader()
        writer.writerows(rows)

    torch.manual_seed(42)
    loader = DataLoader(OvarianUltrasoundDataset(str(selected_manifest), is_train=True), batch_size=2, shuffle=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = StandardUNet(in_channels=1, num_classes=1, base_filters=32).to(device)
    model.load_state_dict(torch.load(checkpoint, map_location=device, weights_only=True), strict=True)
    optimizer = AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)
    criterion = ComboLoss(bce_weight=0.5, dice_weight=0.5)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    history = []
    latest = output_dir / "finetune_2d_latest.pth"
    final = output_dir / "finetune_2d_final.pth"
    started = time.time()
    print(f"Fine-tuning {len(rows)} 2D images for {epochs} epochs on {device}", flush=True)

    for epoch in range(1, epochs + 1):
        model.train()
        loss_sum = dice_sum = 0.0
        for batch in loader:
            images = batch["image"].to(device)
            masks = batch["mask"].to(device)
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=device.type == "cuda"):
                logits = model(images)
                loss = criterion(logits, masks)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            loss_sum += loss.item()
            dice_sum += compute_batch_dice(logits.detach(), masks)
        row = {"epoch": epoch, "train_loss": loss_sum / len(loader), "train_dice": dice_sum / len(loader)}
        history.append(row)
        torch.save(model.state_dict(), latest)
        (output_dir / "finetune_2d_history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
        print(f"Epoch {epoch}/{epochs}: loss={row['train_loss']:.4f}, train_dice={row['train_dice']:.4f}", flush=True)

    latest.replace(final)
    print(f"Finished in {(time.time() - started) / 60:.1f} min; sha256={hashlib.sha256(final.read_bytes()).hexdigest()}", flush=True)
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("checkpoints/full_unet_manifest.csv"))
    parser.add_argument("--checkpoint", type=Path, default=Path("checkpoints/full_unet_final.pth"))
    parser.add_argument("--output-dir", type=Path, default=Path("checkpoints/finetune_2d"))
    parser.add_argument("--epochs", type=int, default=3)
    args = parser.parse_args()
    finetune(args.manifest, args.checkpoint, args.output_dir, args.epochs)
