"""
Selective Sync dialog allowing the user to check/uncheck Google Drive folders to sync.
"""

from __future__ import annotations
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Set

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QPushButton,
    QMessageBox,
    QProgressBar,
)

from ..database.manager import DatabaseManager
from ..database.models import SyncFolder
from ..drive.client import GoogleDriveClient


class SelectiveSyncDialog(QDialog):
    """Dialog for choosing which folders to download locally (Dropbox selective sync)."""

    def __init__(
        self,
        db: DatabaseManager,
        drive_client: Optional[GoogleDriveClient] = None,
        sync_dir: Path = None,
        sync_service: Optional[Any] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.db = db
        self.sync_service = sync_service
        self.drive_client = drive_client or (sync_service.drive_client if sync_service else None)
        self.sync_dir = Path(sync_dir)

        self.setWindowTitle("Sincronización Selectiva - MyGDriveSync")
        self.resize(520, 560)

        # Folder ID -> QTreeWidgetItem
        self._items_by_id: Dict[str, QTreeWidgetItem] = {}
        self._folder_paths: Dict[str, str] = {}

        self._setup_ui()
        self.load_folders()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info_label = QLabel(
            "Selecciona las carpetas de Google Drive que deseas sincronizar en este equipo.\n"
            "Las carpetas desmarcadas no ocuparán espacio en tu disco local."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Carpetas de Google Drive"])
        self.tree.setAnimated(True)
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree)

        # Button row 1 (Selection helpers)
        btn_helpers_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Seleccionar todas")
        self.btn_select_all.clicked.connect(self._select_all)
        self.btn_deselect_all = QPushButton("Deseleccionar todas")
        self.btn_deselect_all.clicked.connect(self._deselect_all)
        self.btn_refresh = QPushButton("Actualizar")
        self.btn_refresh.clicked.connect(self.load_folders)

        btn_helpers_layout.addWidget(self.btn_select_all)
        btn_helpers_layout.addWidget(self.btn_deselect_all)
        btn_helpers_layout.addStretch()
        btn_helpers_layout.addWidget(self.btn_refresh)
        layout.addLayout(btn_helpers_layout)

        # Button row 2 (Dialog actions)
        btn_action_layout = QHBoxLayout()
        btn_action_layout.addStretch()

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton("Guardar cambios")
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self._save_changes)

        btn_action_layout.addWidget(self.btn_cancel)
        btn_action_layout.addWidget(self.btn_save)
        layout.addLayout(btn_action_layout)

    def load_folders(self):
        """Fetches remote folders and populates the tree."""
        if not self.drive_client and self.sync_service:
            self.drive_client = self.sync_service.drive_client

        if not self.drive_client:
            self.tree.clear()
            placeholder = QTreeWidgetItem(["⚠️ Inicia sesión con Google para cargar tus carpetas"])
            placeholder.setFlags(Qt.NoItemFlags)
            self.tree.addTopLevelItem(placeholder)
            return

        self.tree.clear()
        self._items_by_id.clear()
        self.progress_bar.show()
        self.setEnabled(False)

        try:
            folders = self.drive_client.list_all_folders()
            self._folder_paths = self.drive_client.build_folder_paths(folders)

            # Resolve actual root ID from Google Drive
            root_id = "root"
            try:
                res = self.drive_client.service.files().get(fileId="root", fields="id").execute()
                root_id = res.get("id", "root")
            except Exception:
                pass

            id_to_folder = {f["id"]: f for f in folders}

            # Get current DB rules: folder_id -> is_synced
            existing_rules = {f.drive_id: f.is_synced for f in self.db.get_all_sync_folders()}

            # Item 0: Root files (archivos sin carpeta)
            root_files_item = QTreeWidgetItem()
            root_files_item.setText(0, "📄 Archivos en la raíz de Google Drive (sin carpeta)")
            root_files_item.setData(0, Qt.UserRole, "__ROOT_FILES__")
            root_files_item.setFlags(root_files_item.flags() | Qt.ItemIsUserCheckable)
            root_files_synced = existing_rules.get("__ROOT_FILES__", False)
            root_files_item.setCheckState(0, Qt.Checked if root_files_synced else Qt.Unchecked)
            self._items_by_id["__ROOT_FILES__"] = root_files_item
            self.tree.addTopLevelItem(root_files_item)

            # Build tree hierarchy
            # Group by parent
            children_map: Dict[str, List[dict]] = {}
            for f in folders:
                parents = f.get("parents")
                if not parents or parents[0] in ("root", root_id) or parents[0] not in id_to_folder:
                    p_id = "__TOP_LEVEL__"
                else:
                    p_id = parents[0]
                children_map.setdefault(p_id, []).append(f)

            def add_children(parent_id: str, parent_widget_item: Optional[QTreeWidgetItem]):
                sorted_children = sorted(children_map.get(parent_id, []), key=lambda x: x.get("name", "").lower())
                for child in sorted_children:
                    item = QTreeWidgetItem()
                    item.setText(0, f"📁 {child.get('name', 'Carpeta')}")
                    item.setData(0, Qt.UserRole, child["id"])
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)

                    # Determine initial checked state: use existing rule if present
                    is_synced = existing_rules.get(child["id"], True if not existing_rules else False)
                    item.setCheckState(0, Qt.Checked if is_synced else Qt.Unchecked)

                    self._items_by_id[child["id"]] = item

                    if parent_widget_item:
                        parent_widget_item.addChild(item)
                    else:
                        self.tree.addTopLevelItem(item)

                    add_children(child["id"], item)

            add_children("__TOP_LEVEL__", None)
            self.tree.expandToDepth(0)

        except Exception as e:
            QMessageBox.critical(self, "Error al cargar carpetas", str(e))
        finally:
            self.progress_bar.hide()
            self.setEnabled(True)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        """Propagates check state to child items recursively."""
        state = item.checkState(0)
        self.tree.blockSignals(True)
        for i in range(item.childCount()):
            child = item.child(i)
            child.setCheckState(0, state)
        self.tree.blockSignals(False)

    def _select_all(self):
        self.tree.blockSignals(True)
        for item in self._items_by_id.values():
            item.setCheckState(0, Qt.Checked)
        self.tree.blockSignals(False)

    def _deselect_all(self):
        self.tree.blockSignals(True)
        for item in self._items_by_id.values():
            item.setCheckState(0, Qt.Unchecked)
        self.tree.blockSignals(False)

    def _save_changes(self):
        """Applies selective sync rules and frees local space for unchecked folders."""
        unselected_paths: List[str] = []
        sync_root_files = False

        for folder_id, item in self._items_by_id.items():
            is_synced = item.checkState(0) == Qt.Checked
            if folder_id == "__ROOT_FILES__":
                sync_root_files = is_synced
                self.db.set_folder_sync_state(
                    drive_id="__ROOT_FILES__",
                    rel_path="__ROOT_FILES__",
                    is_synced=is_synced,
                )
                continue

            rel_path = self._folder_paths.get(folder_id, "")
            if rel_path:
                self.db.set_folder_sync_state(
                    drive_id=folder_id,
                    rel_path=rel_path,
                    is_synced=is_synced,
                )
                if not is_synced:
                    unselected_paths.append(rel_path)

        # Safely apply through sync_service if available
        if self.sync_service:
            self.sync_service.apply_selective_sync(unselected_paths, sync_root_files=sync_root_files)
        else:
            for rel in unselected_paths:
                local_folder = self.sync_dir / rel
                if local_folder.exists() and local_folder.is_dir():
                    try:
                        shutil.rmtree(str(local_folder), ignore_errors=True)
                    except Exception as e:
                        print(f"[SelectiveSync] Could not remove unchecked folder {local_folder}: {e}")

        QMessageBox.information(
            self,
            "Sincronización selectiva guardada",
            "La configuración de sincronización selectiva se ha actualizado correctamente.",
        )
        self.accept()
