"""
Recent sync activity and transfers monitor dialog.
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QProgressBar,
)

from ..database.manager import DatabaseManager
from ..database.models import SyncStatus


class ActivityDialog(QDialog):
    """Displays real-time transfer progress and recent synchronization history."""

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db

        self.setWindowTitle("Actividad Reciente - MyGDriveSync")
        self.resize(620, 420)

        self._setup_ui()
        self.refresh_history()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Active transfer status header
        self.lbl_active = QLabel("Sincronización al día.")
        self.lbl_active.setStyleSheet("font-weight: bold; font-size: 13px; color: #1a73e8;")
        layout.addWidget(self.lbl_active)

        self.progress_active = QProgressBar()
        self.progress_active.setRange(0, 100)
        self.progress_active.hide()
        layout.addWidget(self.progress_active)

        # Table of history
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Archivo / Carpeta", "Estado", "Tamaño", "Fecha de actualización"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_refresh = QPushButton("Actualizar historial")
        self.btn_refresh.clicked.connect(self.refresh_history)
        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

    def refresh_history(self):
        """Loads recent items from SQLite database."""
        items = self.db.list_items(limit=100)
        self.table.setRowCount(len(items))

        for row, it in enumerate(items):
            # Path
            it_name = QTableWidgetItem(it.rel_path)
            self.table.setItem(row, 0, it_name)

            # Status
            status_text = {
                SyncStatus.SYNCED: "✓ Sincronizado",
                SyncStatus.QUEUED_UPLOAD: "⏳ Pendiente subida",
                SyncStatus.UPLOADING: "⬆ Subiendo...",
                SyncStatus.QUEUED_DOWNLOAD: "⏳ Pendiente descarga",
                SyncStatus.DOWNLOADING: "⬇ Descargando...",
                SyncStatus.CONFLICT: "⚠️ Conflicto",
                SyncStatus.ERROR: "❌ Error",
            }.get(it.status, it.status.value)

            status_item = QTableWidgetItem(status_text)
            self.table.setItem(row, 1, status_item)

            # Size
            size_str = self._format_size(it.size)
            size_item = QTableWidgetItem(size_str)
            self.table.setItem(row, 2, size_item)

            # Date
            dt_str = datetime.fromtimestamp(it.updated_at).strftime("%Y-%m-%d %H:%M:%S")
            date_item = QTableWidgetItem(dt_str)
            self.table.setItem(row, 3, date_item)

    def update_active_progress(self, filename: str, done: int, total: int):
        """Called dynamically from Qt signal."""
        if total > 0:
            pct = int((done / total) * 100)
            self.lbl_active.setText(f"Sincronizando {filename} ({pct}%)")
            self.progress_active.setValue(pct)
            self.progress_active.show()
        else:
            self.progress_active.hide()
            self.lbl_active.setText("Sincronización al día.")

    @staticmethod
    def _format_size(bytes_val: int) -> str:
        if bytes_val <= 0:
            return "-"
        for unit in ["B", "KB", "MB", "GB"]:
            if bytes_val < 1024:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.1f} TB"
