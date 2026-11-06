import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_selected_model_keeps_test_evaluation_blocked_without_retired_artifacts():
    selection = json.loads((ROOT / "evaluation/selected_model.json").read_text(encoding="utf-8"))

    assert selection["candidate_only"] is True
    assert selection["selection_is_validation_tuned"] is True
    assert selection["test_evaluation"] is None
    assert selection["independent_test_status"] == "BLOCKED"
    assert selection["independent_gate_status"] == "BLOCKED"
    assert selection["source_patient_identity_verified"] is False

    synthetic = selection["synthetic_test_benchmark"]
    assert synthetic["benchmark_tag"] == "[SIMULATED - TECHNICAL BENCHMARK ONLY]"
    assert synthetic["patient_independence_verified"] is False
    assert synthetic["source_patient_identity_verified"] is False
    assert synthetic["label_provenance_verified"] is False

    assert not (ROOT / "evaluation/independent_test_cohort_2026-10-19").exists()
    assert not (ROOT / "evaluation/baseline_test_metrics.json").exists()
