"""Guard browser/API upload tests against reading source patient images."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPLOAD_TEST_SOURCES = (
    "tests/browser_hitl_smoke.js",
    "tests/clinical_roundtrip_e2e.js",
    "tests/clinical_safety_e2e.js",
    "tests/doctor_workflow_e2e.js",
    "tests/e2e/test_comprehensive_workstation.js",
    "tests/frontend_workflow_e2e.js",
    "tests/test_live_ui_features.js",
    "tests/workstation_viewer_e2e.js",
    "tests/test_vinmec_api_smoke.py",
    "tests/validation_files.cjs",
)
FORBIDDEN_SOURCE_PATHS = (
    "ai_training/splits",
    "SMOKE_VALIDATION_CSV",
    "dataset/Vinmec/Vinmec_2d/images",
    "dataset/2d/images",
)


def test_upload_e2e_sources_use_synthetic_fixtures_only():
    helper = (ROOT / "tests/helpers/synthetic_fixtures.cjs").read_text(encoding="utf-8")
    assert "artifacts" in helper
    assert "synthetic_fixtures" in helper
    assert "generate_synthetic_e2e_fixtures.py" in helper

    for relative_path in UPLOAD_TEST_SOURCES:
        source_path = ROOT / relative_path
        assert source_path.is_file(), f"Upload test source is missing: {relative_path}"
        source = source_path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_SOURCE_PATHS:
            assert forbidden not in source, (
                f"{relative_path} must not load source patient images via {forbidden!r}"
            )
