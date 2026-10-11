"""系统托盘图标与菜单。"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

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


class TrayController(QObject):
    """托盘：显示主窗口 / 退出。"""

    show_window_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._icon = make_app_icon()
        self._tray = QSystemTrayIcon(self._icon, parent)
        from app import product
        self._tray.setToolTip(product.NAME)

        menu = QMenu(parent)
        act_show = QAction("显示主窗口", menu)
        act_quit = QAction("退出", menu)
        act_show.triggered.connect(self.show_window_requested.emit)
        act_quit.triggered.connect(self.quit_requested.emit)
        menu.addAction(act_show)
        menu.addSeparator()
        menu.addAction(act_quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)

    @property
    def icon(self) -> QIcon:
        return self._icon

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def notify(self, title: str, message: str) -> None:
        if self._tray.supportsMessages():
            self._tray.showMessage(title, message, QSystemTrayIcon.Information, 2500)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.Trigger,
            QSystemTrayIcon.DoubleClick,
        ):
            self.show_window_requested.emit()
