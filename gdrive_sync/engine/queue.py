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
        self._pause_event = threading.Event()
        self._pause_event.set()  # Initially unpaused
        self._active_tasks: set[str] = set()
        self._lock = threading.Lock()

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def pause(self) -> None:
        """Pauses processing of tasks."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Resumes processing of tasks."""
        self._pause_event.set()

    def start(self) -> None:
        """Starts worker threads."""
        self._stop_event.clear()
        self._pause_event.set()
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
        self._pause_event.set()  # Unblock any paused workers so they can exit
        # Add poison pills or wake workers
        for _ in self._workers:
            self._queue.put(SyncTask(priority=0, task_type="STOP", rel_path=""))
        for t in self._workers:
            t.join(timeout=2.0)
        self._workers.clear()

    def clear_tasks(self, should_remove_cb: Callable[[SyncTask], bool]) -> int:
        """Removes queued tasks matching the given callback and frees active keys."""
        with self._lock:
            temp_list = []
            removed_count = 0
            while not self._queue.empty():
                try:
                    task = self._queue.get_nowait()
                    if should_remove_cb(task):
                        self._active_tasks.discard(f"{task.task_type}:{task.rel_path}")
                        removed_count += 1
                    else:
                        temp_list.append(task)
                except queue.Empty:
                    break

            for task in temp_list:
                self._queue.put(task)
            return removed_count

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
            # Wait if queue is paused
            while not self._pause_event.is_set() and not self._stop_event.is_set():
                self._pause_event.wait(timeout=0.2)

            if self._stop_event.is_set():
                break

            try:
                task = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if task.task_type == "STOP" or self._stop_event.is_set():
                self._queue.task_done()
                break

            # If paused while waiting for task, pause before executing work
            while not self._pause_event.is_set() and not self._stop_event.is_set():
                self._pause_event.wait(timeout=0.2)

            if self._stop_event.is_set():
                self._queue.task_done()
                break

            try:
                self.worker_func(task)
            except Exception as e:
                print(f"[SyncQueue Worker] Error executing task {task.task_type} for {task.rel_path}: {e}")
            finally:
                self.remove_active(task.task_type, task.rel_path)
                self._queue.task_done()
