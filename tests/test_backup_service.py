"""
Unit tests for BackupService.
"""

import os
import shutil
import unittest

from backend.services.backup_service import BackupService


class TestBackupService(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.abspath("test_backup_env")
        os.makedirs(self.test_dir, exist_ok=True)
        self.db_path = os.path.join(self.test_dir, "test.db")
        self.data_dir = os.path.join(self.test_dir, "data")
        self.backup_dir = os.path.join(self.test_dir, "backups")
        os.makedirs(self.data_dir, exist_ok=True)

        # Create real sqlite db file and dummy image file
        import sqlite3

        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, val TEXT);")

        conn.execute("INSERT INTO test_table (val) VALUES ('sample');")
        conn.commit()
        conn.close()

        with open(os.path.join(self.data_dir, "sample.png"), "w") as f:
            f.write("DUMMY_IMAGE")

        self.service = BackupService(
            db_path=self.db_path,
            data_dir=self.data_dir,
            backup_dir=self.backup_dir,
        )

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_backup_creation_and_listing(self):
        result = self.service.create_backup(include_images=True)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertTrue(os.path.exists(result["backup_path"]))

        backups = self.service.list_backups()
        self.assertGreaterEqual(len(backups), 1)
        self.assertEqual(backups[0]["filename"], result["backup_filename"])
