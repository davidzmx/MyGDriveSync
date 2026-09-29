"""
Unit tests for UI components and dialog instantiation.
"""

import os
import tempfile
import unittest
from pathlib import Path

# Run Qt in offscreen / minimal platform for headless environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from gdrive_sync.config import AppConfig
from gdrive_sync.database.manager import DatabaseManager
from gdrive_sync.engine.sync_service import SyncService
from gdrive_sync.ui.activity_dialog import ActivityDialog
from gdrive_sync.ui.icons import create_tray_icon
from gdrive_sync.ui.preferences_dialog import PreferencesDialog
from gdrive_sync.ui.selective_sync_dialog import SelectiveSyncDialog
from gdrive_sync.ui.tray import GDriveTrayIcon


class TestUIComponents(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.tmp_dir.name)
        self.config = AppConfig(config_dir=self.config_dir)
        self.db = DatabaseManager(self.config.db_path)
        self.service = SyncService(self.config)

    def tearDown(self):
        self.db.close()
        self.tmp_dir.cleanup()

    def test_icons_generated(self):
        for state in ["IDLE", "SYNCING", "PAUSED", "ERROR", "NO_AUTH"]:
            icon = create_tray_icon(state)
            self.assertFalse(icon.isNull())

    def test_activity_dialog(self):
        dialog = ActivityDialog(self.db)
        self.assertIsNotNone(dialog)
        dialog.close()

    def test_preferences_dialog(self):
        dialog = PreferencesDialog(
            config=self.config,
            sync_service=self.service,
        )
        self.assertIsNotNone(dialog)
        dialog.close()

    def test_selective_sync_dialog(self):
        dialog = SelectiveSyncDialog(
            db=self.db,
            drive_client=None,
            sync_dir=self.config.sync_dir,
            sync_service=self.service,
        )
        self.assertIsNotNone(dialog)
        dialog.close()

    def test_tray_icon(self):
        tray = GDriveTrayIcon(self.service)
        self.assertIsNotNone(tray)
        self.assertIsNotNone(tray.contextMenu())


if __name__ == "__main__":
    unittest.main()
