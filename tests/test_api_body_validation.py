from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.routers.auth import create_access_token, hash_password
from backend.db.database import Base, PatientModel, StudyModel, UserModel, get_db


@pytest.fixture
def authenticated_api(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_JWT_SECRET", "test-only-api-validation-signing-secret-123456")
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path))
    from backend.app.routers import admin as admin_router

    monkeypatch.setattr(admin_router, "_DEPARTMENTS", [{"id": "dep-test", "name": "Test", "code": "TEST", "members": 0}])
    monkeypatch.setattr(admin_router, "_ADMIN_SETTINGS", dict(admin_router._DEFAULT_ADMIN_SETTINGS))

    class CandidateRegistry:
        def __init__(self):
            self.adapters = {}

        def register_adapter(self, key, adapter):
            self.adapters[key] = adapter

        def save_persisted_candidates(self):
            return None

    monkeypatch.setattr(admin_router, "model_registry", CandidateRegistry())
    engine = create_engine(
        f"sqlite:///{tmp_path / 'api-validation.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                UserModel(
                    id="api-validation-admin",
                    username="api-validation-admin",
                    full_name="Admin",
                    role="ADMIN",
                    is_active=True,
                ),
                UserModel(
                    id="api-validation-doctor",
                    username="api-validation-doctor",
                    full_name="Doctor",
                    role="DOCTOR",
                    password_hash=hash_password("current-password"),
                    is_active=True,
                ),
            ]
        )
        db.commit()

    def temporary_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = temporary_db
    client = TestClient(app, raise_server_exceptions=False)
    admin = {
        "Authorization": "Bearer "
        + create_access_token({"sub": "api-validation-admin", "uid": "api-validation-admin"})
    }
    doctor = {
        "Authorization": "Bearer "
        + create_access_token({"sub": "api-validation-doctor", "uid": "api-validation-doctor"})
    }
    try:
        yield client, engine, admin, doctor
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()


def test_password_and_admin_user_endpoints_reject_wrong_field_types(authenticated_api):
    client, _, admin, doctor = authenticated_api

    change_password = client.post(
        "/api/auth/change-password",
        headers=doctor,
        json={"old_password": "current-password", "new_password": 12345678},
    )
    create_user = client.post(
        "/api/admin/users",
        headers=admin,
        json={"username": 123, "full_name": "New user"},
    )
    reset_password = client.post(
        "/api/admin/users/api-validation-doctor/reset-password",
        headers=admin,
        json={"new_password": 12345678},
    )
    update_user = client.patch(
        "/api/admin/users/api-validation-doctor",
        headers=admin,
        json={"full_name": ["Wrong", "type"]},
    )

    assert [
        change_password.status_code,
        create_user.status_code,
        reset_password.status_code,
        update_user.status_code,
    ] == [422, 422, 422, 422]


def test_login_and_registration_schemas_bound_credentials_and_reject_coercion(authenticated_api):
    from pydantic import ValidationError

    from backend.schemas.schemas import RegisterRequest

    client, _, _, _ = authenticated_api
    wrong_login_type = client.post(
        "/api/auth/login",
        json={"username": 12345, "password": "long-enough"},
    )
    oversized_login_secret = client.post(
        "/api/auth/login",
        json={"username": "api-validation-doctor", "password": "x" * 257},
    )
    assert wrong_login_type.status_code == 422
    assert oversized_login_secret.status_code == 422

    registration = {
        "username": "new-doctor",
        "password": "secure-password",
        "full_name": "New Doctor",
        "email": "new-doctor@example.org",
    }
    for invalid in (
        {**registration, "password": "x" * 257},
        {**registration, "username": "u" * 51},
        {**registration, "unexpected": "ignored fields are rejected"},
    ):
        with pytest.raises(ValidationError):
            RegisterRequest.model_validate(invalid)


def test_department_model_and_settings_endpoints_reject_invalid_contracts(authenticated_api):
    client, _, admin, _ = authenticated_api

    create_department = client.post(
        "/api/admin/departments",
        headers=admin,
        json={"id": "dep-invalid", "name": ["Wrong", "type"]},
    )
    update_department = client.patch(
        "/api/admin/departments/dep-test",
        headers=admin,
        json={"id": "dep-test", "name": None},
    )
    register_model = client.post(
        "/api/admin/models/register",
        headers=admin,
        json={"model_id": "candidate-invalid", "name": ["Wrong", "type"], "checkpoint": "candidate.pth"},
    )
    update_settings = client.put(
        "/api/admin/settings",
        headers=admin,
        json={"iqa_threshold": 0.4},
    )

    assert [
        create_department.status_code,
        update_department.status_code,
        register_model.status_code,
        update_settings.status_code,
    ] == [422, 422, 422, 422]


def test_candidate_metadata_can_be_removed_but_serving_models_are_protected(authenticated_api):
    client, _, admin, _ = authenticated_api
    from backend.app.routers import admin as admin_router

    registered = client.post(
        "/api/admin/models/register",
        headers=admin,
        json={"model_id": "candidate-to-remove", "name": "Research candidate", "artifact_id": "artifact-001"},
    )
    assert registered.status_code == 200

    removed = client.delete("/api/admin/models/candidate-to-remove", headers=admin)
    assert removed.status_code == 200
    assert "candidate-to-remove" not in admin_router.model_registry.adapters

    admin_router.model_registry.adapters["attention_unet"] = object()
    protected = client.delete("/api/admin/models/attention_unet", headers=admin)
    assert protected.status_code == 409


