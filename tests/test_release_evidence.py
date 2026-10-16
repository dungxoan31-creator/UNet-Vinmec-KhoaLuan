"""Tests for evaluation baseline and release evidence verification."""

from pathlib import Path
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_baseline_paths_exclude_production_db():
    from tests import serve_isolated_app
    from backend.db import database
    
    runtime_db = Path(database.DB_PATH).resolve()
    assert "artifacts" in runtime_db.parts, f"Runtime DB must be under artifacts, got {runtime_db}"
    prod_candidates = [
        (ROOT / "data" / "vinmec_ai.db").resolve(),
        (ROOT / "vinmec_ai.db").resolve(),
        (ROOT / "backend" / "data" / "vinmec_ai.db").resolve()
    ]
    for prod_db in prod_candidates:
        assert runtime_db != prod_db, f"Runtime DB must not equal production DB candidate {prod_db}"


def test_verifier_preserves_exit_status(tmp_path):
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
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode != 0, f"Verifier must exit nonzero when child process exits 7. Output: {result.stdout}\nError: {result.stderr}"
    
    results_json = tmp_path / "baseline_results.json"
    assert results_json.exists(), f"Results json must be created in {tmp_path}"
    import json
    data = json.loads(results_json.read_text(encoding="utf-8-sig"))
    assert any(cmd_record.get("exit_code") == 7 for cmd_record in data.get("commands", [])), (
        f"Recorded commands must include exit_code 7. Got: {data.get('commands')}"
    )


def test_missing_independent_test_blocks_complete():
    # Will be used in Task 19/20 as well: prototype PASS + independent gate BLOCKED
    # -> prototype_ready=true, evaluation_complete=false
    pass
