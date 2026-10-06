"""Fine-tune the unified Vinmec U-Net on Train and select by Validation Dice."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ai_training.train_baseline_unet import train_baseline

LEARNING_RATES = (1e-4, 3e-4)
EPOCHS = 20
PATIENCE = 6
BATCH_SIZE = 2
SEED = 42


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_split_hashes(split_dir: Path, expected: dict[str, str]) -> dict[str, str]:
    actual = {split: file_sha256(split_dir / f"{split}.csv") for split in ("train", "val", "test")}
    if actual != expected:
        differences = {key: {"expected": expected.get(key), "actual": actual.get(key)} for key in actual if expected.get(key) != actual[key]}
        raise ValueError(f"split SHA-256 mismatch: {differences}")
    return actual


def select_best_candidate(incumbent: dict, runs: list[dict]) -> dict:
    candidates = [
        {
            "name": "current_baseline",
            "checkpoint": incumbent["checkpoint_best"],
            "checkpoint_sha256": incumbent.get("checkpoint_best_sha256"),
            "validation_dice": incumbent["best_validation_dice"],
        }
    ]
    candidates.extend(
        {
            "name": run["name"],
            "checkpoint": run["checkpoint_best"],
            "checkpoint_sha256": run.get("checkpoint_best_sha256"),
            "validation_dice": run["best_validation_dice"],
        }
        for run in runs
    )
    selected = candidates[0]
    for candidate in candidates[1:]:
        if candidate["validation_dice"] > selected["validation_dice"]:
            selected = candidate
    return {
        "selection_metric": "mean per-image Validation Dice at threshold 0.5",
        "validation_only_selection": True,
        "test_used_for_selection": False,
        "improved_over_incumbent": selected["name"] != "current_baseline",
        "candidates": candidates,
        "selected": selected,
    }


def run_refinement(root: Path) -> dict:
    root = root.resolve()
    baseline_dir = root / "checkpoints/unified_vinmec_2026-10-06"
    baseline_config = json.loads((baseline_dir / "run_config.json").read_text(encoding="utf-8"))
    split_dir = root / "ai_training/splits/unified_vinmec_clean_2026-10-06"
    verified_hashes = verify_split_hashes(split_dir, baseline_config["split_sha256"])
    initial_checkpoint = root / baseline_config["checkpoint_best"]
    if not initial_checkpoint.is_file():
        raise FileNotFoundError(initial_checkpoint)
    baseline_config["checkpoint_best_sha256"] = file_sha256(initial_checkpoint)

    output_dir = root / "checkpoints/unified_vinmec_refine_2026-10-06"
    run_configs = []
    for learning_rate in LEARNING_RATES:
        run_name = f"lr_{learning_rate:.0e}"
        run_dir = output_dir / run_name
        train_baseline(
            epochs=EPOCHS,
            batch_size=BATCH_SIZE,
            lr=learning_rate,
            checkpoint_dir=str(run_dir),
            splits_dir=str(split_dir),
            seed=SEED,
            patience=PATIENCE,
            initial_checkpoint_path=str(initial_checkpoint),
        )
        run_config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
        run_config["name"] = run_name
        for key in ("checkpoint_best", "checkpoint_last", "initial_checkpoint"):
            value = run_config.get(key)
            if value:
                run_config[key] = Path(value).resolve().relative_to(root).as_posix()
        (run_dir / "run_config.json").write_text(json.dumps(run_config, indent=2) + "\n", encoding="utf-8")
        run_configs.append(run_config)

    summary = select_best_candidate(baseline_config, run_configs)
    summary.update(
        {
            "status": "completed",
            "split_sha256": verified_hashes,
            "starting_checkpoint": baseline_config["checkpoint_best"],
            "starting_checkpoint_sha256": file_sha256(initial_checkpoint),
            "hyperparameters": {
                "learning_rates": list(LEARNING_RATES),
                "epochs": EPOCHS,
                "patience": PATIENCE,
                "batch_size": BATCH_SIZE,
                "seed": SEED,
                "loss": "0.5 BCE + 0.5 Dice",
                "scheduler": "CosineAnnealingLR(eta_min=1e-6)",
            },
            "identity_level": "image-level; source Patient/Case IDs unavailable",
            "test_policy": "Test split was not iterated, used for selection, or reevaluated.",
        }
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "refinement_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    run_refinement(args.root)


if __name__ == "__main__":
    main()
