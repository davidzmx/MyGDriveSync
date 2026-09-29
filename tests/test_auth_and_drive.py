"""
Tests for TokenStorage, OAuthManager, and GoogleDriveClient logic.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from google.oauth2.credentials import Credentials

from gdrive_sync.auth.token_storage import TokenStorage
from gdrive_sync.drive.client import GoogleDriveClient


class TestAuthAndDrive(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.fallback_file = Path(self.tmp_dir.name) / "token.json"
        self.storage = TokenStorage(fallback_path=self.fallback_file)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_token_storage_fallback_save_load(self):
        mock_creds = Credentials(
            token="test-access-token",
            refresh_token="test-refresh-token",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test-client-id",
            client_secret="test-client-secret",
            scopes=["https://www.googleapis.com/auth/drive"],
        )

        # Save credentials
        self.storage.save_credentials(mock_creds)
        self.assertTrue(self.fallback_file.exists())

        # Load credentials
        loaded = self.storage.load_credentials()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.token, "test-access-token")
        self.assertEqual(loaded.refresh_token, "test-refresh-token")
        self.assertEqual(loaded.client_id, "test-client-id")

        # Clear credentials
        self.storage.clear()
        self.assertFalse(self.fallback_file.exists())

    def test_build_folder_paths(self):
        client = GoogleDriveClient()
        # Mock folder tree:
        # root -> Documents (id: 1)
        # Documents -> Work (id: 2)
        # root -> Photos (id: 3)
        mock_folders = [
            {"id": "1", "name": "Documents", "parents": ["root"]},
            {"id": "2", "name": "Work", "parents": ["1"]},
            {"id": "3", "name": "Photos", "parents": ["root"]},
        ]
        paths = client.build_folder_paths(mock_folders)
        self.assertEqual(paths.get("1"), "Documents")
        self.assertEqual(paths.get("2"), "Documents/Work")
        self.assertEqual(paths.get("3"), "Photos")


if __name__ == "__main__":
    unittest.main()
