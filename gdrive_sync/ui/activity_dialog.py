"""
Recent sync activity and transfers monitor dialog.
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QColor
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
    QMessageBox,
)

from ..database.manager import DatabaseManager
from ..database.models import SyncStatus


class ActivityDialog(QDialog):
    """Displays real-time transfer progress and recent synchronization history."""

    def __init__(self, db: DatabaseManager, sync_service: Optional[Any] = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.sync_service = sync_service

        self.setWindowTitle("Actividad Reciente - MyGDriveSync")
        self.resize(680, 440)

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
        self.progress_active.setTextVisible(True)
        self.progress_active.setStyleSheet(
            "QProgressBar { border: 1px solid #bdc3c7; border-radius: 4px; text-align: center; height: 20px; font-size: 11px; font-weight: bold; }"
            "QProgressBar::chunk { background-color: #1a73e8; border-radius: 3px; }"
        )
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
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self.table)

        # Bottom buttons
        btn_layout = QHBoxLayout()

        self.btn_retry = QPushButton("🔄 Reintentar archivos con error")
        self.btn_retry.clicked.connect(self._retry_failed)
        btn_layout.addWidget(self.btn_retry)

        btn_layout.addStretch()

        self.btn_refresh = QPushButton("Actualizar historial")
        self.btn_refresh.clicked.connect(self.refresh_history)
        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

    def _on_cell_double_clicked(self, row: int, col: int):
        path_item = self.table.item(row, 0)
        if not path_item:
            return
        rel_path = path_item.text()
        item = self.db.get_item_by_path(rel_path)
        if item and item.status == SyncStatus.ERROR and item.error_message:
            QMessageBox.warning(
                self,
                "Detalle del error de sincronización",
                f"<b>Archivo:</b> {rel_path}<br><br>"
                f"<b>Mensaje de error:</b><br><pre style='color: #c0392b;'>{item.error_message}</pre>"
                "<br>Puedes pulsar el botón <i>'Reintentar archivos con error'</i> para volver a intentarlo."
            )

    def _retry_failed(self):
        failed_items = [it for it in self.db.list_items(limit=200) if it.status == SyncStatus.ERROR]
        if not failed_items:
            QMessageBox.information(self, "Reintentar", "No hay archivos con errores para reintentar.")
            return

        requeued = 0
        for it in failed_items:
            full_path = (self.sync_service.config.sync_dir / it.rel_path) if self.sync_service else None
            if full_path and full_path.exists():
                self.sync_service.queue.add_task(
                    task_type="upload",
                    rel_path=it.rel_path,
                )
                self.db.update_status(it.rel_path, SyncStatus.QUEUED_UPLOAD, error=None)
                requeued += 1

        self.refresh_history()
        QMessageBox.information(
            self,
            "Reintentar sincronización",
            f"Se han puesto en cola {requeued} archivo(s) para reintentar la subida."
        )

    def refresh_history(self):
        """Loads recent items from SQLite database."""
        items = self.db.list_items(limit=100)
        self.table.setRowCount(len(items))

        for row, it in enumerate(items):
            # Path
            it_name = QTableWidgetItem(it.rel_path)
            self.table.setItem(row, 0, it_name)

            # Status
            if it.status == SyncStatus.ERROR:
                err_msg = it.error_message.strip() if it.error_message else "Error desconocido"
                short_err = (err_msg[:45] + "...") if len(err_msg) > 45 else err_msg
                status_item = QTableWidgetItem(f"❌ Error: {short_err}")
                status_item.setForeground(QColor("#d32f2f"))
                status_item.setToolTip(f"Detalle del error:\n{err_msg}\n\n(Haz doble clic para ver el mensaje completo)")
            else:
                status_text = {
                    SyncStatus.SYNCED: "✓ Sincronizado",
                    SyncStatus.QUEUED_UPLOAD: "⏳ Pendiente subida",
                    SyncStatus.UPLOADING: "⬆ Subiendo...",
                    SyncStatus.QUEUED_DOWNLOAD: "⏳ Pendiente descarga",
                    SyncStatus.DOWNLOADING: "⬇ Descargando...",
                    SyncStatus.CONFLICT: "⚠️ Conflicto",
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

    def update_active_progress(self, filename: str, done: int, total: int, pending: int = 0):
        """Called dynamically from Qt signal."""
        if total > 0 and done < total:
            pct = int((done / total) * 100)
            done_str = self._format_size(done)
            total_str = self._format_size(total)
            pending_text = f" • {pending} archivo(s) restante(s)" if pending > 0 else ""
            self.lbl_active.setText(f"Sincronizando: {filename} ({pct}% • {done_str} de {total_str}){pending_text}")
            self.progress_active.setValue(pct)
            self.progress_active.setFormat(f"{pct}% ({done_str} / {total_str})")
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
