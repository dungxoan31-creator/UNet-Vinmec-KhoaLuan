"""
Tests for Evaluation Report Builder and Artifact Integration (Task 19).
Verifies:
1. Report values are strictly artifact-derived.
2. Missing cohorts are never reported as 0.0 scores.
3. Current run hash mismatches are loudly visible/rejected.
4. Legacy evaluation is explicitly labeled as historical / retrospective replay.
5. Technical testers are never counted as clinicians.
6. Missing independent test blocks evaluation_complete while allowing prototype_ready.
"""

import json
from pathlib import Path
import pytest

from scripts.build_evaluation_report import (
    build_report,
    audit_run_summary,
    audit_current_run_pointer,
    generate_markdown_report,
    generate_limitations_doc,
)

ROOT = Path(__file__).resolve().parents[1]


def test_report_values_are_artifact_derived(tmp_path):
    """Report metrics must be extracted directly from artifact summary.json files."""
    run_dir = tmp_path / "mock_val"
    run_dir.mkdir()
    summary_data = {
        "schema_version": 1,
        "run_id": "val_mock",
        "run_kind": "validation_dry_run",
        "status": "COMPLETE",
        "protocol_sha256": "abc111",
        "manifest_sha256": "def222",
        "checkpoint_sha256": "417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d",
        "counts": {"total_samples": 50, "nonempty_gt_samples": 50, "empty_gt_samples": 0},
        "primary": {
            "dice": {"mean": 0.671731, "median": 0.758751, "n_valid": 50, "n_null": 0},
            "iou": {"mean": 0.554238, "median": 0.611280, "n_valid": 50, "n_null": 0},
            "recall": {"mean": 0.697852, "median": 0.791255, "n_valid": 50, "n_null": 0},
            "precision": {"mean": 0.752697, "median": 0.857712, "n_valid": 50, "n_null": 0},
            "specificity": {"mean": 0.972636, "median": 0.983766, "n_valid": 50, "n_null": 0},
            "hd95_px": {"mean": 102.4336, "median": 88.8487, "n_valid": 50, "n_null": 0},
        },
        "secondary": {
            "micro_dice": 0.7504,
            "micro_iou": 0.6005,
            "total_tp": 1000,
            "total_fp": 200,
            "total_fn": 300,
            "total_tn": 5000,
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary_data), encoding="utf-8")

    out_dir = tmp_path / "report_out"
    report = build_report(
        root=tmp_path,
        run_dirs=[run_dir],
        hitl_dir=None,
        user_dir=None,
        independent_gate_path=None,
        output=out_dir,
    )

    assert report["runs"][0]["primary"]["dice"]["mean"] == 0.671731
    results_md = (out_dir / "results.md").read_text(encoding="utf-8")
    assert "0.6717" in results_md
    assert "0.5542" in results_md
    assert (out_dir / "release_status.json").exists()


def test_missing_cohort_never_becomes_zero_score(tmp_path):
    """Missing runs/cohorts must retain null/None values, never coerce to 0.0 or 0%."""
    run_dir = tmp_path / "mock_empty_metrics"
    run_dir.mkdir()
    summary_data = {
        "schema_version": 1,
        "run_id": "test_unrun",
        "run_kind": "independent_test",
        "status": "BLOCKED",
        "protocol_sha256": "abc111",
        "checkpoint_sha256": "417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d",
        "counts": {"total_samples": 0, "nonempty_gt_samples": 0, "empty_gt_samples": 0},
        "primary": {
            "dice": {"mean": None, "median": None, "n_valid": 0, "n_null": 0, "null_reason": "unrun_or_blocked"},
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary_data), encoding="utf-8")

    out_dir = tmp_path / "report_out"
    report = build_report(
        root=tmp_path,
        run_dirs=[run_dir],
        hitl_dir=None,
        user_dir=None,
        independent_gate_path=None,
        output=out_dir,
    )

    dice_entry = report["runs"][0]["primary"]["dice"]
    assert dice_entry["mean"] is None
    assert dice_entry.get("null_reason") == "unrun_or_blocked"
    results_md = (out_dir / "results.md").read_text(encoding="utf-8")
    assert "0.0000" not in results_md
    assert "Chưa có / Không xác định" in results_md or "N/A" in results_md


