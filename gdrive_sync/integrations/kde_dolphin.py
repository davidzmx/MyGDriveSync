"""
KDE Plasma / Dolphin integration via KIO Service Menus (.desktop actions).
Adds right-click options in Dolphin to view files on Google Drive Web and copy links.
"""

from __future__ import annotations
import os
import sys
from pathlib import Path

SERVICE_MENU_NAME = "gdrive_sync_dolphin.desktop"


def get_kio_servicemenu_dir() -> Path:
    """Returns ~/.local/share/kio/servicemenus directory."""
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        base = Path(xdg_data)
    else:
        base = Path.home() / ".local" / "share"
    menu_dir = base / "kio" / "servicemenus"
    menu_dir.mkdir(parents=True, exist_ok=True)
    return menu_dir


def install_dolphin_service_menu() -> bool:
    """Installs the Dolphin context menu .desktop file for KDE."""
    if sys.platform != "linux":
        return False

    menu_dir = get_kio_servicemenu_dir()
    desktop_file = menu_dir / SERVICE_MENU_NAME

    # Check if packaged binary exists, otherwise use current python runner
    if Path("/usr/bin/gdrive-sync").exists():
        exec_cmd = "/usr/bin/gdrive-sync"
    else:
        exec_cmd = f"{sys.executable} -m gdrive_sync.main"

    content = f"""[Desktop Entry]
Type=Service
ServiceTypes=KonqPopupMenu/Plugin
MimeType=all/allfiles;inode/directory;
Actions=openInGDriveWeb;copyGDriveLink;
X-KDE-Submenu=MyGDriveSync
X-KDE-Priority=TopLevel

[Desktop Action openInGDriveWeb]
Name=Abrir en Google Drive (Web)
Icon=internet-web-browser
Exec={exec_cmd} --dolphin-open "%u"

[Desktop Action copyGDriveLink]
Name=Copiar enlace web de Drive
Icon=edit-copy
Exec={exec_cmd} --dolphin-copy "%u"
"""
    try:
        desktop_file.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        print(f"[KDE Dolphin] Error writing service menu: {e}")
        return False


def uninstall_dolphin_service_menu() -> bool:
    if sys.platform != "linux":
        return False
    desktop_file = get_kio_servicemenu_dir() / SERVICE_MENU_NAME
    if desktop_file.exists():
        try:
            desktop_file.unlink()
            return True
        except Exception:
            return False
    return True


def handle_dolphin_action(args_list: list[str]) -> None:
    """Handles Dolphin right-click actions without needing separate script."""
    import argparse
    import urllib.parse
    import webbrowser
    from ..config import AppConfig
    from ..database.manager import DatabaseManager

    parser = argparse.ArgumentParser(description="Dolphin KIO Service Menu Handler")
    parser.add_argument("--dolphin-open", help="Open file in Google Drive Web")
    parser.add_argument("--dolphin-copy", help="Copy Google Drive Web link to clipboard")
    args, _ = parser.parse_known_args(args_list)

    config = AppConfig()
    db = DatabaseManager(config.db_path)

    raw_path = args.dolphin_open or args.dolphin_copy
    if not raw_path:
        return

    # Unquote URL (file:///path/to/file)
    parsed = urllib.parse.urlparse(raw_path)
    if parsed.scheme == "file":
        local_file = Path(urllib.parse.unquote(parsed.path))
    else:
        local_file = Path(raw_path)

    try:
        rel_path = str(local_file.resolve().relative_to(config.sync_dir.resolve()))
        item = db.get_item_by_path(rel_path)
        if item and item.drive_id:
            web_url = f"https://drive.google.com/open?id={item.drive_id}"
            if args.dolphin_open:
                webbrowser.open(web_url)
            elif args.dolphin_copy:
                from PySide6.QtWidgets import QApplication
                app = QApplication.instance() or QApplication(sys.argv)
                app.clipboard().setText(web_url)
        else:
            if args.dolphin_open:
                webbrowser.open("https://drive.google.com")
    except Exception as e:
        print(f"Error handling file action: {e}")


def main():
    handle_dolphin_action(sys.argv)


if __name__ == "__main__":
    main()
