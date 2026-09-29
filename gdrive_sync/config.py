"""
Configuration management for gdrive-sync across Linux and Windows.
"""

from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

APP_NAME = "mygdrivesync"
APP_DISPLAY_NAME = "MyGDriveSync"


def get_app_dir() -> Path:
    """Returns the platform-specific application data directory."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            path = Path(base) / APP_NAME
        else:
            path = Path.home() / "AppData" / "Roaming" / APP_NAME
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        # Linux / XDG standard
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            path = Path(xdg_config) / APP_NAME
        else:
            path = Path.home() / ".config" / APP_NAME

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_default_sync_dir() -> Path:
    """Returns the default local directory where files will be synchronized."""
    default_dir = Path.home() / "MyGDriveSync"
    return default_dir


class AppConfig:
    """Manages persistent user configuration."""

    DEFAULT_SETTINGS: Dict[str, Any] = {
        "sync_dir": str(get_default_sync_dir()),
        "poll_interval_seconds": 30,
        "debounce_seconds": 2.0,
        "max_concurrent_transfers": 3,
        "autostart": True,
        "notifications_enabled": True,
        "account_email": None,
        "last_page_token": None,
    }

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or get_app_dir()
        self.settings_file = self.config_dir / "settings.json"
        self.db_path = self.config_dir / "sync_state.db"
        self.token_file = self.config_dir / "token.json"
        self.client_secrets_file = self.config_dir / "client_secrets.json"
        self._data: Dict[str, Any] = dict(self.DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        """Loads configuration from JSON file."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self._data.update(saved)
            except Exception as e:
                print(f"[Config] Error loading settings: {e}")
        else:
            self.save()

    def save(self) -> None:
        """Saves current configuration to JSON file."""
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Error saving settings: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    @property
    def sync_dir(self) -> Path:
        return Path(self.get("sync_dir"))

    @sync_dir.setter
    def sync_dir(self, path: Path | str) -> None:
        self.set("sync_dir", str(path))

    @property
    def poll_interval(self) -> int:
        return int(self.get("poll_interval_seconds", 30))

    @property
    def debounce_seconds(self) -> float:
        return float(self.get("debounce_seconds", 2.0))

    @property
    def max_concurrent_transfers(self) -> int:
        return int(self.get("max_concurrent_transfers", 3))

    @property
    def autostart(self) -> bool:
        return bool(self.get("autostart", True))

    @property
    def last_page_token(self) -> Optional[str]:
        return self.get("last_page_token")

    @last_page_token.setter
    def last_page_token(self, token: Optional[str]) -> None:
        self.set("last_page_token", token)