def test_current_run_hash_mismatch_visible(tmp_path):
    """Audit must fail loudly if current_run.json points to a summary with mismatched hashes."""
    run_dir = tmp_path / "tampered_run"
    run_dir.mkdir()
    summary_data = {
        "schema_version": 1,
        "run_id": "val_1",
        "run_kind": "validation_dry_run",
        "status": "COMPLETE",
        "protocol_sha256": "legit_protocol_hash",
        "manifest_sha256": "manifest_hash",
        "checkpoint_sha256": "417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d",
        "counts": {"total_samples": 10},
        "primary": {},
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary_data), encoding="utf-8")

    pointer_data = {
        "summary_path": str(summary_path),
        "run_id": "val_1",
        "run_kind": "validation_dry_run",
        "protocol_sha256": "TAMPERED_PROTOCOL_HASH",  # Mismatch!
        "checkpoint_sha256": "417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d",
    }
    pointer_file = tmp_path / "current_run.json"
    pointer_file.write_text(json.dumps(pointer_data), encoding="utf-8")

    with pytest.raises(ValueError, match="Hash mismatch|protocol_sha256 mismatch"):
        audit_current_run_pointer(pointer_file)


def test_legacy_evaluation_is_historical(tmp_path):
    """Runs with kind retrospective_test_replay must be tagged as historical/retrospective."""
    run_dir = tmp_path / "legacy_test_v1"
    run_dir.mkdir()
    summary_data = {
        "schema_version": 1,
        "run_id": "legacy_test_v1",
        "run_kind": "retrospective_test_replay",
        "status": "COMPLETE",
        "protocol_sha256": "7ca6c3791b4c2266fd1717276aaf4d2072798010a688851abca5f51f490474bb",
        "checkpoint_sha256": "417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d",
        "counts": {"total_samples": 402},
        "primary": {
            "dice": {"mean": 0.7289, "median": 0.8045, "n_valid": 402, "n_null": 0},
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary_data), encoding="utf-8")

    audit = audit_run_summary(run_dir / "summary.json")
    assert audit["is_historical_replay"] is True
    assert "retrospective" in audit["kind_label"].lower()
    assert "independent" not in audit["kind_label"].lower()


def test_technical_tester_not_clinician(tmp_path):
    """User study summary must not conflate technical testers with actual clinicians."""
    user_study_dir = tmp_path / "user_study"
    user_study_dir.mkdir()
    study_status = {
        "study_status": "NOT_CONDUCTED",
        "clinician_count": 0,
        "technical_count": 1,
        "total_participants": 1,
        "has_clinician_validation": False,
    }
    (user_study_dir / "study_status.json").write_text(json.dumps(study_status), encoding="utf-8")

    out_dir = tmp_path / "report_out"
    report = build_report(
        root=tmp_path,
        run_dirs=[],
        hitl_dir=None,
        user_dir=user_study_dir,
        independent_gate_path=None,
        output=out_dir,
    )

    user_info = report["user_study"]
    assert user_info["clinician_count"] == 0
    assert user_info["technical_count"] == 1
    assert user_info["has_clinician_validation"] is False
    assert user_info["study_status"] == "NOT_CONDUCTED"

    results_md = (out_dir / "results.md").read_text(encoding="utf-8")
    assert "NOT_CONDUCTED" in results_md
    assert "0 bác sĩ" in results_md or "0 clinician" in results_md.lower()


def test_missing_independent_test_blocks_complete(tmp_path):
    """When prototype is PASS but independent test is BLOCKED: prototype_ready=true, evaluation_complete=false."""
    gate_dir = tmp_path / "independent_gate"
    gate_dir.mkdir()
    gate_file = gate_dir / "audit.json"
    gate_file.write_text(
        json.dumps({
            "status": "BLOCKED",
            "counts": {"total": 402, "valid": 0, "failed": 402},
            "errors": ["Sample has empty patient_id; required for independent_test"],
        }),
        encoding="utf-8",
    )

    out_dir = tmp_path / "report_out"
    report = build_report(
        root=tmp_path,
        run_dirs=[],
        hitl_dir=None,
        user_dir=None,
        independent_gate_path=gate_file,
        prototype_checks_passed=True,
        output=out_dir,
    )

    status_json = json.loads((out_dir / "release_status.json").read_text(encoding="utf-8"))
    assert status_json["prototype_ready"] is True
    assert status_json["evaluation_complete"] is False
    assert any("independent" in b.lower() for b in status_json["blockers"])
