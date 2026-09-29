"""
Unit tests for DatabaseManager and state models.
Supports both unittest and pytest.
"""

import tempfile
import unittest
from pathlib import Path

from gdrive_sync.database.models import ItemType, SyncItem, SyncStatus
from gdrive_sync.database.manager import DatabaseManager


class TestDatabaseManager(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_sync.db"
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        self.db.close()
        self.tmp_dir.cleanup()

    def test_upsert_and_get_item(self):
        item = SyncItem(
            rel_path="Documents/report.pdf",
            item_type=ItemType.FILE,
            drive_id="drive-12345",
            size=1024,
            mtime_local=1700000000.0,
            mtime_remote="2026-01-01T12:00:00Z",
            md5_checksum="d41d8cd98f00b204e9800998ecf8427e",
            status=SyncStatus.SYNCED,
        )

        saved = self.db.upsert_item(item)
        self.assertIsNotNone(saved.id)

        fetched = self.db.get_item_by_path("Documents/report.pdf")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.drive_id, "drive-12345")
        self.assertEqual(fetched.size, 1024)
        self.assertEqual(fetched.status, SyncStatus.SYNCED)

        # Test update
        fetched.size = 2048
        fetched.status = SyncStatus.QUEUED_UPLOAD
        self.db.upsert_item(fetched)

        updated = self.db.get_item_by_path("Documents/report.pdf")
        self.assertEqual(updated.size, 2048)
        self.assertEqual(updated.status, SyncStatus.QUEUED_UPLOAD)

    def test_delete_item(self):
        item = SyncItem(
            rel_path="test.txt",
            item_type=ItemType.FILE,
            drive_id="drive-999",
        )
        self.db.upsert_item(item)
        self.assertIsNotNone(self.db.get_item_by_path("test.txt"))

        deleted = self.db.delete_item_by_path("test.txt")
        self.assertTrue(deleted)
        self.assertIsNone(self.db.get_item_by_path("test.txt"))

    def test_selective_sync_rules(self):
        # Setup folder rules:
        # Work is synced
        # Photos is NOT synced
        self.db.set_folder_sync_state("id-work", "Work", is_synced=True)
        self.db.set_folder_sync_state("id-photos", "Photos", is_synced=False)

        self.assertTrue(self.db.is_path_selected_for_sync("Work/doc1.txt"))
        self.assertTrue(self.db.is_path_selected_for_sync("Work/Subfolder/data.csv"))
        self.assertFalse(self.db.is_path_selected_for_sync("Photos/vacation.jpg"))
        self.assertFalse(self.db.is_path_selected_for_sync("Photos/2026/beach.png"))

        # Path not explicitly excluded
        self.assertTrue(self.db.is_path_selected_for_sync("Other/file.txt"))

    def test_kv_storage(self):
        self.assertIsNone(self.db.get_kv("non_existent"))
        self.assertEqual(self.db.get_kv("non_existent", "default_val"), "default_val")

        self.db.set_kv("start_token", "123456")
        self.assertEqual(self.db.get_kv("start_token"), "123456")

        self.db.set_kv("start_token", "789012")
        self.assertEqual(self.db.get_kv("start_token"), "789012")


if __name__ == "__main__":
    unittest.main()
