"""
Main application entry point.
"""

from __future__ import annotations
import signal
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .config import AppConfig, APP_DISPLAY_NAME
from .engine.sync_service import SyncService
from .integrations.kde_dolphin import install_dolphin_service_menu
from .ui.tray import GDriveTrayIcon


def main():
    # Handle Dolphin context menu action invocations directly
    if any(arg in sys.argv for arg in ("--dolphin-open", "--dolphin-copy")):
        from .integrations.kde_dolphin import handle_dolphin_action
        handle_dolphin_action(sys.argv)
        return

    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    app.setApplicationName("mygdrivesync")
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    # Important: keep running in background even when dialogs are closed
    app.setQuitOnLastWindowClosed(False)

    config = AppConfig()

    # Install Dolphin service menus if running on Linux
    if sys.platform == "linux":
        try:
            install_dolphin_service_menu()
        except Exception as e:
            print(f"[Main] Dolphin integration notice: {e}")

    # Initialize sync service
    service = SyncService(config)

    # Create system tray icon
    tray = GDriveTrayIcon(service)
    tray.show()

    # Try starting synchronization
    authenticated = service.start()
    if not authenticated:
        tray.update_state("NO_AUTH")
        tray.showMessage(
            APP_DISPLAY_NAME,
            "Bienvenido a MyGDriveSync. Haz clic derecho en el icono de la bandeja y abre 'Preferencias' para vincular tu cuenta.",
            QSystemTrayIcon.Information,
            5000,
        )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
