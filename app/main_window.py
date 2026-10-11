"""独立小应用窗口：功能面板直接占满窗口。"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent, QMoveEvent, QResizeEvent
from PySide6.QtWidgets import QApplication, QMainWindow

from app import config
from app.tools import load_tools
from app import product
from app.icon import make_app_icon


class MainWindow(QMainWindow):
    def __init__(self, *, diagnostic: bool = False) -> None:
        super().__init__()
        self.setWindowTitle(f"{product.NAME} {product.VERSION}")
        self.setMinimumSize(720, 520)

        # restoreGeometry 可能同步触发 changeEvent / resizeEvent，须先初始化这些字段
        self.setWindowIcon(make_app_icon())
        self._geom_timer = QTimer(self)
        self._geom_timer.setSingleShot(True)
        self._geom_timer.setInterval(300)
        self._geom_timer.timeout.connect(self._save_geometry)

        if not self.restoreGeometry(config.get_window_geometry()):
            self.resize(960, 680)

        tool_cls, = load_tools()
        self.tool = tool_cls()
        self.setCentralWidget(self.tool)

    def _save_geometry(self) -> None:
        if self.isMinimized():
            return
        config.set_window_geometry(self.saveGeometry())

    def _schedule_save_geometry(self) -> None:
        if self.isMinimized() or not self.isVisible():
            return
        self._geom_timer.start()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._schedule_save_geometry()

    def moveEvent(self, event: QMoveEvent) -> None:  # noqa: N802
        super().moveEvent(event)
        self._schedule_save_geometry()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._geom_timer.stop()
        self._save_geometry()
        event.accept()
        QApplication.instance().quit()
