"""
Reconciliation logic and conflict resolution between local filesystem and Google Drive.
"""

from __future__ import annotations
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .queue import TaskPriority, TaskType
from .utils import calculate_md5
from ..database.manager import DatabaseManager
from ..database.models import ItemType, SyncItem, SyncStatus


class Reconciler:
    """Evaluates local and remote events, checks hashes, and detects/resolves conflicts."""

    @staticmethod
    def resolve_local_change(
        rel_path: str,
        event_type: str,
        sync_dir: Path,
        db: DatabaseManager,
    ) -> Optional[Tuple[str, TaskPriority, Dict[str, Any]]]:
        """
        Determines the task needed when a local file or directory is modified/deleted.
        """
        norm_path = SyncItem.normalize_path(rel_path)
        full_path = sync_dir / norm_path
        existing = db.get_item_by_path(norm_path)

        if event_type == "deleted":
            if existing and existing.drive_id:
                return (TaskType.DELETE_REMOTE, TaskPriority.HIGH, {"drive_id": existing.drive_id})
            return None

        if not full_path.exists():
            return None

        if full_path.is_dir():
            # Folder creation
            if not existing or not existing.drive_id:
                return (TaskType.CREATE_REMOTE_FOLDER, TaskPriority.HIGH, {})
            return None

        # It's a file
        size = full_path.stat().st_size
        mtime = full_path.stat().st_mtime
        local_md5 = calculate_md5(full_path)

        if existing and existing.md5_checksum == local_md5 and existing.status == SyncStatus.SYNCED:
            # File content has not changed (e.g. touch or metadata change only)
            return None

        # Prioritize small files over huge files
        priority = TaskPriority.MEDIUM if size < 10 * 1024 * 1024 else TaskPriority.LOW

        # Register pending upload in DB
        item = SyncItem(
            rel_path=norm_path,
            item_type=ItemType.FILE,
            drive_id=existing.drive_id if existing else None,
            size=size,
            mtime_local=mtime,
            md5_checksum=local_md5,
            status=SyncStatus.QUEUED_UPLOAD,
        )
        db.upsert_item(item)

        return (TaskType.UPLOAD, priority, {"size": size, "md5": local_md5})

    @staticmethod
    def resolve_remote_change(
        file_meta: Dict[str, Any],
        rel_path: str,
        sync_dir: Path,
        db: DatabaseManager,
    ) -> Optional[Tuple[str, TaskPriority, Dict[str, Any]]]:
        """
        Determines the task needed when a remote file change is detected from Google Drive.
        Handles conflict detection and creates conflict copy if both were modified.
        """
        drive_id = file_meta.get("id")
        remote_md5 = file_meta.get("md5Checksum")
        mime_type = file_meta.get("mimeType", "")
        is_folder = mime_type == "application/vnd.google-apps.folder"

        norm_path = SyncItem.normalize_path(rel_path)
        full_path = sync_dir / norm_path
        existing = db.get_item_by_drive_id(drive_id) or db.get_item_by_path(norm_path)

        if is_folder:
            # Folder ensure exists locally
            full_path.mkdir(parents=True, exist_ok=True)
            db.upsert_item(
                SyncItem(
                    rel_path=norm_path,
                    item_type=ItemType.FOLDER,
                    drive_id=drive_id,
                    status=SyncStatus.SYNCED,
                )
            )
            return None

        # Check local state
        if full_path.exists():
            local_md5 = calculate_md5(full_path)

            if remote_md5 and local_md5 == remote_md5:
                # Content is identical, mark as synced
                db.upsert_item(
                    SyncItem(
                        rel_path=norm_path,
                        item_type=ItemType.FILE,
                        drive_id=drive_id,
                        size=full_path.stat().st_size,
                        mtime_local=full_path.stat().st_mtime,
                        mtime_remote=file_meta.get("modifiedTime"),
                        md5_checksum=remote_md5,
                        status=SyncStatus.SYNCED,
                    )
                )
                return None

            # Content differs! Check if local was modified concurrently (Conflict)
            if existing and existing.status in (SyncStatus.QUEUED_UPLOAD, SyncStatus.UPLOADING):
                # CONFLICT DETECTED!
                # Preserve local version with conflict filename
                timestamp_str = datetime.now().strftime("%Y-%m-%d-%H%M%S")
                conflict_name = f"{full_path.stem} (Conflicto de copia {timestamp_str}){full_path.suffix}"
                conflict_path = full_path.parent / conflict_name
                shutil.copy2(str(full_path), str(conflict_path))

                # Queue the conflict copy to be uploaded so changes aren't lost
                conflict_rel = SyncItem.normalize_path(str(conflict_path.relative_to(sync_dir)))
                db.upsert_item(
                    SyncItem(
                        rel_path=conflict_rel,
                        item_type=ItemType.FILE,
                        size=conflict_path.stat().st_size,
                        mtime_local=conflict_path.stat().st_mtime,
                        status=SyncStatus.QUEUED_UPLOAD,
                    )
                )

        # Queue download of the remote version
        size = int(file_meta.get("size", 0))
        priority = TaskPriority.MEDIUM if size < 10 * 1024 * 1024 else TaskPriority.LOW

        db.upsert_item(
            SyncItem(
                rel_path=norm_path,
                item_type=ItemType.FILE,
                drive_id=drive_id,
                size=size,
                mtime_remote=file_meta.get("modifiedTime"),
                md5_checksum=remote_md5,
                status=SyncStatus.QUEUED_DOWNLOAD,
            )
        )

        return (TaskType.DOWNLOAD, priority, {"file_meta": file_meta})
