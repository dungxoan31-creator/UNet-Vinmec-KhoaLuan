"""
Automated Database & File System Backup Service for Vinmec Ovarian Ultrasound AI.
Author: Nguyen Huu Dung (MIS 65A - NEU)
"""

import os
import shutil
import sqlite3
import tarfile
from datetime import datetime
from typing import Any


class BackupService:
    def __init__(
        self,
        db_path: str = "ovarian_ai.db",
        data_dir: str = "data",
        backup_dir: str = "backups",
    ):
        self.db_path = os.path.abspath(db_path)
        self.data_dir = os.path.abspath(data_dir)
        self.backup_dir = os.path.abspath(backup_dir)
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self, include_images: bool = True) -> dict[str, Any]:
        """
        Creates a timestamped snapshot of the SQLite database and uploaded clinical media files.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"vinmec_ovarian_backup_{timestamp}"
        archive_path = os.path.join(self.backup_dir, f"{backup_name}.tar.gz")

        temp_backup_dir = os.path.join(self.backup_dir, backup_name)
        os.makedirs(temp_backup_dir, exist_ok=True)

        try:
            # 1. Hot SQLite Backup using online backup API
            if os.path.exists(self.db_path):
                dest_db_path = os.path.join(temp_backup_dir, "ovarian_ai.db")
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
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M:%S"),
                        "path": fpath,
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
