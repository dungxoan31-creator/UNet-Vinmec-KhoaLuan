import pytest
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.schemas.schemas import VisitNumber
from backend.db.database import Base, StudyModel


@pytest.mark.parametrize('value', ['000001', '012345', '999999'])
def test_visit_number_preserves_six_digits(value):
    assert TypeAdapter(VisitNumber).validate_python(value) == value


@pytest.mark.parametrize('value', ['', '12345', '1234567', '12a456', '１２３４５６', ' 123456', 123456])
def test_visit_number_rejects_other_formats(value):
    with pytest.raises(ValidationError):
        TypeAdapter(VisitNumber).validate_python(value)


def test_bulk_auto_generation_300_visits(tmp_path):
    engine = create_engine('sqlite:///'+str(tmp_path/'synthetic.sqlite'))
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            rows = [StudyModel(id=f'synthetic-{i}', study_date='2026-11-02') for i in range(300)]
            db.add_all(rows)
            db.commit()
            numbers = [row.visit_no for row in rows]
            assert len(set(numbers)) == 300
            assert all(TypeAdapter(VisitNumber).validate_python(value) == value for value in numbers)
            assert numbers[0] == '000001' and numbers[-1] == '000300'
    finally:
        engine.dispose()
