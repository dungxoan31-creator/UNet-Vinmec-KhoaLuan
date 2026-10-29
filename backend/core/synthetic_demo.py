"""Fail-closed configuration for disposable, synthetic-only demonstrations."""

from __future__ import annotations

import hashlib
import ipaddress
import os
from pathlib import Path

_TRUE_VALUES = {"1", "true", "yes", "on"}
_ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".dcm"}
# Exact outputs of generate_synthetic_e2e_fixtures.py with its default seed.
# Never derive trusted content from names or hashes found in a runtime directory.
_TRUSTED_SYNTHETIC_FIXTURE_SHA256 = frozenset({
    "1599f902abc445b7c2ab897760ea7e7969bb3b675cc49ec48a840326b047596c",  # synthetic_left.jpg
    "e97ff9a1f4a184036e5a596ac8f95e7e46745fea16e9f34dca455667cee69f6d",  # synthetic_left.png
    "4f422963e577e48a8feeb26406f7a25334934b282f9579008916b6fa157bc17f",  # synthetic_letterbox_640x480.png
    "0bd98f53874ef9d8cdeebee600f88cf8b5c2a005d6f951bd614a239100d34404",  # synthetic_ovary.dcm
    "ac94ff3b1919720e2d27b83dd2830bd7ed19d7b52ad22e507ffbbbfc6b386ea3",  # synthetic_right.png
})


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def load_synthetic_demo_configuration(project_root: str | Path, data_dir: str | Path):
    """Return (enabled, allowlisted SHA-256 values); require a fresh local sandbox."""
    enabled = os.environ.get("APP_SYNTHETIC_DEMO_MODE", "").strip().lower() in _TRUE_VALUES
    if not enabled:
        return False, frozenset()

    if os.environ.get("DATABASE_URL"):
        raise RuntimeError("Synthetic demo mode requires the supported isolated SQLite database.")
    if not os.environ.get("APP_DATA_DIR") or not os.environ.get("APP_DB_PATH"):
        raise RuntimeError("Synthetic demo mode requires explicit APP_DATA_DIR and APP_DB_PATH paths.")
    if os.environ.get("HOST", "127.0.0.1").strip().lower() not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Synthetic demo mode may bind only to loopback.")
    if os.environ.get("APP_CORS_ORIGINS", "").strip():
        raise RuntimeError("Synthetic demo mode does not permit cross-origin access.")

    root = Path(project_root).resolve()
    data_root = Path(data_dir).resolve()
    configured_db = Path(os.environ["APP_DB_PATH"])
    db_path = configured_db.resolve() if configured_db.is_absolute() else (root / configured_db).resolve()
    if not _within(db_path, data_root) or db_path == data_root:
        raise RuntimeError("Synthetic demo database must be inside its isolated APP_DATA_DIR.")
    if data_root.exists() and any(data_root.iterdir()):
        raise RuntimeError("Synthetic demo mode requires a fresh, empty APP_DATA_DIR for every run.")

    configured_fixtures = os.environ.get("APP_SYNTHETIC_DEMO_FIXTURE_DIR", "").strip()
    if not configured_fixtures:
        raise RuntimeError("Synthetic demo mode requires APP_SYNTHETIC_DEMO_FIXTURE_DIR.")
    fixture_root = Path(configured_fixtures)
    if not fixture_root.is_absolute():
        fixture_root = root / fixture_root
    fixture_root = fixture_root.resolve()
    if not fixture_root.is_dir():
        raise RuntimeError("Synthetic demo fixture directory does not exist.")

    allowed_hashes = set()
    for fixture in fixture_root.iterdir():
        if not fixture.is_file() or not fixture.name.lower().startswith("synthetic_"):
            continue
        if fixture.suffix.lower() not in _ALLOWED_SUFFIXES:
            continue
        digest = hashlib.sha256()
        with fixture.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        fixture_hash = digest.hexdigest()
        if fixture_hash in _TRUSTED_SYNTHETIC_FIXTURE_SHA256:
            allowed_hashes.add(fixture_hash)
    if not allowed_hashes:
        raise RuntimeError("Synthetic demo mode found no verified synthetic image fixtures.")

    data_root.mkdir(parents=True, exist_ok=True)
    if any(data_root.iterdir()):
        raise RuntimeError("Synthetic demo mode requires a fresh, empty APP_DATA_DIR for every run.")
    lock_path = data_root / ".synthetic-demo.lock"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("Synthetic demo sandbox is already in use or was not cleaned after a prior run.") from exc
    with os.fdopen(lock_fd, "w", encoding="ascii") as lock_file:
        lock_file.write(f"pid={os.getpid()}\n")
    return True, frozenset(allowed_hashes)


def is_allowlisted_synthetic_upload(contents: bytes, allowed_hashes: frozenset[str]) -> bool:
    if not isinstance(contents, bytes):
        return False
    return hashlib.sha256(contents).hexdigest() in allowed_hashes


def is_loopback_client(remote_host: str | None) -> bool:
    if not remote_host:
        return False
    try:
        return ipaddress.ip_address(remote_host).is_loopback
    except ValueError:
        return remote_host.lower() == "localhost"
