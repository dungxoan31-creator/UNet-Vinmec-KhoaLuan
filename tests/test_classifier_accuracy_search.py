import hashlib
import json

import ai_training.search_classifier_8class as search


def test_accuracy_search_keeps_best_and_stops_after_consecutive_non_improving_trials(monkeypatch, tmp_path):
    validation_accuracies = iter((0.60, 0.58, 0.59, 0.75))
    calls = []

    def fake_train_classifier(**kwargs):
        calls.append(kwargs)
        accuracy = next(validation_accuracies)
        return {
            "best_validation_accuracy": accuracy,
            "best_validation_macro_f1": accuracy - 0.05,
            "best_validation_metrics": {
                "per_class": {"high_grade_serous_cystadenocarcinoma": {"recall": 0.4}}
            },
            "epochs_completed": 2,
            "best_epoch": 1,
            "best_checkpoint": str(kwargs["output_dir"] / "best.pth"),
            "best_checkpoint_sha256": f"hash-{accuracy}",
        }

    monkeypatch.setattr(search, "train_classifier", fake_train_classifier)
    result = search.run_accuracy_search(
        images_dir=tmp_path / "images",
        train_labels=tmp_path / "train.txt",
        val_labels=tmp_path / "val.txt",
        output_dir=tmp_path / "search",
        max_trials=4,
        no_improvement_limit=2,
        epochs=2,
        patience=1,
    )

    assert len(calls) == 3
    assert all(call["selection_metric"] == "accuracy" for call in calls)
    assert result["best_validation_accuracy"] == 0.60
    assert result["best_trial"] == 1
    assert result["stop_reason"] == "consecutive trials did not improve observed validation accuracy"
    assert result["patient_level_independence_verified"] is False


def test_accuracy_search_preserves_a_better_existing_checkpoint(monkeypatch, tmp_path):
    baseline_checkpoint = tmp_path / "baseline.pth"
    baseline_checkpoint.write_bytes(b"previous-best")
    baseline_run_config = tmp_path / "baseline.json"
    baseline_run_config.write_text(
        json.dumps(
            {
                "best_validation_accuracy": 0.70,
                "best_checkpoint": str(baseline_checkpoint),
                "best_checkpoint_sha256": hashlib.sha256(b"previous-best").hexdigest(),
            }
        ),
        encoding="utf-8",
    )

    def fake_train_classifier(**kwargs):
        return {
            "best_validation_accuracy": 0.60,
            "best_validation_macro_f1": 0.55,
            "best_validation_metrics": {
                "per_class": {"high_grade_serous_cystadenocarcinoma": {"recall": 0.4}}
            },
            "epochs_completed": 2,
            "best_epoch": 1,
            "best_checkpoint": str(kwargs["output_dir"] / "trial.pth"),
            "best_checkpoint_sha256": "trial-hash",
        }

    monkeypatch.setattr(search, "train_classifier", fake_train_classifier)
    result = search.run_accuracy_search(
        images_dir=tmp_path / "images",
        train_labels=tmp_path / "train.txt",
        val_labels=tmp_path / "val.txt",
        output_dir=tmp_path / "search",
        max_trials=1,
        no_improvement_limit=1,
        epochs=2,
        patience=1,
        baseline_run_config=baseline_run_config,
    )

    assert result["best_validation_accuracy"] == 0.70
    assert result["best_trial"] is None
    assert result["best_checkpoint"] == str(baseline_checkpoint)
    assert result["trials"][0]["improved_best_accuracy"] is False
