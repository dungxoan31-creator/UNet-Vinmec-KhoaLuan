import os
os.environ.setdefault("APP_JWT_SECRET", "test-secret-at-least-32-chars-long-12345")

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers import cases as cases_router_module
from backend.app.security import create_access_token, hash_password
from backend.db.database import (
    FacilityModel,
    ImageModel,
    PatientModel,
    SessionLocal,
    StudyModel,
    UserModel,
)
from backend.schemas.schemas import CaseImageSummary, CaseItem, WorkspaceCaseSearchResponse


@pytest.fixture
def r4_test_env():
    test_db = SessionLocal()
    prefix = uuid.uuid4().hex[:6]

    fac = FacilityModel(
        id=f"fac-{prefix}",
        facility_code=f"F-{prefix}".upper(),
        name=f"Hospital {prefix}",
        is_active=True,
    )
    test_db.add(fac)

    doc = UserModel(
        id=str(uuid.uuid4()),
        username=f"doc_{prefix}",
        full_name="Dr. R4 Tester",
        role="DOCTOR",
        facility_id=fac.id,
        password_hash=hash_password("DocPass123!"),
        is_active=True,
    )
    test_db.add(doc)

    study = StudyModel(
        id=str(uuid.uuid4()),
        study_code=f"STU-{prefix}",
        study_date="2026-10-31",
        status="PENDING",
        ovary_side="LEFT",
        contralateral_status="NORMAL",
        facility_id=fac.id,
    )
    test_db.add(study)

    img = ImageModel(
        id=str(uuid.uuid4()),
        study_id=study.id,
        filename=f"img_{prefix}.png",
        raw_path=f"data/test_{prefix}.png",
        laterality="L",
    )
    test_db.add(img)
    test_db.commit()

    token = create_access_token({"sub": doc.username, "uid": doc.id})
    client = TestClient(app)

    try:
        yield {
            "client": client,
            "fac": fac,
            "doc": doc,
            "study": study,
            "image": img,
            "token": token,
            "headers": {
                "Authorization": f"Bearer {token}",
            },
            "db": test_db,
            "prefix": prefix,
        }
    finally:
        test_db.close()


def test_case_item_schema_fields():
    """Verify CaseItem schema has all R4 fields and validates properly."""
    img_summary = CaseImageSummary(
        id="img-1",
        filename="scan1.png",
        laterality="RIGHT",
    )
    item_data = {
        "id": "stu-1",
        "study_id": "stu-1",
        "study_code": "STU-001",
        "visit_no": "V-01",
        "patient_id": None,
        "patient_age": "30-39",
        "study_date": "2026-10-31",
        "status": "PENDING",
        "ovary_side": "RIGHT",
        "contralateral_status": "NORMAL",
        "images": [img_summary],
        "image_id": "img-1",
        "image_filename": "scan1.png",
        "lesion_type": "Cystic",
        "max_diameter_mm": 24.5,
        "doctor_action": None,
        "created_at": "31/10/2026 10:00",
    }
    case_item = CaseItem.model_validate(item_data)
    assert case_item.study_id == "stu-1"
    assert case_item.patient_id is None
    assert case_item.patient_age == "30-39"
    assert len(case_item.images) == 1
    assert case_item.images[0].id == "img-1"
    assert case_item.max_diameter_mm == 24.5


def test_router_response_models_registered():
    """Verify router endpoints have response_model set to CaseItem contracts."""
    routes = {
        (route.path, tuple(route.methods)): route
        for route in cases_router_module.router.routes
    }

    get_cases_route = routes.get(("/api/cases", ("GET",)))
    assert get_cases_route is not None
    assert get_cases_route.response_model == list[CaseItem]

    post_cases_search_route = routes.get(("/api/cases/search", ("POST",)))
    assert post_cases_search_route is not None
    assert post_cases_search_route.response_model == list[CaseItem]

    post_workspace_search_route = routes.get(("/api/workspace/cases/search", ("POST",)))
    assert post_workspace_search_route is not None
    assert post_workspace_search_route.response_model in (
        WorkspaceCaseSearchResponse,
        list[CaseItem],
    ) or getattr(post_workspace_search_route.response_model, "__origin__", None) is not None


def test_get_cases_contract(r4_test_env):
    """GET /api/cases returns list conforming to CaseItem contract."""
    client = r4_test_env["client"]
    resp = client.get("/api/cases", headers=r4_test_env["headers"])
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    item = next((c for c in data if c["id"] == r4_test_env["study"].id), None)
    assert item is not None
    validated = CaseItem.model_validate(item)
    assert validated.study_id == r4_test_env["study"].id
    assert validated.patient_id is None
    assert len(validated.images) >= 1
    assert validated.images[0].id == r4_test_env["image"].id


def test_search_cases_contract(r4_test_env):
    """POST /api/cases/search returns list conforming to CaseItem contract."""
    client = r4_test_env["client"]
    resp = client.post(
        "/api/cases/search",
        headers=r4_test_env["headers"],
        json={"limit": 10},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    item = next((c for c in data if c["id"] == r4_test_env["study"].id), None)
    assert item is not None
    validated = CaseItem.model_validate(item)
    assert validated.study_id == r4_test_env["study"].id
    assert validated.study_code == r4_test_env["study"].study_code


def test_workspace_cases_search_contract(r4_test_env):
    """POST /api/workspace/cases/search returns paginated structure with items matching CaseItem."""
    client = r4_test_env["client"]
    resp = client.post(
        "/api/workspace/cases/search",
        headers=r4_test_env["headers"],
        json={"limit": 10},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert isinstance(data["total"], int)
    assert data["total"] >= 1

    item = next((c for c in data["items"] if c["id"] == r4_test_env["study"].id), None)
    assert item is not None
    validated = CaseItem.model_validate(item)
    assert validated.study_id == r4_test_env["study"].id
    assert len(validated.images) >= 1
