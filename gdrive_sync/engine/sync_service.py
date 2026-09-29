"""
Main synchronization service orchestrating Watcher, Poller, DB, and Queue with Qt signals.
"""

from __future__ import annotations
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, Signal

from .poller import CloudPoller
from .queue import SyncQueue, SyncTask, TaskPriority, TaskType
from .reconciler import Reconciler
from .watcher import LocalFileWatcher
from ..auth.oauth import OAuthManager
from ..config import AppConfig
from ..database.manager import DatabaseManager
from ..database.models import ItemType, SyncItem, SyncStatus
from ..drive.client import GoogleDriveClient


class SyncService(QObject):
    """Core synchronization engine connecting local events and cloud updates."""

    # Qt Signals for GUI integration
    status_changed = Signal(str)            # "IDLE", "SYNCING", "PAUSED", "ERROR"
    file_synced = Signal(str, str)          # rel_path, action ("Subido", "Descargado", "Eliminado")
    progress_updated = Signal(str, int, int)# filename, bytes_done, bytes_total
    sync_error = Signal(str)                # error message

    def __init__(self, config: Optional[AppConfig] = None):
        super().__init__()
        self.config = config or AppConfig()
        self.db = DatabaseManager(self.config.db_path)
        self.oauth = OAuthManager(self.config)

        self.drive_client: Optional[GoogleDriveClient] = None
        self.watcher: Optional[LocalFileWatcher] = None
        self.poller: Optional[CloudPoller] = None
        self.queue: Optional[SyncQueue] = None

        self._is_paused = False
        self._is_running = False
        self._state_lock = threading.Lock()
        self._folder_cache: Dict[str, str] = {}  # folder_id -> rel_path

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def initialize(self) -> bool:
        """Initializes Google Drive client using saved credentials."""
        creds = self.oauth.get_valid_credentials()
        if not creds:
            self.status_changed.emit("NO_AUTH")
            return False

        self.drive_client = GoogleDriveClient(creds)
        self.refresh_folder_cache()
        return True

    def refresh_folder_cache(self) -> None:
        """Fetches remote folder structure to map IDs to relative paths."""
        if not self.drive_client:
            return
        try:
            folders = self.drive_client.list_all_folders()
            self._folder_cache = self.drive_client.build_folder_paths(folders)
        except Exception as e:
            print(f"[SyncService] Could not refresh folder cache: {e}")

    def start(self) -> bool:
        """Starts all synchronization subsystems."""
        with self._state_lock:
            if self._is_running:
                return True

            if not self.drive_client:
                if not self.initialize():
                    return False

            self._is_running = True
            self._is_paused = False

            # 1. Start transfer worker queue
            self.queue = SyncQueue(
                worker_func=self._execute_task,
                max_workers=self.config.max_concurrent_transfers,
            )
            self.queue.start()

            # Enqueue pending items from previous session
            pending_items = self.db.get_pending_items()
            for item in pending_items:
                if item.item_type == ItemType.FOLDER:
                    continue
                if item.status in (SyncStatus.QUEUED_DOWNLOAD, SyncStatus.DOWNLOADING):
                    priority = TaskPriority.MEDIUM if (item.size or 0) < 10 * 1024 * 1024 else TaskPriority.LOW
                    self.queue.add_task(
                        task_type=TaskType.DOWNLOAD,
                        rel_path=item.rel_path,
                        priority=priority,
                        drive_id=item.drive_id,
                        extra={"file_meta": {"modifiedTime": item.mtime_remote, "md5Checksum": item.md5_checksum}},
                    )
                elif item.status in (SyncStatus.QUEUED_UPLOAD, SyncStatus.UPLOADING):
                    priority = TaskPriority.MEDIUM if (item.size or 0) < 10 * 1024 * 1024 else TaskPriority.LOW
                    self.queue.add_task(
                        task_type=TaskType.UPLOAD,
                        rel_path=item.rel_path,
                        priority=priority,
                        drive_id=item.drive_id,
                        extra={"size": item.size, "md5": item.md5_checksum},
                    )

            # 2. Start local file watcher
            self.watcher = LocalFileWatcher(
                sync_dir=self.config.sync_dir,
                db=self.db,
                on_change_callback=self._on_local_change,
                debounce_seconds=self.config.debounce_seconds,
            )
            self.watcher.start()

            # 3. Start cloud changes poller
            self.poller = CloudPoller(
                drive_client=self.drive_client,
                db=self.db,
                on_remote_change_cb=self._on_remote_change,
                on_remote_delete_cb=self._on_remote_delete,
                poll_interval_seconds=self.config.poll_interval,
            )
            self.poller.start()

            if pending_items:
                self.status_changed.emit("SYNCING")
            else:
                self.status_changed.emit("IDLE")
            return True

    def stop(self) -> None:
        """Stops all running synchronization threads."""
        with self._state_lock:
            if not self._is_running:
                return

            if self.watcher:
                self.watcher.stop()
                self.watcher = None

            if self.poller:
                self.poller.stop()
                self.poller = None

            if self.queue:
                self.queue.stop()
                self.queue = None

            self._is_running = False
            self.status_changed.emit("STOPPED")

    def pause(self) -> None:
        self._is_paused = True
        self.status_changed.emit("PAUSED")

    def resume(self) -> None:
        self._is_paused = False
        self.status_changed.emit("IDLE")
        if self.poller:
            self.poller.trigger_now()

    # -------------------------------------------------------------------------
    # Internal Event Handlers
    # -------------------------------------------------------------------------

    def _on_local_change(self, rel_path: str, event_type: str) -> None:
        if self._is_paused or not self.queue:
            return

        decision = Reconciler.resolve_local_change(
            rel_path=rel_path,
            event_type=event_type,
            sync_dir=self.config.sync_dir,
            db=self.db,
        )
        if decision:
            task_type, priority, extra = decision
            self.queue.add_task(
                task_type=task_type,
                rel_path=rel_path,
                priority=priority,
                drive_id=extra.get("drive_id"),
                extra=extra,
            )
            self.status_changed.emit("SYNCING")

    def _on_remote_change(self, file_meta: Dict[str, Any]) -> None:
        if self._is_paused or not self.queue:
            return

        drive_id = file_meta.get("id")
        name = file_meta.get("name")
        parents = file_meta.get("parents", [])
        parent_id = parents[0] if parents else "root"

        # Determine relative path using folder cache
        parent_rel = self._folder_cache.get(parent_id, "")
        rel_path = f"{parent_rel}/{name}".strip("/") if parent_rel else name

        mime_type = file_meta.get("mimeType", "")
        if mime_type == "application/vnd.google-apps.folder":
            self._folder_cache[drive_id] = rel_path

        # Check selective sync
        if not self.db.is_path_selected_for_sync(rel_path):
            return

        decision = Reconciler.resolve_remote_change(
            file_meta=file_meta,
            rel_path=rel_path,
            sync_dir=self.config.sync_dir,
            db=self.db,
        )
        if decision:
            task_type, priority, extra = decision
            self.queue.add_task(
                task_type=task_type,
                rel_path=rel_path,
                priority=priority,
                drive_id=drive_id,
                extra=extra,
            )
            self.status_changed.emit("SYNCING")

    def _on_remote_delete(self, drive_id: str) -> None:
        if self._is_paused:
            return

        item = self.db.get_item_by_drive_id(drive_id)
        if not item:
            return

        local_file = self.config.sync_dir / item.rel_path
        if local_file.exists():
            if self.watcher:
                self.watcher.mark_internal_operation(item.rel_path)
            try:
                if local_file.is_dir():
                    import shutil
                    shutil.rmtree(str(local_file))
                else:
                    local_file.unlink()
            except Exception as e:
                print(f"[SyncService] Error deleting local file {local_file}: {e}")
            finally:
                if self.watcher:
                    self.watcher.unmark_internal_operation(item.rel_path)

        self.db.delete_item_by_drive_id(drive_id)
        self.file_synced.emit(item.rel_path, "Eliminado")

    # -------------------------------------------------------------------------
    # Worker Task Execution
    # -------------------------------------------------------------------------

    def _execute_task(self, task: SyncTask) -> None:
        if not self.drive_client:
            return

        full_path = self.config.sync_dir / task.rel_path

        try:
            if task.task_type == TaskType.UPLOAD:
                self._handle_upload(task, full_path)
            elif task.task_type == TaskType.DOWNLOAD:
                self._handle_download(task, full_path)
            elif task.task_type == TaskType.DELETE_REMOTE:
                if task.drive_id:
                    self.drive_client.trash_file(task.drive_id)
                    self.db.delete_item_by_path(task.rel_path)
                    self.file_synced.emit(task.rel_path, "Eliminado en Drive")
            elif task.task_type == TaskType.CREATE_REMOTE_FOLDER:
                self._handle_create_folder(task, full_path)

        except Exception as e:
            err_msg = f"Error en {task.task_type} para {task.rel_path}: {e}"
            print(f"[SyncService] {err_msg}")
            self.db.update_status(task.rel_path, SyncStatus.ERROR, error=str(e))
            self.sync_error.emit(err_msg)

        if self.queue and self.queue.pending_count() == 0:
            self.status_changed.emit("IDLE")

    def _handle_upload(self, task: SyncTask, full_path: Path) -> None:
        if not full_path.exists():
            return

        self.db.update_status(task.rel_path, SyncStatus.UPLOADING)

        def on_prog(done: int, total: int):
            self.progress_updated.emit(full_path.name, done, total)

        existing = self.db.get_item_by_path(task.rel_path)
        existing_id = existing.drive_id if existing else None

        parent_id = "root"
        if "/" in task.rel_path:
            parent_rel = task.rel_path.rsplit("/", 1)[0]
            parent_item = self.db.get_item_by_path(parent_rel)
            if parent_item and parent_item.drive_id:
                parent_id = parent_item.drive_id

        res = self.drive_client.upload_file(
            local_path=full_path,
            parent_id=parent_id,
            existing_file_id=existing_id,
            progress_callback=on_prog,
        )

        item = SyncItem(
            rel_path=task.rel_path,
            item_type=ItemType.FILE,
            drive_id=res.get("id"),
            size=full_path.stat().st_size,
            mtime_local=full_path.stat().st_mtime,
            mtime_remote=res.get("modifiedTime"),
            md5_checksum=res.get("md5Checksum"),
            status=SyncStatus.SYNCED,
        )
        self.db.upsert_item(item)
        self.file_synced.emit(task.rel_path, "Subido")

    def _handle_download(self, task: SyncTask, full_path: Path) -> None:
        if not task.drive_id:
            return

        self.db.update_status(task.rel_path, SyncStatus.DOWNLOADING)

        def on_prog(done: int, total: int):
            self.progress_updated.emit(full_path.name, done, total)

        if self.watcher:
            self.watcher.mark_internal_operation(task.rel_path)

        actual_path = full_path
        try:
            file_meta = task.extra_data.get("file_meta", {})
            mime_type = file_meta.get("mimeType")
            if not mime_type and task.drive_id:
                try:
                    meta = self.drive_client.get_file_metadata(task.drive_id)
                    mime_type = meta.get("mimeType")
                    file_meta.update(meta)
                except Exception:
                    pass
            actual_path = self.drive_client.download_file(
                drive_id=task.drive_id,
                dest_local_path=full_path,
                progress_callback=on_prog,
                mime_type=mime_type,
            )
            rel_path = str(actual_path.relative_to(self.config.sync_dir)).replace("\\", "/")
            if self.watcher and rel_path != task.rel_path:
                self.watcher.mark_internal_operation(rel_path)

            file_size = actual_path.stat().st_size if actual_path.exists() else 0
            mtime_loc = actual_path.stat().st_mtime if actual_path.exists() else 0
            item = SyncItem(
                rel_path=rel_path,
                item_type=ItemType.FILE,
                drive_id=task.drive_id,
                size=file_size,
                mtime_local=mtime_loc,
                mtime_remote=file_meta.get("modifiedTime"),
                md5_checksum=file_meta.get("md5Checksum"),
                status=SyncStatus.SYNCED,
            )
            self.db.upsert_item(item)
            self.file_synced.emit(rel_path, "Descargado")
        finally:
            if self.watcher:
                self.watcher.unmark_internal_operation(task.rel_path)
                try:
                    other_rel = str(actual_path.relative_to(self.config.sync_dir)).replace("\\", "/")
                    if other_rel != task.rel_path:
                        self.watcher.unmark_internal_operation(other_rel)
                except Exception:
                    pass

    def _handle_create_folder(self, task: SyncTask, full_path: Path) -> None:
        parent_id = "root"
        if "/" in task.rel_path:
            parent_rel = task.rel_path.rsplit("/", 1)[0]
            parent_item = self.db.get_item_by_path(parent_rel)
            if parent_item and parent_item.drive_id:
                parent_id = parent_item.drive_id

        folder_id = self.drive_client.create_folder(name=full_path.name, parent_id=parent_id)
        self._folder_cache[folder_id] = task.rel_path

        item = SyncItem(
            rel_path=task.rel_path,
            item_type=ItemType.FOLDER,
            drive_id=folder_id,
            status=SyncStatus.SYNCED,
        )
        self.db.upsert_item(item)
