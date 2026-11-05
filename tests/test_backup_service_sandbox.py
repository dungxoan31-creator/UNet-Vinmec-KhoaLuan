import sqlite3
import tarfile
from pathlib import Path

from backend.services.backup_service import BackupService


def test_backup_archive_can_be_restored_inside_isolated_temp_directory(tmp_path):
    source_db = tmp_path / "synthetic.sqlite3"
    with sqlite3.connect(source_db) as connection:
        connection.execute("CREATE TABLE synthetic_record (value TEXT NOT NULL)")
        connection.execute("INSERT INTO synthetic_record VALUES (?)", ("sandbox-only",))

    data_dir = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    service = BackupService(
        db_path=str(source_db),
        data_dir=str(data_dir),
        backup_dir=str(backup_dir),
    )
    result = service.create_backup(include_images=False)
    archive_path = Path(result["backup_path"]).resolve()
    assert archive_path.is_relative_to(backup_dir.resolve())

    restore_root = tmp_path / "restore"
    restore_root.mkdir()
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            destination = (restore_root / member.name).resolve()
            assert destination.is_relative_to(restore_root.resolve())
        archive.extractall(restore_root, filter="data")

    restored_db = next(restore_root.glob("*/synthetic.sqlite3"))
    with sqlite3.connect(restored_db) as connection:
        row = connection.execute("SELECT value FROM synthetic_record").fetchone()

    assert row == ("sandbox-only",)
    assert list(backup_dir.glob("*.tar.gz")) == [archive_path]


def test_default_backup_directory_uses_explicit_sandbox_environment(tmp_path, monkeypatch):
    source_db = tmp_path / "synthetic.sqlite3"
    source_db.touch()
    sandbox_backup_dir = tmp_path / "isolated-backups"
    monkeypatch.setenv("APP_BACKUP_DIR", str(sandbox_backup_dir))

    service = BackupService(db_path=str(source_db), data_dir=str(tmp_path / "data"))

    assert Path(service.backup_dir) == sandbox_backup_dir.resolve()
