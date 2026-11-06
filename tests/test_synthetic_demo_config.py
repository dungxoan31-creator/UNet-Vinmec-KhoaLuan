import hashlib

import pytest

from backend.core.synthetic_demo import is_loopback_client, load_synthetic_demo_configuration
from scripts.generate_synthetic_e2e_fixtures import generate_fixtures


@pytest.fixture(scope="session")
def verified_synthetic_fixture(tmp_path_factory):
    generated = generate_fixtures(tmp_path_factory.mktemp("verified-synthetic-fixtures"))
    return generated / "synthetic_left.png"


def _configure(monkeypatch, tmp_path, verified_fixture_bytes=None):
    data_dir = tmp_path / "runtime"
    data_dir.mkdir()
    fixture_dir = tmp_path / "fixtures"
    fixture_dir.mkdir()
    (fixture_dir / "synthetic_allowed.png").write_bytes(b"approved synthetic fixture bytes")
    if verified_fixture_bytes is not None:
        (fixture_dir / "synthetic_left.png").write_bytes(verified_fixture_bytes)
    (fixture_dir / "ordinary.png").write_bytes(b"not allowlisted by name")
    (fixture_dir / "synthetic_notes.txt").write_bytes(b"unsupported fixture type")
    monkeypatch.setenv("APP_SYNTHETIC_DEMO_MODE", "true")
    monkeypatch.setenv("APP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("APP_DB_PATH", str(data_dir / "sandbox.sqlite3"))
    monkeypatch.setenv("APP_SYNTHETIC_DEMO_FIXTURE_DIR", str(fixture_dir))
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("APP_CORS_ORIGINS", "")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    return data_dir, fixture_dir


def test_disabled_demo_mode_does_not_require_demo_configuration(monkeypatch, tmp_path):
    monkeypatch.delenv("APP_SYNTHETIC_DEMO_MODE", raising=False)
    assert load_synthetic_demo_configuration(tmp_path, tmp_path / "missing") == (False, frozenset())


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_demo_loopback_client_accepts_local_addresses(host):
    assert is_loopback_client(host) is True


@pytest.mark.parametrize("host", [None, "", "10.1.2.3", "203.0.113.5", "workstation.local"])
def test_demo_loopback_client_rejects_nonlocal_or_missing_addresses(host):
    assert is_loopback_client(host) is False


def test_allowlist_contains_only_preverified_fixture_hashes(monkeypatch, tmp_path, verified_synthetic_fixture):
    data_dir, fixture_dir = _configure(monkeypatch, tmp_path, verified_synthetic_fixture.read_bytes())
    enabled, hashes = load_synthetic_demo_configuration(tmp_path, data_dir)
    expected = hashlib.sha256((fixture_dir / "synthetic_left.png").read_bytes()).hexdigest()
    assert enabled is True
    assert hashes == frozenset({expected})
    with pytest.raises(RuntimeError, match="fresh, empty APP_DATA_DIR"):
        load_synthetic_demo_configuration(tmp_path, data_dir)


def test_demo_mode_does_not_trust_an_unverified_file_with_synthetic_prefix(monkeypatch, tmp_path):
    data_dir, _fixture_dir = _configure(monkeypatch, tmp_path)
    with pytest.raises(RuntimeError, match="no verified synthetic image fixtures"):
        load_synthetic_demo_configuration(tmp_path, data_dir)


@pytest.mark.parametrize(
    ("variable", "value", "message"),
    [
        ("DATABASE_URL", "postgresql://unavailable/test", "isolated SQLite"),
        ("HOST", "0.0.0.0", "loopback"),
        ("APP_CORS_ORIGINS", "https://example.invalid", "cross-origin"),
    ],
)
def test_demo_mode_rejects_unsafe_runtime_configuration(monkeypatch, tmp_path, variable, value, message):
    data_dir, _ = _configure(monkeypatch, tmp_path)
    monkeypatch.setenv(variable, value)
    with pytest.raises(RuntimeError, match=message):
        load_synthetic_demo_configuration(tmp_path, data_dir)


def test_demo_mode_requires_database_inside_runtime_and_fresh_directory(monkeypatch, tmp_path):
    data_dir, _ = _configure(monkeypatch, tmp_path)
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "outside.sqlite3"))
    with pytest.raises(RuntimeError, match="inside its isolated APP_DATA_DIR"):
        load_synthetic_demo_configuration(tmp_path, data_dir)

    monkeypatch.setenv("APP_DB_PATH", str(data_dir / "sandbox.sqlite3"))
    (data_dir / "old-run.sqlite3").touch()
    with pytest.raises(RuntimeError, match="fresh, empty APP_DATA_DIR"):
        load_synthetic_demo_configuration(tmp_path, data_dir)


def test_demo_mode_requires_a_fixture_directory_with_supported_synthetic_images(monkeypatch, tmp_path):
    data_dir, fixture_dir = _configure(monkeypatch, tmp_path)
    monkeypatch.setenv("APP_SYNTHETIC_DEMO_FIXTURE_DIR", str(tmp_path / "missing"))
    with pytest.raises(RuntimeError, match="fixture directory does not exist"):
        load_synthetic_demo_configuration(tmp_path, data_dir)

    empty_fixture_dir = tmp_path / "empty-fixtures"
    empty_fixture_dir.mkdir()
    (empty_fixture_dir / "synthetic_notes.txt").write_bytes(b"not an image")
    monkeypatch.setenv("APP_SYNTHETIC_DEMO_FIXTURE_DIR", str(empty_fixture_dir))
    with pytest.raises(RuntimeError, match="no verified synthetic image fixtures"):
        load_synthetic_demo_configuration(tmp_path, data_dir)