@pytest.mark.parametrize("unsupported_role", ["TK", "SECRETARY"])
@pytest.mark.parametrize("operation", ["create", "update"])
def test_admin_cannot_assign_roles_without_an_active_api_boundary(
    authenticated_api, unsupported_role, operation
):
    client, _, admin, _ = authenticated_api

    if operation == "create":
        response = client.post(
            "/api/admin/users",
            headers=admin,
            json={
                "username": f"unsupported-{unsupported_role.lower()}",
                "full_name": "Unavailable Role",
                "role": unsupported_role,
            },
        )
    else:
        response = client.patch(
            "/api/admin/users/nonexistent-user",
            headers=admin,
            json={"role": unsupported_role},
        )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "path",
    ["/api/cases", "/api/workspace/cases"],
)
@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "offset=10001"])
def test_case_list_rejects_out_of_range_pagination(authenticated_api, path, query):
    client, _, _, doctor = authenticated_api

    response = client.get(f"{path}?{query}", headers=doctor)

    assert response.status_code == 422


def test_case_list_defaults_to_bounded_pages_and_supports_offsets(authenticated_api):
    client, engine, _, doctor = authenticated_api
    with Session(engine) as db:
        patients = [
            PatientModel(id=f"page-patient-{index}", anonymized_pid=f"PAGE-PID-{index}")
            for index in range(101)
        ]
        studies = [
            StudyModel(
                id=f"page-study-{index}",
                patient_id=f"page-patient-{index}",
                study_code=f"PAGE-{index}",
                study_date="2026-10-21",
                created_at=datetime(2026, 10, 21, 12, 0),
            )
            for index in range(101)
        ]
        db.add_all(patients)
        db.add_all(studies)
        db.commit()

    first_page = client.get("/api/cases", headers=doctor)
    second_page = client.get("/api/cases?limit=100&offset=100", headers=doctor)

    assert first_page.status_code == second_page.status_code == 200
    assert len(first_page.json()) == 100
    assert len(second_page.json()) == 1
    assert [row["study_id"] for row in first_page.json() + second_page.json()] == sorted(
        (f"page-study-{index}" for index in range(101)), reverse=True
    )


def test_candidate_registration_rolls_back_when_metadata_cannot_be_saved(authenticated_api, monkeypatch):
    client, engine, admin, _ = authenticated_api
    from backend.app.routers import admin as admin_router
    from backend.db.database import AuditLogModel

    def fail_save():
        raise OSError("simulated candidate metadata storage failure")

    monkeypatch.setattr(admin_router.model_registry, "save_persisted_candidates", fail_save)
    response = client.post(
        "/api/admin/models/register",
        headers=admin,
        json={"model_id": "candidate-unsaved", "name": "Candidate", "artifact_id": "artifact-002"},
    )

    assert response.status_code == 500
    assert "candidate-unsaved" not in admin_router.model_registry.adapters
    with Session(engine) as db:
        assert db.query(AuditLogModel).filter_by(entity_id="candidate-unsaved").count() == 0


def test_admin_configuration_is_not_updated_when_atomic_save_fails(authenticated_api, monkeypatch):
    client, _, admin, _ = authenticated_api
    from backend.app.routers import admin as admin_router

    previous_settings = dict(admin_router._ADMIN_SETTINGS)
    previous_departments = [dict(department) for department in admin_router._DEPARTMENTS]

    def fail_replace(*_args):
        raise OSError("simulated configuration storage failure")

    monkeypatch.setattr(admin_router.os, "replace", fail_replace)
    settings = client.put(
        "/api/admin/settings",
        headers=admin,
        json={"report_header": "Must not be saved"},
    )
    department = client.post(
        "/api/admin/departments",
        headers=admin,
        json={"id": "dep-unsaved", "name": "Unsaved department", "code": "UNSAVED"},
    )

    assert settings.status_code == department.status_code == 500
    assert admin_router._ADMIN_SETTINGS == previous_settings
    assert admin_router._DEPARTMENTS == previous_departments


def test_department_codes_are_unique_and_missing_delete_is_404(authenticated_api):
    client, _, admin, _ = authenticated_api
    duplicate = client.post(
        "/api/admin/departments",
        headers=admin,
        json={"id": "dep-test", "name": "Duplicate", "code": "OTHER"},
    )
    missing = client.delete("/api/admin/departments/no-such-department", headers=admin)

    assert duplicate.status_code == 409
    assert missing.status_code == 404


def test_admin_model_overview_includes_stable_model_ids_and_candidate_status(monkeypatch):
    from backend.services.model_service import CandidateModelAdapter, ModelRegistry

    class ServingAdapter:
        is_loaded = False

        def get_info(self):
            return {"name": "Serving model", "is_loaded": False}

    registry = ModelRegistry.__new__(ModelRegistry)
    registry.adapters = {
        "attention_unet": ServingAdapter(),
        "candidate-research": CandidateModelAdapter(
            name="Research candidate", checkpoint="artifact-003"
        ),
    }
    registry.primary_model_key = "attention_unet"
    registry.ensemble_enabled = False
    monkeypatch.setattr(registry, "load_persisted_candidates", lambda: None)

    overview = registry.get_admin_overview()
    by_id = {model["model_id"]: model for model in overview["registered_models"]}

    assert by_id["attention_unet"]["is_candidate"] is False
    assert by_id["candidate-research"]["is_candidate"] is True
