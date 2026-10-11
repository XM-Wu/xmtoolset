"""应用窗口图标。"""

from __future__ import annotations

from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from app.theme import ACCENT, BG


def make_app_icon(size: int = 64) -> QIcon:
    """生成简单应用图标（无需外部资源文件）。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(BG))
    painter.setPen(QColor(ACCENT))
    margin = size // 10
    painter.drawRoundedRect(margin, margin, size - 2 * margin, size - 2 * margin, 12, 12)
    painter.setBrush(QColor(ACCENT))
    painter.setPen(QColor(ACCENT))
    bar_w = size // 5
    gap = size // 12
    x0 = size // 2 - (3 * bar_w + 2 * gap) // 2
    heights = (0.45, 0.7, 0.55)
    for i, h in enumerate(heights):
        bh = int(size * h * 0.5)
        x = x0 + i * (bar_w + gap)
        y = size // 2 + int(size * 0.22) - bh
        painter.drawRoundedRect(x, y, bar_w, bh, 3, 3)
    painter.end()
    return QIcon(pixmap)

