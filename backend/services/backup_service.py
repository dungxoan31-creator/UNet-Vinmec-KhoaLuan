"""
Automated Database & File System Backup Service for Vinmec Ovarian Ultrasound AI.
Author: Nguyen Huu Dung (MIS 65A - NEU)
"""

import os
import shutil
import sqlite3
import tarfile
import uuid
from datetime import datetime
from typing import Any


class BackupService:
    def __init__(
        self,
        db_path: str | None = None,
        data_dir: str | None = None,
        backup_dir: str = "backups",
    ):
        from backend.db.database import DB_PATH

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

        if db_path:
            self.db_path = os.path.abspath(db_path) if os.path.isabs(db_path) else os.path.abspath(os.path.join(project_root, db_path))
        elif os.environ.get("APP_DB_PATH"):
            env_db = os.environ.get("APP_DB_PATH")
            self.db_path = os.path.abspath(env_db) if os.path.isabs(env_db) else os.path.abspath(os.path.join(project_root, env_db))
        else:
            self.db_path = DB_PATH

        if data_dir:
            self.data_dir = os.path.abspath(data_dir) if os.path.isabs(data_dir) else os.path.abspath(os.path.join(project_root, data_dir))
        elif os.environ.get("APP_DATA_DIR"):
            env_data = os.environ.get("APP_DATA_DIR")
            self.data_dir = os.path.abspath(env_data) if os.path.isabs(env_data) else os.path.abspath(os.path.join(project_root, env_data))
        else:
            self.data_dir = os.path.abspath(os.path.join(project_root, "data"))

        self.backup_dir = os.path.abspath(backup_dir) if os.path.isabs(backup_dir) else os.path.abspath(os.path.join(project_root, backup_dir))
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, include_images: bool = True) -> dict[str, Any]:
        """
        Creates a timestamped snapshot of the SQLite database and uploaded clinical media files.
        """
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database file not found: {self.db_path}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_suffix = uuid.uuid4().hex[:6]
        base_name = f"vinmec_ovarian_backup_{timestamp}_{unique_suffix}"

        # Avoid colliding archive paths if called in the same second (BUG-30)
        candidate_name = base_name
        counter = 1
        while os.path.exists(os.path.join(self.backup_dir, f"{candidate_name}.tar.gz")):
            candidate_name = f"{base_name}_{counter}"
            counter += 1

        backup_name = candidate_name
        archive_path = os.path.join(self.backup_dir, f"{backup_name}.tar.gz")

        temp_dir_name = f"{backup_name}_{uuid.uuid4().hex[:6]}"
        temp_backup_dir = os.path.join(self.backup_dir, temp_dir_name)
        os.makedirs(temp_backup_dir, exist_ok=True)

        try:
            # 1. Hot SQLite Backup using online backup API (BUG-29)
            dest_db_name = os.path.basename(self.db_path)
            dest_db_path = os.path.join(temp_backup_dir, dest_db_name)
            src_conn = sqlite3.connect(self.db_path)
            dest_conn = sqlite3.connect(dest_db_path)
            with dest_conn:
                src_conn.backup(dest_conn, pages=100)
            dest_conn.close()
            src_conn.close()

            # 2. Copy media directories if requested
            if include_images and os.path.exists(self.data_dir):
                dest_data_dir = os.path.join(temp_backup_dir, "data")
                shutil.copytree(
                    self.data_dir,
                    dest_data_dir,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("*.tmp", "*.lock"),
                )

            # 3. Create compressed tar.gz archive
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(temp_backup_dir, arcname=backup_name)

            archive_size_bytes = os.path.getsize(archive_path)

            return {
                "status": "SUCCESS",
                "backup_filename": f"{backup_name}.tar.gz",
                "backup_path": archive_path,
                "size_mb": round(archive_size_bytes / (1024 * 1024), 2),
                "timestamp": timestamp,
                "included_images": include_images,
            }
        finally:
            if os.path.exists(temp_backup_dir):
                shutil.rmtree(temp_backup_dir, ignore_errors=True)

    def list_backups(self) -> list[dict[str, Any]]:
        """
        Lists all existing backup archives with creation times and sizes.
        """
        backups = []
        if not os.path.exists(self.backup_dir):
            return backups

        for fname in sorted(os.listdir(self.backup_dir), reverse=True):
            if fname.endswith(".tar.gz") and fname.startswith("vinmec_ovarian_backup_"):
                fpath = os.path.join(self.backup_dir, fname)
                stat = os.stat(fpath)
                backups.append(
                    {
                        "filename": fname,
                        "path": fpath,
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M:%S"),
                    }
                )
        return backups

    def cleanup_old_backups(self, max_retained: int = 10) -> int:
        """
        Retains only the most recent `max_retained` backups and cleans up older archives.
        """
        backups = self.list_backups()
        deleted_count = 0
        if len(backups) > max_retained:
            to_delete = backups[max_retained:]
            for b in to_delete:
                try:
                    os.remove(b["path"])
                    deleted_count += 1
                except Exception as e:
                    print(f"Error removing backup {b['filename']}: {e}")
        return deleted_count
