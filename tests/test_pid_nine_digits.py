import pytest
from pydantic import ValidationError
from backend.schemas.schemas import CreateCaseRequest


@pytest.mark.parametrize('pid', ['123456789', '000000001', '900000300'])
def test_pid_exactly_nine_ascii_digits(pid):
    assert CreateCaseRequest(patient_id=pid, study_date='2026-11-02').patient_id == pid


@pytest.mark.parametrize('pid', ['', '12345678', '1234567890', '12345678a', ' 123456789', '123456789 ', '１２３４５６７８９', 123456789])
def test_invalid_pid_rejected(pid):
    with pytest.raises(ValidationError):
        CreateCaseRequest(patient_id=pid, study_date='2026-11-02')


def test_pid_is_optional_for_deidentified_research():
    assert CreateCaseRequest(study_date='2026-11-02').patient_id is None
    assert CreateCaseRequest(patient_id=None, study_date='2026-11-02').patient_id is None
