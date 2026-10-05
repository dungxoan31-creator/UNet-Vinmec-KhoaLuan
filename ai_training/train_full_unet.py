"""Train Standard U-Net on every local Vinmec_2D and Vinmec_CEUS image-mask pair."""

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

from ai_training.dataset_loader import OvarianUltrasoundDataset
from ai_training.train_baseline_unet import ComboLoss, compute_batch_dice
from backend.models.unet import StandardUNet

GROUPS = (
    ("Vinmec_2D_train", "Vinmec_2D/train/train_image", "Vinmec_2D/train/train_label/label"),
    ("Vinmec_2D_test", "Vinmec_2D/test/image", "Vinmec_2D/test/label/black_write"),
    ("Vinmec_CEUS", "Vinmec_CEUS/image", "Vinmec_CEUS/label"),
)


def discover_pairs(data_dir: Path) -> list[tuple[str, Path, Path]]:
    pairs = []
    for group, image_dir, mask_dir in GROUPS:
        images = {path.stem: path for path in (data_dir / image_dir).glob("*.JPG")}
        masks = {path.stem: path for path in (data_dir / mask_dir).glob("*.PNG")}
        if not images or images.keys() != masks.keys():
            raise ValueError(f"Missing image or mask in {group}: images={len(images)}, masks={len(masks)}")
        for stem in sorted(images):
            image = cv2.imread(str(images[stem]), cv2.IMREAD_GRAYSCALE)
            mask = cv2.imread(str(masks[stem]), cv2.IMREAD_GRAYSCALE)
            if image is None or mask is None or image.shape != mask.shape:
                raise ValueError(f"Invalid image-mask pair: {group}/{stem}")
            if not set(np.unique(mask)).issubset({0, 255}):
                raise ValueError(f"Non-binary mask: {group}/{stem}")
            pairs.append((f"{group}_{stem}", images[stem], masks[stem]))
    return pairs


def train_full(data_dir: Path, output_dir: Path, epochs: int = 12, batch_size: int = 2) -> Path:
    pairs = discover_pairs(data_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = output_dir / "full_unet_manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("case_id", "image_path", "mask_path"))
        writer.writerows((case_id, image.as_posix(), mask.as_posix()) for case_id, image, mask in pairs)

    dataset = OvarianUltrasoundDataset(str(manifest), is_train=True)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0)
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
    started = time.time()
    print(f"Training {len(pairs)} image-mask pairs on {device}; {epochs} epochs, batch size {batch_size}", flush=True)

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
        scheduler.step()
        row = {"epoch": epoch, "train_loss": loss_sum / len(loader), "train_dice": dice_sum / len(loader)}
        history.append(row)
        torch.save(model.state_dict(), latest)
        history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
        print(f"Epoch {epoch}/{epochs}: loss={row['train_loss']:.4f}, train_dice={row['train_dice']:.4f}", flush=True)

    latest.replace(final)
    digest = hashlib.sha256(final.read_bytes()).hexdigest()
    print(f"Finished in {(time.time() - started) / 60:.1f} min; checkpoint={final}; sha256={digest}", flush=True)
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("dataset"))
    parser.add_argument("--output-dir", type=Path, default=Path("checkpoints"))
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=2)
    args = parser.parse_args()
    train_full(args.data_dir, args.output_dir, args.epochs, args.batch_size)
