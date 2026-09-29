"""
Cross-platform autostart management (Linux XDG autostart & Windows Registry).
"""

from __future__ import annotations
import os
import sys
from pathlib import Path

AUTOSTART_NAME = "mygdrivesync"


def _get_linux_desktop_file() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        base = Path(config_home)
    else:
        base = Path.home() / ".config"
    autostart_dir = base / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    return autostart_dir / f"{AUTOSTART_NAME}.desktop"


def is_autostart_enabled() -> bool:
    """Checks if autostart is currently configured."""
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ,
            )
            try:
                winreg.QueryValueEx(key, AUTOSTART_NAME)
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception:
            return False
    else:
        # Linux
        f = _get_linux_desktop_file()
        return f.exists()


def set_autostart(enable: bool) -> bool:
    """Enables or disables system autostart."""
    command = f'"{sys.executable}" -m gdrive_sync.main'

    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            )
            try:
                if enable:
                    winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ, command)
                else:
                    try:
                        winreg.DeleteValue(key, AUTOSTART_NAME)
                    except FileNotFoundError:
                        pass
                return True
            finally:
                winreg.CloseKey(key)
        except Exception as e:
            print(f"[Autostart] Windows registry error: {e}")
            return False
    else:
        # Linux .desktop file in ~/.config/autostart/
        f = _get_linux_desktop_file()
        if enable:
            content = f"""[Desktop Entry]
Type=Application
Version=1.0
Name=MyGDriveSync
GenericName=File Synchronizer
Comment=Dropbox-like synchronization client for Google Drive
Exec={command}
Icon=drive-multimedia
Terminal=false
Categories=Network;FileTransfer;
StartupNotify=false
X-GNOME-Autostart-enabled=true
"""
            try:
                f.write_text(content, encoding="utf-8")
                return True
            except Exception as e:
                print(f"[Autostart] Linux autostart write error: {e}")
                return False
        else:
            if f.exists():
                try:
                    f.unlink()
                except Exception:
                    pass
            return True
