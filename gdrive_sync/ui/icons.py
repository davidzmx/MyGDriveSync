"""
Dynamic high-DPI icon generator using QPainter for cross-platform tray states.
"""

from __future__ import annotations
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap


def create_tray_icon(state: str = "IDLE", size: int = 64) -> QIcon:
    """
    Renders clean, modern vector-style icons for system tray in KDE and Windows.
    States: 'IDLE', 'SYNCING', 'PAUSED', 'ERROR', 'NO_AUTH'
    """
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Outer circle background
    rect = QRectF(4, 4, size - 8, size - 8)

    if state == "IDLE":
        # Green / Google Drive teal-green
        painter.setBrush(QColor(15, 157, 88))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(rect)

        # White Checkmark
        pen = QPen(QColor(255, 255, 255), size * 0.1)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)

        p1 = QPointF(size * 0.28, size * 0.52)
        p2 = QPointF(size * 0.44, size * 0.68)
        p3 = QPointF(size * 0.72, size * 0.36)
        painter.drawPolyline([p1, p2, p3])

    elif state == "SYNCING":
        # Blue
        painter.setBrush(QColor(66, 133, 244))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(rect)

        # White rotating arrows/arc
        pen = QPen(QColor(255, 255, 255), size * 0.08)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        inner_rect = QRectF(size * 0.25, size * 0.25, size * 0.5, size * 0.5)
        painter.drawArc(inner_rect, 45 * 16, 230 * 16)
        painter.drawArc(inner_rect, 225 * 16, 230 * 16)

    elif state == "PAUSED":
        # Neutral Grey
        painter.setBrush(QColor(120, 144, 156))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(rect)

        # White Pause bars
        painter.setBrush(QColor(255, 255, 255))
        w = size * 0.1
        h = size * 0.4
        top = size * 0.3
        painter.drawRoundedRect(QRectF(size * 0.35, top, w, h), 2, 2)
        painter.drawRoundedRect(QRectF(size * 0.55, top, w, h), 2, 2)

    elif state == "ERROR":
        # Red
        painter.setBrush(QColor(219, 68, 55))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(rect)

        # Exclamation point
        painter.setBrush(QColor(255, 255, 255))
        painter.drawRoundedRect(QRectF(size * 0.45, size * 0.25, size * 0.1, size * 0.32), 2, 2)
        painter.drawEllipse(QRectF(size * 0.45, size * 0.65, size * 0.1, size * 0.1))

    else:  # NO_AUTH or WARNING
        # Amber / Orange
        painter.setBrush(QColor(244, 180, 0))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(rect)

        # Keyhole / lock icon
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(QRectF(size * 0.40, size * 0.30, size * 0.20, size * 0.20))
        painter.drawRoundedRect(QRectF(size * 0.32, size * 0.45, size * 0.36, size * 0.28), 3, 3)

    painter.end()
    return QIcon(pixmap)
