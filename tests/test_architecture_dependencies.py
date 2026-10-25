import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_service_modules_do_not_import_the_application_layer():
    offenders = []
    for path in sorted((ROOT / "backend" / "services").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("backend.app"):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}: {node.module}")
            elif isinstance(node, ast.Import):
                offenders.extend(
                    f"{path.relative_to(ROOT)}:{node.lineno}: {alias.name}"
                    for alias in node.names
                    if alias.name.startswith("backend.app")
                )

    assert offenders == [], "Service modules must not import the application layer: " + ", ".join(offenders)
