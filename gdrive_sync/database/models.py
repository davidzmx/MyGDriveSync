"""
Data models and Enums for synchronization state.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import time


class SyncStatus(str, Enum):
    SYNCED = "synced"
    QUEUED_UPLOAD = "queued_upload"
    UPLOADING = "uploading"
    QUEUED_DOWNLOAD = "queued_download"
    DOWNLOADING = "downloading"
    CONFLICT = "conflict"
    ERROR = "error"
    IGNORED = "ignored"
    DELETED_LOCAL = "deleted_local"
    DELETED_REMOTE = "deleted_remote"

    @property
    def is_active_transfer(self) -> bool:
        return self in (
            SyncStatus.QUEUED_UPLOAD,
            SyncStatus.UPLOADING,
            SyncStatus.QUEUED_DOWNLOAD,
            SyncStatus.DOWNLOADING,
        )


class ItemType(str, Enum):
    FILE = "file"
    FOLDER = "folder"


@dataclass
class SyncFolder:
    """Represents a folder rule for selective sync."""
    drive_id: str
    rel_path: str
    is_synced: bool = True
    last_scanned: float = 0.0


@dataclass
class SyncItem:
    """Represents a synchronized file or folder in the local state database."""
    rel_path: str
    item_type: ItemType
    drive_id: Optional[str] = None
    size: int = 0
    mtime_local: float = 0.0
    mtime_remote: Optional[str] = None
    md5_checksum: Optional[str] = None
    status: SyncStatus = SyncStatus.SYNCED
    error_message: Optional[str] = None
    parent_drive_id: Optional[str] = None
    updated_at: float = 0.0
    id: Optional[int] = None

    def __post_init__(self):
        if self.updated_at == 0.0:
            self.updated_at = time.time()
        # Normalize relative path: forward slashes, no leading/trailing slashes
        self.rel_path = self.normalize_path(self.rel_path)

    @staticmethod
    def normalize_path(path: str) -> str:
        """Normalizes path using forward slashes for cross-platform compatibility."""
        p = path.replace("\\", "/").strip("/")
        return p
