"""
Unit tests for Reconciler, SyncQueue, and File utilities.
"""

import tempfile
import unittest
from pathlib import Path

from gdrive_sync.database.manager import DatabaseManager
from gdrive_sync.database.models import ItemType, SyncItem, SyncStatus
from gdrive_sync.engine.queue import SyncQueue, SyncTask, TaskPriority, TaskType
from gdrive_sync.engine.reconciler import Reconciler
from gdrive_sync.engine.utils import calculate_md5, is_ignored_filename


class TestEngine(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)
        self.sync_dir = self.root / "GoogleDrive"
        self.sync_dir.mkdir(parents=True)
        self.db = DatabaseManager(self.root / "sync.db")

    def tearDown(self):
        self.db.close()
        self.tmp_dir.cleanup()

    def test_utils(self):
        test_file = self.sync_dir / "sample.txt"
        test_file.write_text("Hello World 123", encoding="utf-8")

        md5 = calculate_md5(test_file)
        self.assertTrue(len(md5) == 32)

        self.assertTrue(is_ignored_filename(".git"))
        self.assertTrue(is_ignored_filename("test.tmp"))
        self.assertTrue(is_ignored_filename("desktop.ini"))
        self.assertFalse(is_ignored_filename("document.pdf"))

    def test_reconciler_local_change_new_file(self):
        file = self.sync_dir / "document.txt"
        file.write_text("Secret Content", encoding="utf-8")

        res = Reconciler.resolve_local_change(
            rel_path="document.txt",
            event_type="created",
            sync_dir=self.sync_dir,
            db=self.db,
        )
        self.assertIsNotNone(res)
        task_type, priority, extra = res
        self.assertEqual(task_type, TaskType.UPLOAD)
        self.assertEqual(priority, TaskPriority.MEDIUM)

    def test_reconciler_conflict_detection(self):
        # Scenario: Local file was modified and marked as QUEUED_UPLOAD
        file = self.sync_dir / "notes.txt"
        file.write_text("Local Edits", encoding="utf-8")

        self.db.upsert_item(
            SyncItem(
                rel_path="notes.txt",
                item_type=ItemType.FILE,
                drive_id="id-notes-remote",
                status=SyncStatus.QUEUED_UPLOAD,
            )
        )

        # Remote change arrives with different MD5
        remote_meta = {
            "id": "id-notes-remote",
            "name": "notes.txt",
            "md5Checksum": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "size": 50,
            "modifiedTime": "2026-09-28T12:00:00Z",
        }

        res = Reconciler.resolve_remote_change(
            file_meta=remote_meta,
            rel_path="notes.txt",
            sync_dir=self.sync_dir,
            db=self.db,
        )
        self.assertIsNotNone(res)
        task_type, priority, _ = res
        self.assertEqual(task_type, TaskType.DOWNLOAD)

        # Verify conflict file was generated locally!
        conflict_files = list(self.sync_dir.glob("notes (Conflicto de copia *).txt"))
        self.assertEqual(len(conflict_files), 1)
        self.assertEqual(conflict_files[0].read_text(encoding="utf-8"), "Local Edits")

    def test_sync_queue_ordering(self):
        executed_tasks = []

        def worker(task: SyncTask):
            executed_tasks.append(task.task_type)

        q = SyncQueue(worker_func=worker, max_workers=1)
        q.start()

        # Add Low priority then High priority
        q.add_task(task_type="LOW_TASK", rel_path="file1", priority=TaskPriority.LOW)
        q.add_task(task_type="HIGH_TASK", rel_path="file2", priority=TaskPriority.HIGH)

        import time
        time.sleep(0.5)
        q.stop()

        self.assertEqual(len(executed_tasks), 2)
        # High priority should execute first
        self.assertEqual(executed_tasks[0], "HIGH_TASK")
        self.assertEqual(executed_tasks[1], "LOW_TASK")


    def test_reconciler_google_docs_export_and_idempotence(self):
        # Scenario 1: First time seeing a Google Docs file (no extension remotely)
        doc_meta = {
            "id": "gdoc-12345",
            "name": "Documento de Prueba",
            "mimeType": "application/vnd.google-apps.document",
            "modifiedTime": "2026-10-20T10:00:00Z",
        }

        res = Reconciler.resolve_remote_change(
            file_meta=doc_meta,
            rel_path="Documento de Prueba",
            sync_dir=self.sync_dir,
            db=self.db,
        )
        self.assertIsNotNone(res)
        task_type, priority, extra = res
        self.assertEqual(task_type, TaskType.DOWNLOAD)
        # Should target .docx automatically
        self.assertEqual(extra.get("target_rel"), "Documento de Prueba.docx")

        # Simulate that it was downloaded and saved into DB with .docx
        local_docx = self.sync_dir / "Documento de Prueba.docx"
        local_docx.write_text("Exported Word content", encoding="utf-8")
        local_md5 = calculate_md5(local_docx)

        self.db.upsert_item(
            SyncItem(
                rel_path="Documento de Prueba.docx",
                item_type=ItemType.FILE,
                drive_id="gdoc-12345",
                size=local_docx.stat().st_size,
                mtime_remote="2026-10-20T10:00:00Z",
                md5_checksum=local_md5,
                status=SyncStatus.SYNCED,
            )
        )

        # Scenario 2: Poller sees Google Docs again with unchanged modifiedTime
        res2 = Reconciler.resolve_remote_change(
            file_meta=doc_meta,
            rel_path="Documento de Prueba",
            sync_dir=self.sync_dir,
            db=self.db,
        )
        # MUST return None: already up to date, do NOT re-download!
        self.assertIsNone(res2)

        # Scenario 3: Local watcher event for the downloaded .docx file
        res_local = Reconciler.resolve_local_change(
            rel_path="Documento de Prueba.docx",
            event_type="created",
            sync_dir=self.sync_dir,
            db=self.db,
        )
        # MUST return None: local file MD5 matches what's in DB, do NOT re-upload!
        self.assertIsNone(res_local)


if __name__ == "__main__":
    unittest.main()
