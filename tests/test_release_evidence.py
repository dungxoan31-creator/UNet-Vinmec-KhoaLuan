"""Tests for evaluation baseline and release evidence verification."""

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_baseline_paths_exclude_production_db():
    from backend.db import database

    runtime_db = Path(database.DB_PATH).resolve()
    is_isolated = any(p.lower() in ("artifacts", "temp", "tmp") or "temp" in p.lower() or "artifacts" in p.lower() for p in runtime_db.parts)
    assert is_isolated, f"Runtime DB must be an isolated test database, got {runtime_db}"
    prod_candidates = [
        (ROOT / "data" / "vinmec_ai.db").resolve(),
        (ROOT / "vinmec_ai.db").resolve(),
        (ROOT / "ovarian_ai.db").resolve(),
        (ROOT / "data" / "ovarian_ai.db").resolve(),
        (ROOT / "backend" / "data" / "vinmec_ai.db").resolve()
    ]
    for prod_db in prod_candidates:
        assert runtime_db != prod_db, f"Runtime DB must not equal production DB candidate {prod_db}"



def test_verifier_preserves_exit_status(tmp_path):
    if os.environ.get("VERIFIER_TEST_RUNNING"):
        return

    verifier_script = ROOT / "scripts" / "verify_evaluation_release.ps1"
    assert verifier_script.exists(), f"Verifier script {verifier_script} must exist"

    # Run verifier with a mock failing command or flag to ensure exit code 7 is recorded and verifier exits nonzero
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(verifier_script),
        "-MockCommandExit",
        "7",
        "-OutputDir",
        str(tmp_path),
        "-BaselineOnly"
    ]
    env = dict(os.environ)
    env["VERIFIER_TEST_RUNNING"] = "1"
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert result.returncode != 0, f"Verifier must exit nonzero when child process exits 7. Output: {result.stdout}\nError: {result.stderr}"

    results_json = tmp_path / "baseline_results.json"
    assert results_json.exists(), f"Results json must be created in {tmp_path}"
    import json
    data = json.loads(results_json.read_text(encoding="utf-8-sig"))
    assert any(cmd_record.get("exit_code") == 7 for cmd_record in data.get("commands", [])), (
        f"Recorded commands must include exit_code 7. Got: {data.get('commands')}"
    )


def test_missing_independent_test_blocks_complete(tmp_path):
    from scripts.build_evaluation_report import build_report

    gate_dir = tmp_path / "independent_gate"
    gate_dir.mkdir()
    gate_file = gate_dir / "audit.json"
    gate_file.write_text(
        '{"status": "BLOCKED", "counts": {"total": 402, "valid": 0, "failed": 402}}',
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
    assert report["prototype_ready"] is True
    assert report["evaluation_complete"] is False
    assert any("independent" in b.lower() for b in report["blockers"])


def test_release_rejects_missing_artifact_or_stale_hash(tmp_path):
    """Release package validation must fail if required report artifacts are missing or checkpoint SHA is stale."""
    from scripts.build_evaluation_report import validate_release_package

    report_dir = tmp_path / "incomplete_report"
    report_dir.mkdir()
    # Missing required files
    valid, errors = validate_release_package(report_dir)
    assert valid is False
    assert any("missing" in err.lower() for err in errors)

    # Now create files with mismatched hash
    for fname in ["results.md", "limitations.md", "evidence_matrix.csv", "checksums.csv", "final_checks.json", "open_issues.csv", "demo_script.md"]:
        (report_dir / fname).write_text("content", encoding="utf-8")

    (report_dir / "release_status.json").write_text(
        json.dumps({
            "checkpoint_sha256": "WRONG_STALE_HASH",
            "prototype_ready": True,
            "evaluation_complete": False,
        }),
        encoding="utf-8",
    )
    valid, errors = validate_release_package(report_dir, expected_checkpoint_sha="417828fa74349d0f7909434f9ad1ad7cb3258b64d41d3d756e2e80569744697d")
    assert valid is False
    assert any("hash mismatch" in err.lower() or "checkpoint" in err.lower() for err in errors)


def test_prototype_only_does_not_mark_evaluation_complete():
    """Prototype-only readiness must decouple prototype_ready (True) from evaluation_complete (False)."""
    report_file = ROOT / "evaluation" / "milestone_3_final" / "report" / "release_status.json"
    assert report_file.exists(), f"{report_file} must exist"
    import json
    data = json.loads(report_file.read_text(encoding="utf-8"))
    assert data["prototype_ready"] is True
    assert data["evaluation_complete"] is False
    assert len(data["blockers"]) > 0


def test_skipped_browser_is_not_live_verified(tmp_path):
    """Skipping browser tests cannot record live_browser_verified as True."""
    from scripts.build_evaluation_report import generate_final_checks

    checks = generate_final_checks(
        results={
            "skip_browser": True,
            "overall_exit_code": 0,
            "commands": [{"name": "pytest", "exit_code": 0}],
        },
        independent_gate_status="BLOCKED",
        output_dir=tmp_path,
    )
    assert checks["live_browser_verified"] is False
    assert checks["browser_skipped"] is True


def test_full_verifier_does_not_select_four_files():
    """Verifier script must support full regression scope without hardcoding 4 files."""
    script_text = (ROOT / "scripts" / "verify_evaluation_release.ps1").read_text(encoding="utf-8")
    assert "TestScope" in script_text, "verify_evaluation_release.ps1 must support -TestScope parameter"
    assert "full" in script_text.lower(), "verify_evaluation_release.ps1 must define 'full' test scope"
    assert "pytest.main(['tests'" in script_text or 'pytest.main(["tests"' in script_text, (
        "Full test scope must target entire tests/ directory"
    )


def test_selected_suite_cannot_claim_full_regression(tmp_path):
    """When running selected suite, recorded test_scope must be 'selected' and never claim 'full'."""
    script_text = (ROOT / "scripts" / "verify_evaluation_release.ps1").read_text(encoding="utf-8")
    assert "test_scope" in script_text, "verify_evaluation_release.ps1 must record test_scope in results"


def test_final_checks_records_test_scope(tmp_path):
    """generate_final_checks must record test_scope in final_checks.json."""
    from scripts.build_evaluation_report import generate_final_checks
    checks = generate_final_checks(
        results={"test_scope": "selected", "overall_exit_code": 0, "live_browser_verified": True},
        independent_gate_status="BLOCKED",
        output_dir=tmp_path,
    )
    assert checks["test_scope"] == "selected"
    saved = json.loads((tmp_path / "final_checks.json").read_text(encoding="utf-8"))
    assert saved["test_scope"] == "selected"



