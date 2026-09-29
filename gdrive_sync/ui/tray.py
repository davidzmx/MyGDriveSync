"""
QSystemTrayIcon integration with dynamic state icons and full context menu.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QApplication

from .activity_dialog import ActivityDialog
from .icons import create_tray_icon
from .preferences_dialog import PreferencesDialog
from .selective_sync_dialog import SelectiveSyncDialog
from ..engine.sync_service import SyncService


class GDriveTrayIcon(QSystemTrayIcon):
    """System tray icon running continuously on KDE Plasma and Windows."""

    def __init__(self, sync_service: SyncService, parent=None):
        super().__init__(parent)
        self.service = sync_service
        self.config = sync_service.config
        self.db = sync_service.db

        self._pref_dialog: Optional[PreferencesDialog] = None
        self._sel_dialog: Optional[SelectiveSyncDialog] = None
        self._act_dialog: Optional[ActivityDialog] = None

        self._current_state = "IDLE"

        self._setup_menu()
        self._connect_signals()
        self.update_state("IDLE")

    def _setup_menu(self):
        self.menu = QMenu()

        # Status item (non-clickable header)
        self.action_status = QAction("MyGDriveSync: Iniciando...", self)
        self.action_status.setEnabled(False)
        self.menu.addAction(self.action_status)
        self.menu.addSeparator()

        # Open local folder
        self.action_open_local = QAction("📁 Abrir carpeta local", self)
        self.action_open_local.triggered.connect(self._open_local_folder)
        self.menu.addAction(self.action_open_local)

        # Open Google Drive Web
        self.action_open_web = QAction("🌐 Abrir Google Drive en la web", self)
        self.action_open_web.triggered.connect(self._open_web_drive)
        self.menu.addAction(self.action_open_web)

        self.menu.addSeparator()

        # Pause / Resume
        self.action_pause = QAction("⏸ Pausar sincronización", self)
        self.action_pause.triggered.connect(self._toggle_pause)
        self.menu.addAction(self.action_pause)

        # Sync now
        self.action_sync_now = QAction("🔄 Sincronizar ahora", self)
        self.action_sync_now.triggered.connect(self._sync_now)
        self.menu.addAction(self.action_sync_now)

        # Selective sync
        self.action_selective = QAction("🗂 Sincronización selectiva...", self)
        self.action_selective.triggered.connect(self._open_selective_sync)
        self.menu.addAction(self.action_selective)

        # Recent activity
        self.action_activity = QAction("📊 Actividad reciente...", self)
        self.action_activity.triggered.connect(self._open_activity)
        self.menu.addAction(self.action_activity)

        # Preferences
        self.action_preferences = QAction("⚙ Preferencias...", self)
        self.action_preferences.triggered.connect(self._open_preferences)
        self.menu.addAction(self.action_preferences)

        self.menu.addSeparator()

        # Exit
        self.action_exit = QAction("❌ Salir", self)
        self.action_exit.triggered.connect(self._quit)
        self.menu.addAction(self.action_exit)

        self.setContextMenu(self.menu)

    def _connect_signals(self):
        self.service.status_changed.connect(self.update_state)
        self.service.file_synced.connect(self._on_file_synced)
        self.service.progress_updated.connect(self._on_progress_updated)
        self.activated.connect(self._on_activated)

    def update_state(self, state: str):
        """Updates icon and status description."""
        self._current_state = state
        self.setIcon(create_tray_icon(state))

        desc_map = {
            "IDLE": "Al día",
            "SYNCING": "Sincronizando...",
            "PAUSED": "En pausa",
            "ERROR": "Error de sincronización",
            "NO_AUTH": "Iniciar sesión requerida",
            "STOPPED": "Detenido",
        }
        desc = desc_map.get(state, state)
        self.action_status.setText(f"MyGDriveSync: {desc}")
        self.setToolTip(f"MyGDriveSync - {desc}")

        if state == "PAUSED":
            self.action_pause.setText("▶ Reanudar sincronización")
        else:
            self.action_pause.setText("⏸ Pausar sincronización")

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """Single or double click on tray icon opens local sync folder."""
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._open_local_folder()

    def _open_local_folder(self):
        sync_dir = self.config.sync_dir
        sync_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(sync_dir)))

    def _open_web_drive(self):
        QDesktopServices.openUrl(QUrl("https://drive.google.com"))

    def _toggle_pause(self):
        if self.service.is_paused:
            self.service.resume()
        else:
            self.service.pause()

    def _sync_now(self):
        if self.service.poller:
            self.service.poller.trigger_now()

    def _open_selective_sync(self):
        if not self._sel_dialog or not self._sel_dialog.isVisible():
            self._sel_dialog = SelectiveSyncDialog(
                db=self.db,
                drive_client=self.service.drive_client,
                sync_dir=self.config.sync_dir,
                sync_service=self.service,
            )
            self._sel_dialog.show()
        else:
            self._sel_dialog.raise_()
            self._sel_dialog.activateWindow()

    def _open_preferences(self):
        if not self._pref_dialog or not self._pref_dialog.isVisible():
            self._pref_dialog = PreferencesDialog(
                config=self.config,
                sync_service=self.service,
                oauth=self.service.oauth,
                drive_client=self.service.drive_client,
            )
            self._pref_dialog.show()
        else:
            self._pref_dialog.raise_()
            self._pref_dialog.activateWindow()

    def _open_activity(self):
        if not self._act_dialog or not self._act_dialog.isVisible():
            self._act_dialog = ActivityDialog(db=self.db)
            self._act_dialog.show()
        else:
            self._act_dialog.raise_()
            self._act_dialog.activateWindow()

    def _on_file_synced(self, rel_path: str, action: str):
        if self.config.get("notifications_enabled", True):
            self.showMessage(
                "MyGDriveSync",
                f"{action}: {Path(rel_path).name}",
                QSystemTrayIcon.Information,
                2000,
            )
        if self._act_dialog and self._act_dialog.isVisible():
            self._act_dialog.refresh_history()

    def _on_progress_updated(self, filename: str, done: int, total: int):
        if self._act_dialog and self._act_dialog.isVisible():
            self._act_dialog.update_active_progress(filename, done, total)

    def _quit(self):
        self.service.stop()
        QApplication.quit()
