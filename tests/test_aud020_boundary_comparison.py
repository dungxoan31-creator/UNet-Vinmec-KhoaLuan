import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "generate_boundary_comparison_report.py"


def test_boundary_report_compares_current_cdss_to_acr_without_patient_data(tmp_path):
    output = tmp_path / "aud020-boundary.csv"
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    with output.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))

    assert [row["diameter_mm"] for row in rows] == ["29.9", "30.0", "30.1"]
    assert (rows[0]["current_project_status"], rows[0]["current_project_category"]) == (
        "RULE_MATCHED",
        "O-RADS 1",
    )
    assert (rows[1]["current_project_status"], rows[1]["current_project_category"]) == (
        "UNSUPPORTED_PATTERN",
        "",
    )
    assert "≤3 cm" in rows[1]["acr_v2022_descriptor"]
    assert "morphology-based" in rows[2]["acr_v2022_descriptor"]
    assert "patient_id" not in rows[0]
    assert all(row["fixture_type"] == "synthetic_boundary_case_no_patient_data" for row in rows)


def test_boundary_report_refuses_to_overwrite_existing_output(tmp_path):
    output = tmp_path / "aud020-boundary.csv"
    output.write_text("preserve", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Refusing to overwrite" in result.stderr
    assert output.read_text(encoding="utf-8") == "preserve"
