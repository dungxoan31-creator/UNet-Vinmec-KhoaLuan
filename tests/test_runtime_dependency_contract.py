import re
from pathlib import Path


def _minimum_version(package_name: str) -> tuple[int, ...]:
    requirements = Path("requirements.txt").read_text(encoding="utf-8").splitlines()
    pattern = re.compile(
        rf"^{re.escape(package_name)}\s*>=\s*(\d+(?:\.\d+)+)(?:\s|$)",
        re.IGNORECASE,
    )
    versions = [
        tuple(int(part) for part in match.group(1).split("."))
        for line in requirements
        if (match := pattern.match(line.strip()))
    ]
    assert len(versions) == 1, f"Expected one explicit minimum for {package_name}."
    return versions[0]


def _locked_version(package_name: str) -> tuple[int, ...]:
    lock = Path("requirements-lock.txt").read_text(encoding="utf-8").splitlines()
    pattern = re.compile(
        rf"^{re.escape(package_name)}==(?P<version>\d+(?:\.\d+)+)(?:\+cpu)?$", re.IGNORECASE
    )
    versions = [
        tuple(int(part) for part in match.group("version").split("."))
        for line in lock
        if (match := pattern.match(line.strip()))
    ]
    assert len(versions) == 1, f"Expected one exact lock pin for {package_name}."
    return versions[0]


def test_requirements_and_docker_lock_use_monai_compatible_pytorch_pair():
    assert _minimum_version("torch") >= (2, 8, 0)
    assert _minimum_version("torchvision") >= (0, 23, 0)
    assert _locked_version("torch") == (2, 8, 0)
    assert _locked_version("torchvision") == (0, 23, 0)


def test_clean_test_environment_declares_evaluation_import_dependencies():
    assert _minimum_version("matplotlib") >= (3, 8, 0)
    assert _minimum_version("python-docx") >= (1, 1, 0)


def test_project_declares_only_the_headless_opencv_wheel():
    requirements = Path("requirements.txt").read_text(encoding="utf-8").splitlines()

    assert _minimum_version("opencv-python-headless") >= (4, 8, 0)
    assert not any(
        re.match(r"^opencv-python\s*[<>=~]", line.strip(), re.IGNORECASE)
        for line in requirements
    )
