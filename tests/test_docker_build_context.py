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
