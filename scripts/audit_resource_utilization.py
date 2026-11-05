"""Read-only source/import/resource inventory; reachability is not runtime proof."""

import ast
import hashlib
import importlib.metadata
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/resource_audit"
SOURCE_ROOTS = {"backend", "frontend", "ai_training", "evaluation", "scripts", "deploy"}
EXCLUDED = {"archive", "archive_milestone_1", "__pycache__", "node_modules", ".venv"}
EXTENSIONS = {".py", ".js", ".mjs", ".cjs", ".html", ".css", ".sql", ".ps1", ".yml", ".yaml", ".toml", ".conf", ".service"}
ROOT_CONFIG = {"Dockerfile", ".dockerignore", "docker-compose.yml", "docker-compose.postgres.yml", "nginx.conf",
               "requirements.txt", "requirements-lock.txt", "pyproject.toml", "package.json"}


def main():
    names = subprocess.check_output(["rg", "--files", "--hidden", "-g", "!.git", "-g", "!.venv",
                                     "-g", "!node_modules", "-g", "!artifacts", "-g", "!.tmp*"], cwd=ROOT, text=True).splitlines()
    paths = sorted(Path(name.replace("\\", "/")) for name in names
                   if (name in ROOT_CONFIG or (Path(name).parts[0] in SOURCE_ROOTS and Path(name).suffix in EXTENSIONS))
                   and not any(part in EXCLUDED for part in Path(name).parts))
    sources = {path.as_posix(): (ROOT / path).read_text(encoding="utf-8-sig") for path in paths}
    modules = {path[:-3].replace("/", "."): path for path in sources if path.endswith(".py")}
    modules.update({name.removesuffix(".__init__"): path for name, path in list(modules.items())
                    if name.endswith(".__init__")})
    edges = defaultdict(set)
    importers = defaultdict(set)
    routes, errors, signals = [], [], []
    resources = []
    for path, source in sources.items():
        if path.endswith(".py"):
            try:
                tree = ast.parse(source)
                current = path[:-3].replace("/", ".").split(".")
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        imports = [alias.name for alias in node.names]
                        for name in imports:
                            importers[name.split(".")[0]].add(path)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and not node.level:
                            importers[node.module.split(".")[0]].add(path)
                        parent = ".".join(current[:-node.level]) if node.level else ""
                        base = ".".join(filter(None, [parent, node.module]))
                        imports = [base] + [f"{base}.{alias.name}" for alias in node.names]
                    else:
                        imports = []
                    edges[path].update(modules[name] for name in imports if name in modules)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for dec in node.decorator_list:
                            if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                                    and dec.func.attr in {"get", "post", "put", "patch", "delete", "websocket"}):
                                route = ast.literal_eval(dec.args[0]) if dec.args and isinstance(dec.args[0], ast.Constant) else None
                                routes.append({"file": path, "line": node.lineno, "method": dec.func.attr,
                                               "declared_path": route, "handler": node.name,
                                               "runtime_verified": False})
            except SyntaxError as exc:
                errors.append({"path": path, "line": exc.lineno, "error": exc.msg})
        if path.endswith((".js", ".mjs", ".cjs", ".html", ".css")):
            for match in re.finditer(r'''(?:from\s*|import\s*|src=|href=|url\(|new URL\(|new Worker\()\s*["']([^"']+)["']''', source):
                ref = match[1].split("?")[0]
                target = ((ROOT / path).parent / ref).resolve() if ref.startswith(".") else ROOT / "frontend" / ref.removeprefix("/static/")
                if target.is_relative_to(ROOT) and target.relative_to(ROOT).as_posix() in sources:
                    edges[path].add(target.relative_to(ROOT).as_posix())
        for number, line in enumerate(source.splitlines(), 1):
            if re.search(r"\bTODO\b|\bFIXME\b|NotImplementedError|status_code=501", line):
                signals.append({"file": path, "line": number, "review": "stub/guard signal; requires manual interpretation"})

    def reachable(entry):
        seen, queue = set(), [entry]
        while queue:
            item = queue.pop()
            if item not in seen:
                seen.add(item)
                queue.extend(edges[item])
        return seen

    production = reachable("backend/app/main.py") | reachable("frontend/index.html") | reachable("frontend/app/main.js")
    inbound = defaultdict(list)
    for origin, destinations in edges.items():
        for destination in destinations:
            inbound[destination].append(origin)
    for path, source in sources.items():
        role = "runtime_config" if path in ROOT_CONFIG else path.split("/")[0]
        # Category 6 deliberately leaves runtime claims unassigned. The manually
        # verified subsystem matrix is authoritative for categories 1–5.
        resources.append({
            "path": path, "lines": len(source.splitlines()),
            "sha256": hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
            "source_role": role, "static_product_reachable": path in production,
            "imported_by": sorted(inbound[path]), "imports": sorted(edges[path]),
            "classification": "6: potential value; manual subsystem classification in report",
            "runtime_verified": False,
            "integration_evidence": "static import/asset graph only; conditional imports may be disabled at runtime",
        })
    hashes = defaultdict(list)
    for resource in resources:
        hashes[resource["sha256"]].append(resource["path"])
    duplicates = [group for group in hashes.values() if len(group) > 1]
    dependencies = []
    distribution_modules = {
        "opencv-python-headless": "cv2", "scikit-image": "skimage", "scikit-learn": "sklearn",
        "segmentation-models-pytorch": "segmentation_models_pytorch", "simpleitk": "SimpleITK",
        "python-multipart": "multipart", "SQLAlchemy": "sqlalchemy", "PyJWT": "jwt",
        "pillow": "PIL", "python-docx": "docx", "Jinja2": "jinja2",
    }
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        name = re.split(r"[<>=!~\[]", line.strip())[0]
        if not name or name.startswith("#"):
            continue
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        dependencies.append({"requirement": line, "installed_version": installed,
                             "static_source_importers": sorted(importers[distribution_modules.get(name, name.replace("-", "_"))]),
                             "usage_limit": "No direct import is not proof of non-use: CLI, framework plugins and transitive requirements remain relevant",
                             "presence_proves_functionality": False})
    checkpoints = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                    "verified_by_this_scan": False}
                   for path in sorted((ROOT / "checkpoints").rglob("*")) if path.suffix in {".pth", ".pt"}]
    result = {"scope": "static production/research/deployment source inventory; excludes historical archives and generated artifacts",
              "limitations": "Not a call graph, runtime coverage or external license validation. Dynamic routing/imports may be missed.",
              "summary": {"files": len(resources), "lines": sum(r["lines"] for r in resources),
                          "static_product_reachable": len(production), "declared_routes": len(routes),
                          "files_by_role": dict(Counter(r["source_role"] for r in resources))},
              "resources": resources, "declared_routes": routes, "stub_signals": signals,
              "parse_errors": errors, "exact_duplicate_sources": duplicates,
              "python_dependencies": dependencies, "checkpoint_files": checkpoints}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "resource_inventory.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    print(f"Parse errors: {len(errors)}; exact duplicate groups: {len(duplicates)}")


if __name__ == "__main__":
    main()
