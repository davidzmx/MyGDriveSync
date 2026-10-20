"""
Recent sync activity and transfers monitor dialog.
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QAction
from PySide6.QtWidgets import (
    QApplication,
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
    QMenu,
    QTextEdit,
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
        self.resize(750, 480)

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
        
        # Allow user to interactively resize every column by dragging the borders
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 230)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(3, 150)

        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        # Context menu for copying text & retrying
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.table)

        # Note on Google Docs limitation
        lbl_docs_note = QLabel(
            "💡 <b>Nota sobre Documentos de Google:</b> Los archivos creados en Google Docs, Sheets o Slides se descargan "
            "en formato Office (<i>.docx, .xlsx, .pptx</i>) como respaldo para lectura sin conexión. "
            "Para editarlos y conservar los cambios en la nube, modifícalos directamente desde la web de Google Drive."
        )
        lbl_docs_note.setWordWrap(True)
        lbl_docs_note.setStyleSheet(
            "background-color: #f1f8fe; border: 1px solid #c2e0ff; border-radius: 4px; "
            "padding: 6px 10px; font-size: 11px; color: #1a5276;"
        )
        layout.addWidget(lbl_docs_note)

        # Bottom buttons
        btn_layout = QHBoxLayout()

        self.btn_retry = QPushButton("🔄 Reintentar archivos con error")
        self.btn_retry.clicked.connect(self._retry_failed)
        btn_layout.addWidget(self.btn_retry)

        btn_layout.addStretch()

        self.btn_refresh = QPushButton("Actualizar historial")
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

    def keyPressEvent(self, event):
        """Allows copying selected cells to clipboard using Ctrl+C."""
        if event.matches(QKeySequence.Copy) or (event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_C):
            self._copy_selection_to_clipboard()
            event.accept()
            return
        super().keyPressEvent(event)

    def _copy_selection_to_clipboard(self):
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            selected_items = self.table.selectedItems()
            if selected_items:
                text = "\t".join(it.text() for it in selected_items)
                QApplication.clipboard().setText(text)
            return

        lines = []
        for r in range(selected_ranges[0].topRow(), selected_ranges[0].bottomRow() + 1):
            row_vals = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                row_vals.append(item.text() if item else "")
            lines.append("\t".join(row_vals))

        if lines:
            QApplication.clipboard().setText("\n".join(lines))

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return

        row = item.row()
        path_item = self.table.item(row, 0)
        status_item = self.table.item(row, 1)
        rel_path = path_item.text() if path_item else ""
        db_item = self.db.get_item_by_path(rel_path) if rel_path else None

        menu = QMenu(self)

        action_copy_row = menu.addAction("📋 Copiar fila seleccionada (Ctrl+C)")
        action_copy_row.triggered.connect(self._copy_selection_to_clipboard)

        action_copy_path = menu.addAction("📋 Copiar ruta del archivo")
        action_copy_path.triggered.connect(lambda: QApplication.clipboard().setText(rel_path))

        if db_item and db_item.status == SyncStatus.ERROR and db_item.error_message:
            action_copy_err = menu.addAction("📋 Copiar mensaje de error completo")
            action_copy_err.triggered.connect(lambda: QApplication.clipboard().setText(db_item.error_message))

            action_view_err = menu.addAction("🔍 Ver detalle del error...")
            action_view_err.triggered.connect(lambda: self._show_error_dialog(rel_path, db_item.error_message))

            menu.addSeparator()
            action_retry = menu.addAction("🔄 Reintentar este archivo")
            action_retry.triggered.connect(lambda: self._retry_single_item(rel_path))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _show_error_dialog(self, rel_path: str, err_msg: str):
        dlg = QDialog(self)
        dlg.setWindowTitle("Detalle del error de sincronización")
        dlg.resize(560, 320)
        l = QVBoxLayout(dlg)

        lbl = QLabel(f"<b>Archivo:</b> {rel_path}")
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        l.addWidget(lbl)

        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(err_msg)
        txt.setStyleSheet("color: #c0392b; font-family: monospace; font-size: 11px;")
        l.addWidget(txt)

        h = QHBoxLayout()
        btn_copy = QPushButton("📋 Copiar error al portapapeles")
        def do_copy():
            QApplication.clipboard().setText(err_msg)
            btn_copy.setText("✓ ¡Copiado!")
        btn_copy.clicked.connect(do_copy)
        h.addWidget(btn_copy)

        btn_retry_one = QPushButton("🔄 Reintentar archivo")
        def do_retry():
            dlg.accept()
            self._retry_single_item(rel_path)
        btn_retry_one.clicked.connect(do_retry)
        h.addWidget(btn_retry_one)

        h.addStretch()
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(dlg.accept)
        h.addWidget(btn_close)
        l.addLayout(h)

        dlg.exec()

    def _retry_single_item(self, rel_path: str):
        full_path = (self.sync_service.config.sync_dir / rel_path) if self.sync_service else None
        if full_path and full_path.exists():
            self.sync_service.queue.add_task(
                task_type="upload",
                rel_path=rel_path,
            )
            self.db.update_status(rel_path, SyncStatus.QUEUED_UPLOAD, error=None)
            self.refresh_history()

    def _on_refresh_clicked(self):
        if self.sync_service and hasattr(self.sync_service, "trigger_sync"):
            self.sync_service.trigger_sync()
        self.refresh_history()

    def _on_cell_double_clicked(self, row: int, col: int):
        path_item = self.table.item(row, 0)
        if not path_item:
            return
        rel_path = path_item.text()
        item = self.db.get_item_by_path(rel_path)
        if item and item.status == SyncStatus.ERROR and item.error_message:
            self._show_error_dialog(rel_path, item.error_message)

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
                status_item = QTableWidgetItem(f"❌ Error: {err_msg}")
                status_item.setForeground(QColor("#d32f2f"))
                status_item.setToolTip(f"Detalle del error:\n{err_msg}\n\n(Haz doble clic o clic derecho para ver/copiar el detalle)")
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
