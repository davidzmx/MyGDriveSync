"""
Utility functions for file hashing, path manipulations, and lock checks.
"""

from __future__ import annotations
import hashlib
import os
import time
from pathlib import Path
from typing import Optional


def calculate_md5(file_path: Path | str, chunk_size: int = 64 * 1024) -> str:
    """Calculates MD5 checksum of a local file in chunks."""
    p = Path(file_path)
    if not p.is_file():
        return ""
    md5 = hashlib.md5()
    with open(p, "rb") as f:
        while chunk := f.read(chunk_size):
            md5.update(chunk)
    return md5.hexdigest()


def is_file_ready(file_path: Path | str, wait_timeout: float = 2.0) -> bool:
    """
    Checks if a file is ready to read and not locked or being actively written to.
    """
    p = Path(file_path)
    if not p.exists() or not p.is_file():
        return False

    start_time = time.time()
    last_size = -1

    while time.time() - start_time < wait_timeout:
        try:
            curr_size = p.stat().st_size
            if curr_size == last_size:
                # Size has stabilized, test open for reading
                with open(p, "rb"):
                    return True
            last_size = curr_size
        except (OSError, PermissionError):
            pass
        time.sleep(0.3)

    return False


def is_ignored_filename(name: str) -> bool:
    """
    Determines if a file or directory name should be ignored from syncing
    (temporary files, office lock files, git, etc.)
    """
    if name.startswith((".", "~$", "~")):
        return True
    if name.endswith((".tmp", ".swp", ".sync_tmp", ".crdownload", ".part")):
        return True
    ignored_names = {
        "desktop.ini",
        "thumbs.db",
        ".ds_store",
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
    }
    return name.lower() in ignored_names
