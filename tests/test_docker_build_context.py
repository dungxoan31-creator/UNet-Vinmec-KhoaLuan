import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_docker_build_context_excludes_source_data_and_runtime_artifacts():
    excluded = {
        line.strip()
        for line in (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {"dataset/", "ai_training/", "checkpoints/", "evaluation/"} <= excluded


def test_compose_mounts_runtime_artifacts_that_are_not_baked_into_the_image():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "COPY checkpoints/" not in dockerfile
    assert "COPY evaluation/" not in dockerfile
    assert "./checkpoints:/app/checkpoints:ro" in compose
    assert "./evaluation:/app/evaluation:ro" in compose


def test_dockerfile_copy_sources_exist_in_the_build_context():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    sources = [
        source
        for line in dockerfile.splitlines()
        if line.strip().startswith("COPY ")
        for source in line.split()[1:-1]
    ]

    assert sources
    assert all((PROJECT_ROOT / source).exists() for source in sources)


def test_http_access_logs_do_not_record_query_values():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    launcher = (PROJECT_ROOT / "scripts" / "run_prototype.ps1").read_text(encoding="utf-8")
    nginx = (PROJECT_ROOT / "nginx.conf").read_text(encoding="utf-8")
    isolated_server = (PROJECT_ROOT / "tests" / "serve_isolated_app.py").read_text(encoding="utf-8")

    assert "--no-access-log" in dockerfile
    assert "--no-access-log" in launcher
    assert "access_log=False" in isolated_server
    match = re.search(r"log_format\s+privacy_safe\s+(.+?);", nginx, re.DOTALL)
    assert match is not None
    log_format = match.group(1)
    variables = set(re.findall(r"\$[A-Za-z0-9_]+", log_format))
    assert "$uri" in variables
    assert "$request" not in variables
    assert "$args" not in variables
    assert "$http_referer" not in variables
    assert "access_log /var/log/nginx/access.log privacy_safe;" in nginx


def test_docker_uvicorn_bind_uses_the_host_checked_by_synthetic_demo_startup():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    normalized = re.sub(r"\s+", " ", dockerfile.replace("\\\n", " "))
    command_line = next(line.strip() for line in dockerfile.splitlines() if line.strip().startswith("CMD ["))
    command = json.loads(command_line.removeprefix("CMD "))

    assert "HOST=0.0.0.0" in normalized
    assert command[:2] == ["sh", "-c"]
    assert '--host "$HOST"' in command[2]
    assert '--port "$PORT"' in command[2]


def test_docker_image_installs_the_cpu_pytorch_pair_from_the_official_index():
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    normalized = re.sub(r"\s+", " ", dockerfile.replace("\\\n", " "))

    assert (
        "--index-url https://download.pytorch.org/whl/cpu "
        "torch==2.8.0 torchvision==0.23.0"
    ) in normalized


def test_docker_lock_is_transitive_and_contains_runtime_imports_only():
    requirements = [
        line.strip()
        for line in (PROJECT_ROOT / "requirements-lock.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    packages = {
        re.sub(r"[-_.]+", "-", line.partition("==")[0]).lower()
        for line in requirements
        if "==" in line
    }
    runtime = {
        "torch",
        "torchvision",
        "opencv-python-headless",
        "numpy",
        "pillow",
        "pydicom",
        "fastapi",
        "uvicorn",
        "pydantic",
        "sqlalchemy",
        "pyjwt",
        "reportlab",
        "segmentation-models-pytorch",
        "python-multipart",
    }
    training_and_test_only = {
        "albumentations",
        "alembic",
        "httpx",
        "matplotlib",
        "monai",
        "nibabel",
        "pandas",
        "pytest",
        "pytest-asyncio",
        "python-docx",
        "ruff",
        "scikit-image",
        "scikit-learn",
        "scipy",
        "simpleitk",
    }

    assert requirements
    assert all("==" in requirement for requirement in requirements)
    assert runtime <= packages
    assert not (training_and_test_only & packages)

    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY requirements-lock.txt /app/" in dockerfile
    assert "COPY requirements.txt" not in dockerfile
