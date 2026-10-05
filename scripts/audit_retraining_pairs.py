"""Verify same-stem Vinmec_2D train pairs and export preprocessing evidence."""

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np
import torch

from ai_training.dataset_loader import OvarianUltrasoundDataset, cv2_imread_unicode
from backend.services.preprocessor import UltrasoundPreprocessor


def audit(splits_dir: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    preprocessor = UltrasoundPreprocessor()
    rows = []
    preview_count = 0
    for split in ("train", "val"):
        dataset = OvarianUltrasoundDataset(splits_dir / f"{split}.csv", is_train=False)
        for index in range(len(dataset)):
            row = dataset.df.iloc[index]
            image_path = Path(row["image_path"])
            mask_path = Path(row["mask_path"])
            if image_path.stem != mask_path.stem:
                raise ValueError(f"Filename stems do not match: {image_path}, {mask_path}")
            sample = dataset[index]
            image = cv2_imread_unicode(str(image_path))
            tensor, padded, _, _ = preprocessor.preprocess_for_inference(image)
            if not torch.equal(tensor[0], sample["image"]):
                raise ValueError(f"Train/inference preprocessing differs: {image_path}")
            if sample["image"].shape != (1, 512, 512) or sample["mask"].shape != (1, 512, 512):
                raise ValueError(f"Unexpected preprocessed dimensions: {image_path}")
            if not set(sample["mask"].unique().tolist()).issubset({0.0, 1.0}):
                raise ValueError(f"Preprocessed mask is not binary: {mask_path}")
            rows.append({
                "image_id": image_path.stem, "split": split,
                "image_path": image_path.as_posix(), "mask_path": mask_path.as_posix(),
                "height": image.shape[0], "width": image.shape[1],
                "foreground_pixels_512": int(sample["mask"].sum().item()),
                "same_stem": True, "preprocessing_parity": True,
            })
            if preview_count < 6:
                mask = sample["mask"][0].numpy().astype(np.uint8)
                original = cv2.cvtColor(padded, cv2.COLOR_GRAY2BGR)
                overlay = original.copy()
                overlay[mask > 0] = (0.5 * overlay[mask > 0] + np.array([0, 127, 0])).astype(np.uint8)
                preview = np.concatenate((original, cv2.cvtColor(mask * 255, cv2.COLOR_GRAY2BGR), overlay), axis=1)
                success, encoded = cv2.imencode(".png", preview)
                if not success:
                    raise OSError("Cannot encode ground-truth preview")
                encoded.tofile(str(output_dir / f"pair_{image_path.stem}.png"))
                preview_count += 1
            if (index + 1) % 100 == 0:
                print(f"Audited {split}: {index + 1}/{len(dataset)}", flush=True)
    with (output_dir / "pairs.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "count": len(rows), "same_stem_pairs": len(rows), "preprocessing_parity_pairs": len(rows),
        "empty_masks": sum(row["foreground_pixels_512"] == 0 for row in rows),
        "previews": preview_count, "patient_split_status": "image-level only; verified PID unavailable",
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splits-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.splits_dir, args.output_dir), indent=2))
