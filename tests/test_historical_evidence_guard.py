"""Historical M1 claims must not be regenerated as current clinical evidence."""

import importlib
import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.database import Base


@pytest.mark.parametrize(
    ("module_name", "symbol_name"),
    [
        ("scripts.export_milestone_1_report", "build_full_report"),
        ("scripts.generate_humanized_docx_report", "create_report"),
    ],
)
def test_historical_m1_generators_are_absent_or_refuse_unverified_regeneration(
    module_name, symbol_name, tmp_path, monkeypatch
):
    module_spec = importlib.util.find_spec(module_name)
    if module_spec is None:
        assert not (Path(__file__).resolve().parents[1] / Path(*module_name.split("."))).with_suffix(".py").exists()
        return

    module = importlib.import_module(module_name)
    generate = getattr(module, symbol_name, None)
    if generate is None:
        return

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
