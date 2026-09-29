"""
Prioritized job queue and worker pool for asynchronous sync transfers.
"""

from __future__ import annotations
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Callable, Dict, Optional


class TaskPriority(IntEnum):
    HIGH = 1       # Deletions, folder creations
    MEDIUM = 2     # Small files (<10MB)
    LOW = 3        # Large files


class TaskType(str):
    UPLOAD = "upload"
    DOWNLOAD = "download"
    DELETE_LOCAL = "delete_local"
    DELETE_REMOTE = "delete_remote"
    CREATE_REMOTE_FOLDER = "create_remote_folder"


@dataclass(order=True)
class SyncTask:
    priority: int
    task_type: str = field(compare=False)
    rel_path: str = field(compare=False)
    drive_id: Optional[str] = field(default=None, compare=False)
    extra_data: Dict[str, Any] = field(default_factory=dict, compare=False)
    created_at: float = field(default_factory=time.time, compare=False)


class SyncQueue:
    """Thread-safe priority queue with worker threads."""

    def __init__(
        self,
        worker_func: Callable[[SyncTask], None],
        max_workers: int = 3,
    ):
        self._queue: queue.PriorityQueue[SyncTask] = queue.PriorityQueue()
        self.worker_func = worker_func
        self.max_workers = max_workers
        self._workers: list[threading.Thread] = []
        self._stop_event = threading.Event()
        self._active_tasks: set[str] = set()
        self._lock = threading.Lock()

    def start(self) -> None:
        """Starts worker threads."""
        self._stop_event.clear()
        for i in range(self.max_workers):
            t = threading.Thread(
                target=self._worker_loop,
                name=f"SyncWorker-{i+1}",
                daemon=True,
            )
            t.start()
            self._workers.append(t)

    def stop(self) -> None:
        """Stops workers and clears queue."""
        self._stop_event.set()
        # Add poison pills or wake workers
        for _ in self._workers:
            self._queue.put(SyncTask(priority=0, task_type="STOP", rel_path=""))
        for t in self._workers:
            t.join(timeout=2.0)
        self._workers.clear()

    def add_task(
        self,
        task_type: str,
        rel_path: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        drive_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Adds a task if not already in queue or active."""
        with self._lock:
            key = f"{task_type}:{rel_path}"
            if key in self._active_tasks:
                return False
            self._active_tasks.add(key)

        task = SyncTask(
            priority=priority.value,
            task_type=task_type,
            rel_path=rel_path,
            drive_id=drive_id,
            extra_data=extra or {},
        )
        self._queue.put(task)
        return True

    def remove_active(self, task_type: str, rel_path: str) -> None:
        with self._lock:
            self._active_tasks.discard(f"{task_type}:{rel_path}")

    def pending_count(self) -> int:
        return self._queue.qsize()

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                task = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if task.task_type == "STOP" or self._stop_event.is_set():
                self._queue.task_done()
                break

            try:
                self.worker_func(task)
            except Exception as e:
                print(f"[SyncQueue Worker] Error executing task {task.task_type} for {task.rel_path}: {e}")
            finally:
                self.remove_active(task.task_type, task.rel_path)
                self._queue.task_done()
