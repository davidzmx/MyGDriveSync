"""
Local filesystem watcher using watchdog with event debouncing and loop prevention.
"""

from __future__ import annotations
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional, Set

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .utils import is_file_ready, is_ignored_filename
from ..database.manager import DatabaseManager


class LocalFileWatcher:
    """Watches the local sync folder for changes, debounces rapid writes, and invokes callbacks."""

    def __init__(
        self,
        sync_dir: Path | str,
        db: DatabaseManager,
        on_change_callback: Callable[[str, str], None],
        debounce_seconds: float = 2.0,
    ):
        self.sync_dir = Path(sync_dir).resolve()
        self.db = db
        self.on_change = on_change_callback
        self.debounce_seconds = debounce_seconds

        self._observer: Optional[Observer] = None
        self._internal_operations: Set[str] = set()
        self._internal_lock = threading.Lock()

        # Debouncing structures: rel_path -> (due_timestamp, event_type)
        self._pending_events: Dict[str, tuple[float, str]] = {}
        self._debounce_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._debounce_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Starts the filesystem observer and the debounce processor."""
        self.sync_dir.mkdir(parents=True, exist_ok=True)
        self._stop_event.clear()

        # Start debounce worker
        self._debounce_thread = threading.Thread(
            target=self._debounce_loop,
            name="WatcherDebounceWorker",
            daemon=True,
        )
        self._debounce_thread.start()

        # Start watchdog observer
        handler = _SyncEventHandler(self)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.sync_dir), recursive=True)
        self._observer.start()

    def stop(self) -> None:
        """Stops the observer and threads gracefully."""
        self._stop_event.set()
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=3.0)
            except Exception:
                pass
            self._observer = None

        if self._debounce_thread:
            self._debounce_thread.join(timeout=3.0)
            self._debounce_thread = None

    def mark_internal_operation(self, rel_path: str) -> None:
        """Marks a path as an internal write (e.g. from cloud download) to prevent loop events."""
        with self._internal_lock:
            self._internal_operations.add(rel_path.replace("\\", "/").strip("/"))

    def unmark_internal_operation(self, rel_path: str) -> None:
        with self._internal_lock:
            self._internal_operations.discard(rel_path.replace("\\", "/").strip("/"))

    def is_internal_operation(self, rel_path: str) -> bool:
        with self._internal_lock:
            return rel_path.replace("\\", "/").strip("/") in self._internal_operations

    def queue_event(self, rel_path: str, event_type: str) -> None:
        """Queues an event to be debounced."""
        norm_path = rel_path.replace("\\", "/").strip("/")
        if not norm_path:
            return

        # Check ignored filenames in path parts
        for part in norm_path.split("/"):
            if is_ignored_filename(part):
                return

        # Check selective sync
        if not self.db.is_path_selected_for_sync(norm_path):
            return

        # If it's our own download or write, ignore it
        if self.is_internal_operation(norm_path):
            return

        with self._debounce_lock:
            due_time = time.time() + self.debounce_seconds
            self._pending_events[norm_path] = (due_time, event_type)

    def _debounce_loop(self) -> None:
        """Checks for expired debounced events and fires the callback."""
        while not self._stop_event.is_set():
            now = time.time()
            to_fire = []

            with self._debounce_lock:
                for path, (due_time, ev_type) in list(self._pending_events.items()):
                    if now >= due_time:
                        to_fire.append((path, ev_type))
                        del self._pending_events[path]

            for path, ev_type in to_fire:
                # If deleted, fire right away
                if ev_type == "deleted":
                    self.on_change(path, ev_type)
                else:
                    full_path = self.sync_dir / path
                    if full_path.is_file():
                        # Ensure write completed and file is readable
                        if is_file_ready(full_path, wait_timeout=1.5):
                            self.on_change(path, ev_type)
                    elif full_path.is_dir():
                        self.on_change(path, ev_type)

            time.sleep(0.4)


class _SyncEventHandler(FileSystemEventHandler):
    """Translates Watchdog filesystem events into relative path sync events."""

    def __init__(self, watcher: LocalFileWatcher):
        super().__init__()
        self.watcher = watcher

    def _to_rel_path(self, full_path: str) -> Optional[str]:
        try:
            p = Path(full_path).resolve()
            rel = p.relative_to(self.watcher.sync_dir)
            return str(rel).replace("\\", "/").strip("/")
        except ValueError:
            return None

    def on_created(self, event: FileSystemEvent) -> None:
        rel = self._to_rel_path(event.src_path)
        if rel:
            self.watcher.queue_event(rel, "created")

    def on_modified(self, event: FileSystemEvent) -> None:
        rel = self._to_rel_path(event.src_path)
        if rel:
            self.watcher.queue_event(rel, "modified")

    def on_deleted(self, event: FileSystemEvent) -> None:
        rel = self._to_rel_path(event.src_path)
        if rel:
            self.watcher.queue_event(rel, "deleted")

    def on_moved(self, event: FileSystemEvent) -> None:
        src_rel = self._to_rel_path(event.src_path)
        dest_rel = self._to_rel_path(getattr(event, "dest_path", ""))
        if src_rel:
            self.watcher.queue_event(src_rel, "deleted")
        if dest_rel:
            self.watcher.queue_event(dest_rel, "created")
