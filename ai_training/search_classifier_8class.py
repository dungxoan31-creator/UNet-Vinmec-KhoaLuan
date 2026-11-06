"""Run bounded image-level MMOTU classifier trials selected by validation accuracy.

This is a research hyperparameter search. The official validation partition becomes
model-selection data after repeated trials and must not be presented as an unbiased
test set or as patient-independent clinical performance.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_training.train_classifier_8class import train_classifier

TRIALS: tuple[dict[str, Any], ...] = (
    {"name": "balanced_256_finetune_lr1e4", "seed": 43, "image_size": 256, "batch_size": 8, "learning_rate": 1e-4, "head_learning_rate": 1e-3, "balanced_sampling": True, "freeze_encoder": False},
    {"name": "balanced_256_finetune_lr5e5", "seed": 44, "image_size": 256, "batch_size": 8, "learning_rate": 5e-5, "head_learning_rate": 5e-4, "balanced_sampling": True, "freeze_encoder": False},
    {"name": "balanced_384_linear_probe", "seed": 45, "image_size": 384, "batch_size": 4, "learning_rate": 1e-4, "head_learning_rate": 1e-3, "balanced_sampling": True, "freeze_encoder": True},
    {"name": "weighted_256_finetune", "seed": 46, "image_size": 256, "batch_size": 8, "learning_rate": 1e-4, "head_learning_rate": 1e-3, "balanced_sampling": False, "freeze_encoder": False},
    {"name": "balanced_384_finetune_lr3e5", "seed": 47, "image_size": 384, "batch_size": 4, "learning_rate": 3e-5, "head_learning_rate": 3e-4, "balanced_sampling": True, "freeze_encoder": False},
    {"name": "balanced_256_finetune_seed48", "seed": 48, "image_size": 256, "batch_size": 8, "learning_rate": 1e-4, "head_learning_rate": 1e-3, "balanced_sampling": True, "freeze_encoder": False},
)


def _write_search_state(path: Path, state: dict[str, Any]) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def run_accuracy_search(
    images_dir: Path,
    train_labels: Path,
    val_labels: Path,
    output_dir: Path,
    max_trials: int = len(TRIALS),
    no_improvement_limit: int = 3,
    epochs: int = 24,
    patience: int = 5,
    baseline_run_config: Path | None = None,
) -> dict[str, Any]:
    if not 1 <= max_trials <= len(TRIALS):
        raise ValueError(f"max_trials must be between 1 and {len(TRIALS)}")
    if no_improvement_limit < 1 or epochs < 1 or patience < 1:
        raise ValueError("no_improvement_limit, epochs, and patience must be positive")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if baseline_run_config is None:
        baseline_run_config = ROOT / "checkpoints/mmotu_8class_classifier_2026-10-27_balanced/run_config.json"
    baseline_run_config = Path(baseline_run_config)
    baseline: dict[str, Any] | None = None
    if baseline_run_config.is_file():
        baseline = json.loads(baseline_run_config.read_text(encoding="utf-8"))
        baseline_checkpoint = Path(baseline["best_checkpoint"])
        if not baseline_checkpoint.is_file():
            raise FileNotFoundError(f"Baseline classifier checkpoint is missing: {baseline_checkpoint}")
        from ai_training.train_classifier_8class import _sha256_file

        if _sha256_file(baseline_checkpoint) != baseline.get("best_checkpoint_sha256"):
            raise ValueError("Baseline classifier checkpoint SHA-256 does not match its run configuration")
    baseline_accuracy = None
    if baseline is not None:
        baseline_accuracy = baseline.get("best_validation_accuracy")
        if baseline_accuracy is None:
            baseline_accuracy = baseline.get("best_validation_metrics", {}).get("accuracy")
        if baseline_accuracy is None:
            raise ValueError("Baseline run configuration has no validation accuracy")
    initial_best_accuracy = float(baseline_accuracy) if baseline_accuracy is not None else -1.0
    state: dict[str, Any] = {
        "objective": "maximize observed validation accuracy",
        "validation_role": "repeated model selection; not independent evaluation",
        "split_level": "image-level",
        "patient_level_independence_verified": False,
        "stop_rule": {
            "maximum_trials": max_trials,
            "consecutive_trials_without_accuracy_improvement": no_improvement_limit,
            "maximum_epochs_per_trial": epochs,
            "epoch_patience": patience,
        },
        "comparison_baseline": (
            {
                "run_config": str(baseline_run_config.resolve()),
                "validation_accuracy": initial_best_accuracy,
                "checkpoint": baseline["best_checkpoint"],
                "checkpoint_sha256": baseline["best_checkpoint_sha256"],
            }
            if baseline
            else None
        ),
        "trials": [],
        "best_trial": None,
        "best_validation_accuracy": initial_best_accuracy,
        "best_checkpoint": baseline["best_checkpoint"] if baseline else None,
        "best_checkpoint_sha256": baseline["best_checkpoint_sha256"] if baseline else None,
        "trials_without_improvement": 0,
    }
    state_path = output_dir / "search_results.json"
    _write_search_state(state_path, state)

    for trial_index, trial_spec in enumerate(TRIALS[:max_trials], start=1):
        trial_dir = output_dir / f"trial_{trial_index:02d}_{trial_spec['name']}"
        train_kwargs = {key: value for key, value in trial_spec.items() if key != "name"}
        run_config = train_classifier(
            images_dir=images_dir,
            train_labels=train_labels,
            val_labels=val_labels,
            output_dir=trial_dir,
            epochs=epochs,
            patience=patience,
            selection_metric="accuracy",
            **train_kwargs,
        )
        validation_accuracy = float(run_config["best_validation_accuracy"])
        improved = validation_accuracy > state["best_validation_accuracy"]
        result = {
            "trial": trial_index,
            "name": trial_spec["name"],
            "seed": trial_spec["seed"],
            "image_size": trial_spec["image_size"],
            "batch_size": trial_spec["batch_size"],
            "balanced_sampling": trial_spec["balanced_sampling"],
            "freeze_encoder": trial_spec["freeze_encoder"],
            "learning_rate": trial_spec["learning_rate"],
            "head_learning_rate": trial_spec["head_learning_rate"],
            "epochs_completed": run_config["epochs_completed"],
            "best_epoch": run_config["best_epoch"],
            "validation_accuracy": validation_accuracy,
            "validation_macro_f1": run_config["best_validation_macro_f1"],
            "high_grade_serous_recall": run_config["best_validation_metrics"]["per_class"][
                "high_grade_serous_cystadenocarcinoma"
            ]["recall"],
            "checkpoint": run_config["best_checkpoint"],
            "checkpoint_sha256": run_config["best_checkpoint_sha256"],
            "improved_best_accuracy": improved,
        }
        state["trials"].append(result)
        if improved:
            state["best_validation_accuracy"] = validation_accuracy
            state["best_trial"] = trial_index
            state["best_checkpoint"] = run_config["best_checkpoint"]
            state["best_checkpoint_sha256"] = run_config["best_checkpoint_sha256"]
            state["trials_without_improvement"] = 0
        else:
            state["trials_without_improvement"] += 1
        _write_search_state(state_path, state)
        print(
            f"trial={trial_index}/{max_trials} validation_accuracy={validation_accuracy:.4f} "
            f"best={state['best_validation_accuracy']:.4f} "
            f"no_improvement={state['trials_without_improvement']}/{no_improvement_limit}",
            flush=True,
        )
        if state["trials_without_improvement"] >= no_improvement_limit:
            state["stop_reason"] = "consecutive trials did not improve observed validation accuracy"
            break

    if "stop_reason" not in state:
        state["stop_reason"] = "maximum trial count reached"
    _write_search_state(state_path, state)
    print(json.dumps(state, indent=2, ensure_ascii=False), flush=True)
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded MMOTU image-level classifier search by validation accuracy.")
    parser.add_argument("--images-dir", type=Path, default=ROOT / "dataset/2d/images")
    parser.add_argument("--train-labels", type=Path, default=ROOT / "metadata/mmotu_2d_train_cls.txt")
    parser.add_argument("--val-labels", type=Path, default=ROOT / "metadata/mmotu_2d_val_cls.txt")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "checkpoints/mmotu_8class_accuracy_search_2026-10-27")
    parser.add_argument("--max-trials", type=int, default=len(TRIALS))
    parser.add_argument("--no-improvement-limit", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=24)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument(
        "--baseline-run-config",
        type=Path,
        default=ROOT / "checkpoints/mmotu_8class_classifier_2026-10-27_balanced/run_config.json",
    )
    args = parser.parse_args()
    run_accuracy_search(
        images_dir=args.images_dir,
        train_labels=args.train_labels,
        val_labels=args.val_labels,
        output_dir=args.output_dir,
        max_trials=args.max_trials,
        no_improvement_limit=args.no_improvement_limit,
        epochs=args.epochs,
        patience=args.patience,
        baseline_run_config=args.baseline_run_config,
    )


if __name__ == "__main__":
    main()
