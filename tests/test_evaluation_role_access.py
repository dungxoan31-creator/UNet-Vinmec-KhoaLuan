import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import get_current_user
from backend.db.database import UserModel

client = TestClient(app)


@pytest.fixture
def evaluation_role():
    def set_role(role):
        app.dependency_overrides[get_current_user] = lambda: UserModel(
            id=f"evaluation-{role.lower()}",
            username=f"evaluation_{role.lower()}",
            full_name="Synthetic evaluation user",
            role=role,
            facility_id="FAC-DEFAULT-TEST",
        )

    original = app.dependency_overrides.get(get_current_user)
    try:
        yield set_role
    finally:
        if original is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = original


def test_evaluation_metrics_require_authentication(evaluation_role):
    app.dependency_overrides.pop(get_current_user, None)

    response = client.get("/api/evaluation/metrics")

    assert response.status_code == 401


def test_senior_reviewer_can_read_metrics_but_legacy_samples_remain_blocked(evaluation_role):
    evaluation_role("SENIOR")

    metrics = client.get("/api/evaluation/metrics")
    samples = client.get("/api/evaluation/samples?limit=10")

    assert metrics.status_code == 200
    assert samples.status_code == 503
    assert "provenance" in samples.json()["detail"].lower()


@pytest.mark.parametrize("role", ["DOCTOR", "ADMIN", "TECHNICIAN"])
def test_non_reviewer_roles_cannot_read_evaluation_or_samples(evaluation_role, role):
    evaluation_role(role)

    metrics = client.get("/api/evaluation/metrics")
    samples = client.get("/api/evaluation/samples?limit=10")

    assert metrics.status_code == 403
    assert samples.status_code == 403
