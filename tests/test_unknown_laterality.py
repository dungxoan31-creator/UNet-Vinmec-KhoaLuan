from backend.schemas.schemas import CreateCaseRequest


def test_case_can_record_unconfirmed_laterality():
    case = CreateCaseRequest(patient_id="TEST-CASE", active_ovary_side="UNKNOWN")
    assert case.active_ovary_side == "UNKNOWN"
