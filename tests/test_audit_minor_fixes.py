"""Regression tests for audit fixes - MINOR issues."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.routers.auth import create_access_token
from backend.db.database import Base, UserModel, get_db


def test_be_24_create_user_empty_payload_rejects_with_422(tmp_path, monkeypatch):
    """BE-24: Creating user with empty payload or blank username must return HTTP 422, not HTTP 200 SUCCESS."""
    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-long-random-string-for-minor-fixes-123456")
    db_file = tmp_path / "be24.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        admin = UserModel(
            id="admin-be24",
            username="admin_be24",
            full_name="Admin Test",
            role="ADMIN",
            password_hash="fakehash",
            is_active=True,
        )
        session.add(admin)
        session.commit()

    token = create_access_token({"sub": "admin_be24", "uid": "admin-be24", "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    def override_get_db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)

        # Empty body
        res = client.post("/api/admin/users", json={}, headers=headers)
        assert res.status_code == 422, f"BE-24 VULNERABILITY: Empty payload returned {res.status_code} instead of 422!"
        assert "không được để trống" in res.json().get("detail", "")

        # Blank username
        res2 = client.post("/api/admin/users", json={"username": "   "}, headers=headers)
        assert res2.status_code == 422
        assert "không được để trống" in res2.json().get("detail", "")

        # Verify no users were created
        with Session(engine) as s:
            assert s.query(UserModel).count() == 1  # Only the admin
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_be_11_audit_events_export_endpoint(tmp_path, monkeypatch):
    """BE-11: UI calls /api/admin/audit-events/export which must exist, require admin, and return filtered export data."""
    from datetime import datetime

    from backend.db.database import AuditLogModel

    monkeypatch.setenv("APP_JWT_SECRET", "test-secret-long-random-string-for-minor-fixes-123456")
    db_file = tmp_path / "be11.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        admin = UserModel(
            id="admin-be11",
            username="admin_be11",
            full_name="Admin Test",
            role="ADMIN",
            password_hash="fakehash",
            is_active=True,
        )
        session.add(admin)
        log1 = AuditLogModel(
            id=1,
            timestamp=datetime(2026, 10, 18, 10, 0, 0),
            actor_id="admin_be11",
            action_type="LOGIN",
            entity_name="user",
            entity_id="admin-be11",
            details="Admin login",
        )
        log2 = AuditLogModel(
            id=2,
            timestamp=datetime(2026, 10, 18, 11, 0, 0),
            actor_id="dr_dung",
            action_type="SIGN_PRELIM",
            entity_name="study",
            entity_id="study-123",
            details="Review signed",
        )
        session.add_all([log1, log2])
        session.commit()

    admin_token = create_access_token({"sub": "admin_be11", "uid": "admin-be11", "role": "ADMIN"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    def override_get_db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)

        # 1. Unauthenticated request must be rejected 401
        unauth_res = client.get("/api/admin/audit-events/export")
        assert unauth_res.status_code == 401

        # 2. Authenticated export request must return 200 with items
        res = client.get("/api/admin/audit-events/export", headers=admin_headers)
        assert res.status_code == 200, f"BE-11 VULNERABILITY: /api/admin/audit-events/export returned {res.status_code}!"
        data = res.json()
        assert "items" in data
        assert len(data["items"]) == 2
        item = data["items"][0]
        assert "timestamp" in item
        assert "actor_id" in item
        assert "action_type" in item
        assert "entity_id" in item

        # 3. Filtered export by action
        res_filtered = client.get("/api/admin/audit-events/export?action=LOGIN", headers=admin_headers)
        assert res_filtered.status_code == 200
        filtered_items = res_filtered.json()["items"]
        assert len(filtered_items) == 1
        assert filtered_items[0]["action_type"] == "LOGIN"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_demo_01_report_generator_removes_hardcoded_placeholders():
    """DEMO-01: Report generator must require mandatory patient ID and must NOT fill fake patient identity, fake D1/D2/area measurements, or fake O-RADS 2 conclusions."""
    import pytest

    from backend.services.report_generator import MedicalReportGenerator

    generator = MedicalReportGenerator()

    # 1. Missing patient identifier must raise ValueError
    with pytest.raises(ValueError, match="mã định danh bệnh nhân"):
        generator._normalize_report_data({})

    # 2. When patient ID is provided but other clinical fields are empty, no hardcoded clinical placeholders may appear
    norm = generator._normalize_report_data({"patientId": "BN-TEST-001"})
    assert norm["patientId"] == "BN-TEST-001"

    # Must NOT contain hardcoded patient or doctor names
    assert norm["patientName"] != "Nguyễn Thị Phượng", "DEMO-01 VULNERABILITY: Hardcoded patient name used as fallback!"
    assert "Trương Thị Phượng" not in norm.get("doctorName", "")
    assert "Lê Khắc Hiếu" not in norm.get("referringDoctor", "")

    # Must NOT invent measurements D1=28.5, D2=21.0, area=4.62
    conc1 = norm.get("conclusion_l1", "")
    ovary_r3 = norm.get("ovary_r3", "")
    assert "28.5" not in ovary_r3, "DEMO-01 VULNERABILITY: Hardcoded D1=28.5 used as fallback!"
    assert "21" not in ovary_r3, "DEMO-01 VULNERABILITY: Hardcoded D2=21 used as fallback!"
    assert "4.62" not in ovary_r3, "DEMO-01 VULNERABILITY: Hardcoded area=4.62 used as fallback!"

    # Must NOT invent O-RADS 2 classification or 3-month follow-up without clinical input
    assert "O-RADS 2" not in conc1, "DEMO-01 VULNERABILITY: Hardcoded O-RADS 2 conclusion used as fallback!"
    assert "3 THÁNG" not in norm.get("conclusion_l2", ""), "DEMO-01 VULNERABILITY: Hardcoded 3-month recall used as fallback!"


def test_fe_04_viewer_readonly_and_lease_loss_guard_blocks_clinical_mutation():
    """FE-04: Viewer clinical controls must enforce readonly and editing.allowed guards, and lease loss must disable selectors."""
    from pathlib import Path

    viewer_js = Path("frontend/app/viewer.js").read_text(encoding="utf-8")

    # 1. handleIota and handleOrads must guard against !state.editing?.allowed
    assert "!state.editing?.allowed" in viewer_js, "FE-04 VULNERABILITY: Clinical input handlers missing editing.allowed guard!"

    # 2. window.addEventListener("ova:lease-lost") must disable iotaMorphology and oradsScore
    assert 'if ($("#iotaMorphology")) $("#iotaMorphology").disabled = true;' in viewer_js, (
        "FE-04 VULNERABILITY: lease-lost listener does not disable iotaMorphology!"
    )
    assert 'if ($("#oradsScore")) $("#oradsScore").disabled = true;' in viewer_js, (
        "FE-04 VULNERABILITY: lease-lost listener does not disable oradsScore!"
    )


def test_ops_04_security_headers_present():
    """OPS-04: Responses must contain Content-Security-Policy and X-Content-Type-Options: nosniff headers."""
    from fastapi.testclient import TestClient

    from backend.app.main import app

    client = TestClient(app)
    response = client.get("/")

    # Must include Content-Security-Policy
    csp = response.headers.get("content-security-policy", "")
    assert csp, "OPS-04 VULNERABILITY: Missing Content-Security-Policy header in response!"
    assert "default-src 'self'" in csp, "OPS-04 VULNERABILITY: CSP missing default-src 'self' directive!"
    assert "object-src 'none'" in csp, "OPS-04 VULNERABILITY: CSP missing object-src 'none' directive!"

    # Must include X-Content-Type-Options: nosniff
    assert response.headers.get("x-content-type-options") == "nosniff", (
        "OPS-04 VULNERABILITY: Missing or invalid X-Content-Type-Options header!"
    )

    # Must include X-Frame-Options
    assert response.headers.get("x-frame-options") in ("DENY", "SAMEORIGIN"), (
        "OPS-04 VULNERABILITY: Missing or invalid X-Frame-Options header!"
    )


def test_fe_07_banner_info_contrast_meets_wcag_aa():
    """FE-07: Informational banner (.banner.info) text contrast must strictly satisfy WCAG AA >= 4.5:1."""
    import re
    from pathlib import Path

    css_text = Path("frontend/css/workspace.css").read_text(encoding="utf-8")
    tokens_text = Path("frontend/css/workspace-tokens.css").read_text(encoding="utf-8")

    assert "--accent-text: #0062a1;" in tokens_text, "FE-07: Light theme --accent-text token modified!"
    assert "--accent-text: #38bdf8;" in tokens_text, "FE-07: Dark theme --accent-text token modified!"

    # .banner.info must use --accent-text rather than --accent to ensure >= 4.5:1 contrast
    match = re.search(r"\.banner\.info\s*\{[^}]*color:\s*var\(--accent-text\)", css_text)
    assert match, "FE-07 VULNERABILITY: .banner.info does not use var(--accent-text) for accessible contrast!"

    # Calculate exact contrast ratios for light theme
    def lum(rgb):
        adj = [(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4) for c in rgb]
        return 0.2126 * adj[0] + 0.7152 * adj[1] + 0.0722 * adj[2]

    # Light: bg #e8f4fc vs text #0062a1
    l_bg = lum([int("e8f4fc"[i : i + 2], 16) / 255.0 for i in (0, 2, 4)])
    l_text = lum([int("0062a1"[i : i + 2], 16) / 255.0 for i in (0, 2, 4)])
    light_ratio = (max(l_bg, l_text) + 0.05) / (min(l_bg, l_text) + 0.05)
    assert light_ratio >= 4.5, f"FE-07 VULNERABILITY: Light banner contrast {light_ratio:.2f} < 4.5:1!"


def test_dep_06_to_12_build_toolchain_security_boundaries():
    """DEP-06..12: Build toolchain advisories must be pinned to safe versions and unexposed at HTTP runtime."""
    from pathlib import Path

    lock_content = Path("requirements-lock.txt").read_text(encoding="utf-8")
    docker_content = Path("Dockerfile").read_text(encoding="utf-8")

    # 1. requirements-lock.txt must specify pip>=26.2 and setuptools>=78.1.1
    assert "pip>=26.2" in lock_content, "DEP-06..11 VULNERABILITY: requirements-lock.txt missing safe pip>=26.2 pin!"
    assert "setuptools>=78.1.1" in lock_content, "DEP-12 VULNERABILITY: requirements-lock.txt missing safe setuptools>=78.1.1 pin!"

    # 2. Dockerfile must explicitly upgrade build toolchain
    assert "pip>=26.2" in docker_content, "DEP-06..11 VULNERABILITY: Dockerfile does not upgrade pip to >=26.2!"
    assert "setuptools>=78.1.1" in docker_content, "DEP-12 VULNERABILITY: Dockerfile does not upgrade setuptools to >=78.1.1!"


def test_qa_02_static_type_check_configured():
    """QA-02: Project must configure static type-checking pipeline across frontend and backend boundaries."""
    import json
    from pathlib import Path

    # 1. package.json must define "type-check" script
    pkg_path = Path("package.json")
    assert pkg_path.exists(), "QA-02: Missing package.json!"
    pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
    scripts = pkg_data.get("scripts", {})
    assert "type-check" in scripts, "QA-02 VULNERABILITY: package.json missing 'type-check' script!"

    # 2. scripts/type_check.js must exist and be executable
    type_check_script = Path("scripts/type_check.js")
    assert type_check_script.exists(), "QA-02 VULNERABILITY: Missing scripts/type_check.js runner!"

    # 3. pyproject.toml must have static type check configuration
    pyproject_text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.mypy]" in pyproject_text, "QA-02 VULNERABILITY: pyproject.toml missing [tool.mypy] section!"



