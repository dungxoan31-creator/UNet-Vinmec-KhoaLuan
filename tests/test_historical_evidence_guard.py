"""Historical M1 claims must not be regenerated as current clinical evidence."""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.database import Base
try:
    from scripts.export_milestone_1_report import build_full_report
except ImportError:
    build_full_report = None

try:
    from scripts.generate_humanized_docx_report import create_report
except ImportError:
    create_report = None


@pytest.mark.parametrize("generate", [build_full_report, create_report])
def test_historical_m1_generators_refuse_unverified_regeneration(generate, tmp_path, monkeypatch):
    if generate is None:
        pytest.skip("Historical report generator has been removed from workspace.")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="unverified.*Patient|Patient.*unverified"):
        generate()
    assert list(tmp_path.iterdir()) == []


def test_admin_export_does_not_count_historical_claims_as_verified():
    from backend.app.routers.admin import export_ground_truth_dataset, get_doctor_productivity_stats

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            payload = json.loads(export_ground_truth_dataset(db).body)
            doctors = get_doctor_productivity_stats(db)
        assert payload["total_cases_cataloged"] == 0
        assert payload["total_verified_ground_truth"] == 0
        assert doctors == []
    finally:
        engine.dispose()
