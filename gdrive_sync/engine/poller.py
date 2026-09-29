"""
Cloud Poller querying Google Drive Changes API periodically for delta updates.
"""

from __future__ import annotations
import threading
import time
from typing import Any, Callable, Dict, Optional

from ..database.manager import DatabaseManager
from ..drive.client import GoogleDriveClient


class CloudPoller:
    """Periodically fetches remote changes from Google Drive Changes API."""

    def __init__(
        self,
        drive_client: GoogleDriveClient,
        db: DatabaseManager,
        on_remote_change_cb: Callable[[Dict[str, Any]], None],
        on_remote_delete_cb: Callable[[str], None],
        poll_interval_seconds: int = 30,
    ):
        self.client = drive_client
        self.db = db
        self.on_remote_change = on_remote_change_cb
        self.on_remote_delete = on_remote_delete_cb
        self.poll_interval = poll_interval_seconds

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()

    def start(self) -> None:
        """Starts the polling thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="CloudPollerThread",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Stops the polling thread gracefully."""
        self._stop_event.set()
        self._wake_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

    def trigger_now(self) -> None:
        """Forces an immediate poll cycle without waiting for poll_interval."""
        self._wake_event.set()

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.poll_once()
            except Exception as e:
                print(f"[CloudPoller] Error during poll cycle: {e}")

            # Wait for poll interval or immediate wake signal
            self._wake_event.wait(timeout=self.poll_interval)
            self._wake_event.clear()

    def poll_once(self) -> None:
        """Executes one pass of the Google Drive Changes API."""
        if not self.client.credentials:
            return

        page_token = self.db.get_kv("start_page_token")
        if not page_token:
            # First run: acquire start token
            start_token = self.client.get_start_page_token()
            self.db.set_kv("start_page_token", start_token)
            return

        changes, new_token = self.client.list_changes(page_token)

        for change in changes:
            file_id = change.get("fileId")
            is_removed = change.get("removed", False)
            file_meta = change.get("file")

            if is_removed or (file_meta and file_meta.get("trashed")):
                self.on_remote_delete(file_id)
            elif file_meta:
                self.on_remote_change(file_meta)

        if new_token and new_token != page_token:
            self.db.set_kv("start_page_token", new_token)
