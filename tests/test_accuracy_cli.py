"""The documented script-path commands must work from the repository root."""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "script",
    ("audit_milestone3_evidence.py", "evaluate_accuracy_candidates.py"),
)
def test_accuracy_scripts_accept_help_when_invoked_by_file_path(script):
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "scripts" / script), "--help"],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert "usage:" in completed.stdout
