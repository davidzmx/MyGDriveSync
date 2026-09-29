"""
Preferences Dialog with General settings, OAuth account management, and storage quota.
"""

from __future__ import annotations
import shutil
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QSpinBox,
    QFileDialog,
    QMessageBox,
    QProgressBar,
    QGroupBox,
)

from ..auth.oauth import OAuthManager
from ..config import AppConfig
from ..drive.client import GoogleDriveClient
from ..integrations.autostart import set_autostart, is_autostart_enabled


class PreferencesDialog(QDialog):
    """Preferences and settings dialog."""

    def __init__(
        self,
        config: AppConfig,
        sync_service: Optional[Any] = None,
        oauth: Optional[OAuthManager] = None,
        drive_client: Optional[GoogleDriveClient] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.config = config
        self.sync_service = sync_service
        self.oauth = oauth or (sync_service.oauth if sync_service else OAuthManager(config))
        self.drive_client = drive_client or (sync_service.drive_client if sync_service else None)

        from .. import __version__

        self.setWindowTitle(f"Preferencias - MyGDriveSync v{__version__}")
        self.resize(540, 420)

        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        from .. import __version__
        main_layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: General
        self.tab_general = QWidget()
        self._setup_general_tab()
        self.tabs.addTab(self.tab_general, "General")

        # Tab 2: Cuenta
        self.tab_account = QWidget()
        self._setup_account_tab()
        self.tabs.addTab(self.tab_account, "Cuenta de Google")

        # Bottom layout with version label
        btn_layout = QHBoxLayout()
        lbl_version = QLabel(f"MyGDriveSync v{__version__}")
        lbl_version.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        btn_layout.addWidget(lbl_version)
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton("Guardar")
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self._save_and_close)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        main_layout.addLayout(btn_layout)

    def _setup_general_tab(self):
        layout = QVBoxLayout(self.tab_general)
        layout.setSpacing(14)

        # Sync Folder Group
        folder_group = QGroupBox("Carpeta de sincronización local")
        folder_layout = QVBoxLayout(folder_group)

        h_box = QHBoxLayout()
        self.txt_sync_dir = QLineEdit()
        self.btn_browse = QPushButton("Examinar...")
        self.btn_browse.clicked.connect(self._browse_folder)
        h_box.addWidget(self.txt_sync_dir)
        h_box.addWidget(self.btn_browse)
        folder_layout.addLayout(h_box)

        lbl_folder_info = QLabel("Los archivos de Google Drive se sincronizarán en este directorio local.")
        lbl_folder_info.setStyleSheet("color: gray; font-size: 11px;")
        folder_layout.addWidget(lbl_folder_info)
        layout.addWidget(folder_group)

        # Sync Options Group
        sync_group = QGroupBox("Comportamiento del sistema")
        sync_layout = QVBoxLayout(sync_group)

        self.chk_autostart = QCheckBox("Iniciar MyGDriveSync automáticamente al encender el equipo")
        sync_layout.addWidget(self.chk_autostart)

        poll_box = QHBoxLayout()
        poll_box.addWidget(QLabel("Intervalo de comprobación en la nube (segundos):"))
        self.spin_poll = QSpinBox()
        self.spin_poll.setRange(10, 3600)
        self.spin_poll.setValue(30)
        poll_box.addWidget(self.spin_poll)
        poll_box.addStretch()
        sync_layout.addLayout(poll_box)

        layout.addWidget(sync_group)
        layout.addStretch()

    def _setup_account_tab(self):
        layout = QVBoxLayout(self.tab_account)
        layout.setSpacing(14)

        self.account_group = QGroupBox("Estado de la cuenta")
        acc_layout = QVBoxLayout(self.account_group)

        self.lbl_user_email = QLabel("No hay ninguna cuenta conectada.")
        self.lbl_user_email.setStyleSheet("font-weight: bold; font-size: 13px;")
        acc_layout.addWidget(self.lbl_user_email)

        # Quota progress
        self.lbl_quota = QLabel("")
        self.progress_quota = QProgressBar()
        self.progress_quota.setRange(0, 100)
        acc_layout.addWidget(self.lbl_quota)
        acc_layout.addWidget(self.progress_quota)

        # Buttons
        btn_box = QHBoxLayout()
        self.btn_login = QPushButton("Iniciar sesión con Google")
        self.btn_login.clicked.connect(self._login_flow)
        self.btn_logout = QPushButton("Cerrar sesión")
        self.btn_logout.clicked.connect(self._logout)
        btn_box.addWidget(self.btn_login)
        btn_box.addWidget(self.btn_logout)
        btn_box.addStretch()
        acc_layout.addLayout(btn_box)

        layout.addWidget(self.account_group)

        # OAuth Credentials config Group
        oauth_group = QGroupBox("Configuración de credenciales de Google Cloud")
        oauth_layout = QVBoxLayout(oauth_group)
        lbl_oauth = QLabel(
            "Para conectar tu cuenta personal, puedes importar tu archivo client_secrets.json "
            "obtenido desde la consola de Google Cloud (OAuth 2.0 Client ID para Desktop)."
        )
        lbl_oauth.setWordWrap(True)
        lbl_oauth.setStyleSheet("color: gray; font-size: 11px;")
        oauth_layout.addWidget(lbl_oauth)

        btn_import_creds = QPushButton("Importar archivo client_secrets.json...")
        btn_import_creds.clicked.connect(self._import_client_secrets)
        oauth_layout.addWidget(btn_import_creds)

        layout.addWidget(oauth_group)
        layout.addStretch()

    def _load_values(self):
        self.txt_sync_dir.setText(str(self.config.sync_dir))
        self.chk_autostart.setChecked(is_autostart_enabled())
        self.spin_poll.setValue(self.config.poll_interval)
        self._refresh_account_info()

    def _refresh_account_info(self):
        creds = self.oauth.get_valid_credentials()
        if creds:
            if not self.drive_client and self.sync_service:
                self.sync_service.initialize()
                self.drive_client = self.sync_service.drive_client
            elif not self.drive_client:
                self.drive_client = GoogleDriveClient(creds)

            if self.drive_client:
                try:
                    about = self.drive_client.get_about()
                    user = about.get("user", {})
                    email = user.get("emailAddress", "Conectado")
                    name = user.get("displayName", "")
                    self.lbl_user_email.setText(f"👤 {name} ({email})")

                    quota = about.get("storageQuota", {})
                    usage = int(quota.get("usage", 0))
                    limit = int(quota.get("limit", 0))

                    if limit > 0:
                        pct = int((usage / limit) * 100)
                        self.progress_quota.setValue(pct)
                        usage_gb = usage / (1024 ** 3)
                        limit_gb = limit / (1024 ** 3)
                        self.lbl_quota.setText(f"Espacio utilizado: {usage_gb:.2f} GB de {limit_gb:.1f} GB ({pct}%)")
                        self.progress_quota.show()
                    else:
                        self.progress_quota.hide()
                        self.lbl_quota.setText(f"Espacio utilizado: {usage / (1024**3):.2f} GB (Ilimitado)")

                    self.btn_login.setEnabled(False)
                    self.btn_logout.setEnabled(True)
                    return
                except Exception as e:
                    print(f"[PreferencesDialog] Error fetching account info: {e}")
                    self.lbl_user_email.setText("👤 Sesión iniciada con Google Drive")
                    self.btn_login.setEnabled(False)
                    self.btn_logout.setEnabled(True)
                    return

        # Not authenticated
        self.lbl_user_email.setText("⚠️ No has iniciado sesión con Google.")
        self.progress_quota.hide()
        self.lbl_quota.setText("")
        self.btn_login.setEnabled(True)
        self.btn_logout.setEnabled(False)

    def _browse_folder(self):
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar carpeta de sincronización",
            str(self.config.sync_dir),
        )
        if chosen:
            self.txt_sync_dir.setText(chosen)

    def _import_client_secrets(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar client_secrets.json",
            str(Path.home()),
            "Archivos JSON (*.json)",
        )
        if path:
            dest = self.config.client_secrets_file
            try:
                shutil.copy2(path, str(dest))
                QMessageBox.information(
                    self,
                    "Credenciales importadas",
                    f"El archivo de credenciales se ha guardado en:\n{dest}\n\nAhora puedes pulsar 'Iniciar sesión con Google'.",
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo copiar el archivo: {e}")

    def _login_flow(self):
        if not self.config.client_secrets_file.exists():
            QMessageBox.warning(
                self,
                "Faltan credenciales",
                "Por favor importa primero tu archivo 'client_secrets.json' usando el botón inferior.",
            )
            return

        try:
            self.oauth.start_auth_flow()
            if self.sync_service:
                self.sync_service.initialize()
                self.drive_client = self.sync_service.drive_client
            elif not self.drive_client:
                creds = self.oauth.get_valid_credentials()
                if creds:
                    self.drive_client = GoogleDriveClient(creds)

            self._refresh_account_info()

            # Check if selective sync has already been configured
            has_rules = bool(self.sync_service and self.sync_service.db.get_all_sync_folders())

            if not has_rules:
                QMessageBox.information(
                    self,
                    "Sesión iniciada con éxito",
                    "¡Cuenta de Google Drive vinculada con éxito!\n\n"
                    "A continuación, selecciona qué carpetas deseas sincronizar en este equipo.",
                )
                from .selective_sync_dialog import SelectiveSyncDialog
                sel_dialog = SelectiveSyncDialog(
                    db=self.sync_service.db if self.sync_service else None,
                    drive_client=self.drive_client,
                    sync_dir=self.config.sync_dir,
                    sync_service=self.sync_service,
                    parent=self,
                )
                sel_dialog.exec()
                if self.sync_service:
                    self.sync_service.start()
            else:
                if self.sync_service:
                    self.sync_service.start()
                QMessageBox.information(
                    self,
                    "Sesión iniciada",
                    "¡Cuenta de Google Drive vinculada con éxito!\nLa sincronización está activa.",
                )
        except Exception as e:
            QMessageBox.critical(self, "Error de autenticación", str(e))

    def _logout(self):
        reply = QMessageBox.question(
            self,
            "Cerrar sesión",
            "¿Estás seguro de que deseas desconectar tu cuenta de Google Drive?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            if self.sync_service:
                self.sync_service.stop()
                self.sync_service.drive_client = None
                self.sync_service.status_changed.emit("NO_AUTH")
            self.drive_client = None
            self.oauth.logout()
            self._refresh_account_info()
            QMessageBox.information(self, "Sesión cerrada", "La cuenta ha sido desconectada.")

    def _save_and_close(self):
        new_path = Path(self.txt_sync_dir.text().strip())
        if not new_path.exists():
            try:
                new_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Error de ruta", f"No se pudo crear la carpeta: {e}")
                return

        self.config.sync_dir = new_path
        self.config.set("poll_interval_seconds", self.spin_poll.value())

        # Autostart
        autostart_active = self.chk_autostart.isChecked()
        self.config.set("autostart", autostart_active)
        set_autostart(autostart_active)

        self.accept()
