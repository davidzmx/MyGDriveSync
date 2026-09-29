"""
Database manager for SQLite operations with WAL mode and thread safety.
"""

from __future__ import annotations
import sqlite3
import threading
import time
from pathlib import Path
from typing import List, Optional, Set

from .models import ItemType, SyncFolder, SyncItem, SyncStatus
from .schema import CREATE_TABLES_SQL


class DatabaseManager:
    """Thread-safe SQLite manager for tracking synchronization state."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._lock = threading.Lock()
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a thread-local SQLite connection configured with WAL mode."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for concurrent reads and writes
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            self._local.conn = conn
        return self._local.conn

    def close(self) -> None:
        """Closes the current thread's connection."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

    def init_db(self) -> None:
        """Initializes tables and indexes."""
        with self._lock:
            conn = self._get_connection()
            with conn:
                conn.executescript(CREATE_TABLES_SQL)

    # -------------------------------------------------------------------------
    # Key-Value Storage (KV)
    # -------------------------------------------------------------------------

    def get_kv(self, key: str, default: Optional[str] = None) -> Optional[str]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT value FROM app_kv WHERE key = ?;", (key,))
        row = cur.fetchone()
        return row["value"] if row else default

    def set_kv(self, key: str, value: str) -> None:
        conn = self._get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO app_kv (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at;
                """,
                (key, str(value), time.time()),
            )

    # -------------------------------------------------------------------------
    # Sync Items (Files & Folders)
    # -------------------------------------------------------------------------

    def upsert_item(self, item: SyncItem) -> SyncItem:
        """Inserts or updates a synchronized item."""
        rel_path = SyncItem.normalize_path(item.rel_path)
        item.rel_path = rel_path
        now = time.time()
        conn = self._get_connection()

        with conn:
            cur = conn.execute(
                """
                INSERT INTO sync_items (
                    rel_path, drive_id, item_type, size,
                    mtime_local, mtime_remote, md5_checksum,
                    status, error_message, parent_drive_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(rel_path) DO UPDATE SET
                    drive_id = COALESCE(excluded.drive_id, sync_items.drive_id),
                    item_type = excluded.item_type,
                    size = excluded.size,
                    mtime_local = excluded.mtime_local,
                    mtime_remote = COALESCE(excluded.mtime_remote, sync_items.mtime_remote),
                    md5_checksum = COALESCE(excluded.md5_checksum, sync_items.md5_checksum),
                    status = excluded.status,
                    error_message = excluded.error_message,
                    parent_drive_id = COALESCE(excluded.parent_drive_id, sync_items.parent_drive_id),
                    updated_at = excluded.updated_at;
                """,
                (
                    rel_path,
                    item.drive_id,
                    item.item_type.value,
                    item.size,
                    item.mtime_local,
                    item.mtime_remote,
                    item.md5_checksum,
                    item.status.value,
                    item.error_message,
                    item.parent_drive_id,
                    now,
                ),
            )
            if item.id is None:
                item.id = cur.lastrowid
            item.updated_at = now
        return item

    def get_item_by_path(self, rel_path: str) -> Optional[SyncItem]:
        normalized = SyncItem.normalize_path(rel_path)
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM sync_items WHERE rel_path = ?;", (normalized,))
        row = cur.fetchone()
        return self._row_to_item(row) if row else None

    def get_item_by_drive_id(self, drive_id: str) -> Optional[SyncItem]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM sync_items WHERE drive_id = ?;", (drive_id,))
        row = cur.fetchone()
        return self._row_to_item(row) if row else None

    def delete_item_by_path(self, rel_path: str) -> bool:
        normalized = SyncItem.normalize_path(rel_path)
        conn = self._get_connection()
        with conn:
            cur = conn.execute("DELETE FROM sync_items WHERE rel_path = ?;", (normalized,))
            return cur.rowcount > 0

    def delete_item_by_drive_id(self, drive_id: str) -> bool:
        conn = self._get_connection()
        with conn:
            cur = conn.execute("DELETE FROM sync_items WHERE drive_id = ?;", (drive_id,))
            return cur.rowcount > 0

    def update_status(
        self,
        rel_path: str,
        status: SyncStatus,
        error: Optional[str] = None,
    ) -> bool:
        normalized = SyncItem.normalize_path(rel_path)
        conn = self._get_connection()
        with conn:
            cur = conn.execute(
                """
                UPDATE sync_items
                SET status = ?, error_message = ?, updated_at = ?
                WHERE rel_path = ?;
                """,
                (status.value, error, time.time(), normalized),
            )
            return cur.rowcount > 0

    def list_items(
        self,
        status: Optional[SyncStatus] = None,
        limit: int = 100,
    ) -> List[SyncItem]:
        conn = self._get_connection()
        cur = conn.cursor()
        if status:
            cur.execute(
                "SELECT * FROM sync_items WHERE status = ? ORDER BY updated_at DESC LIMIT ?;",
                (status.value, limit),
            )
        else:
            cur.execute(
                "SELECT * FROM sync_items ORDER BY updated_at DESC LIMIT ?;",
                (limit,),
            )
        return [self._row_to_item(r) for r in cur.fetchall()]

    def get_all_synced_paths(self) -> Set[str]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT rel_path FROM sync_items;")
        return {row["rel_path"] for row in cur.fetchall()}

    def get_pending_items(self) -> List[SyncItem]:
        """Returns all items that are pending upload or download."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM sync_items
            WHERE status IN (?, ?, ?, ?)
            ORDER BY updated_at ASC;
            """,
            (
                SyncStatus.QUEUED_DOWNLOAD.value,
                SyncStatus.DOWNLOADING.value,
                SyncStatus.QUEUED_UPLOAD.value,
                SyncStatus.UPLOADING.value,
            ),
        )
        return [self._row_to_item(r) for r in cur.fetchall()]

    # -------------------------------------------------------------------------
    # Selective Sync Folders
    # -------------------------------------------------------------------------

    def set_folder_sync_state(self, drive_id: str, rel_path: str, is_synced: bool) -> None:
        """Sets whether a specific folder is included or excluded from synchronization."""
        normalized = SyncItem.normalize_path(rel_path)
        conn = self._get_connection()
        with conn:
            conn.execute(
                """
                INSERT INTO sync_folders (drive_id, rel_path, is_synced, last_scanned)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(drive_id) DO UPDATE SET
                    rel_path = excluded.rel_path,
                    is_synced = excluded.is_synced,
                    last_scanned = excluded.last_scanned;
                """,
                (drive_id, normalized, 1 if is_synced else 0, time.time()),
            )

    def get_all_sync_folders(self) -> List[SyncFolder]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM sync_folders ORDER BY rel_path ASC;")
        return [
            SyncFolder(
                drive_id=row["drive_id"],
                rel_path=row["rel_path"],
                is_synced=bool(row["is_synced"]),
                last_scanned=row["last_scanned"],
            )
            for row in cur.fetchall()
        ]

    def is_path_selected_for_sync(self, rel_path: str) -> bool:
        """
        Determines if a path should be synced based on selective sync rules.
        If a parent folder or the path itself is marked `is_synced = False`, it is excluded.
        """
        normalized = SyncItem.normalize_path(rel_path)
        if not normalized:
            return True

        folders = self.get_all_sync_folders()
        if not folders:
            # Default: everything is synced
            return True

        # Check path segments from top to bottom
        parts = normalized.split("/")
        current_sub = ""
        for part in parts:
            current_sub = f"{current_sub}/{part}" if current_sub else part
            for sf in folders:
                if sf.rel_path == current_sub:
                    if not sf.is_synced:
                        return False
        return True

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> SyncItem:
        return SyncItem(
            id=row["id"],
            rel_path=row["rel_path"],
            drive_id=row["drive_id"],
            item_type=ItemType(row["item_type"]),
            size=row["size"],
            mtime_local=row["mtime_local"],
            mtime_remote=row["mtime_remote"],
            md5_checksum=row["md5_checksum"],
            status=SyncStatus(row["status"]),
            error_message=row["error_message"],
            parent_drive_id=row["parent_drive_id"],
            updated_at=row["updated_at"],
        )
