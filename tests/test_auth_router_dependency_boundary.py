"""Keep shared auth dependencies out of endpoint router modules."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_routers_do_not_import_security_dependencies_from_auth_router():
    router_dir = ROOT / "backend" / "app" / "routers"
    modules = [*router_dir.glob("*.py"), ROOT / "backend" / "app" / "main.py"]
    violations = []

    for path in modules:
        if path.name in {"__init__.py", "auth.py"}:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "backend.app.routers.auth":
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}")

    assert violations == [], "Routers import shared auth/security functions from auth router: " + ", ".join(violations)


def test_auth_router_reexports_moved_helpers_for_existing_consumers():
    from backend.app import security
    from backend.app.routers import auth

    for name in (
        "get_current_user",
        "require_admin",
        "require_clinical",
        "hash_password",
        "verify_password",
        "create_access_token",
    ):
        assert getattr(auth, name) is getattr(security, name)
