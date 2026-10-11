"""主窗口：左侧工具导航 + 右侧工具面板 + 系统托盘。"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QMoveEvent, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.tools import load_tools
from app import product
from app.tray import TrayController


class MainWindow(QMainWindow):
    def __init__(self, *, diagnostic: bool = False) -> None:
        super().__init__()
        self.setWindowTitle(f"{product.NAME} {product.VERSION}")
        self.setMinimumSize(720, 520)

        # restoreGeometry 可能同步触发 changeEvent / resizeEvent，须先初始化这些字段
        self._force_quit = False
        self._tray: TrayController | None = None
        self._geom_timer = QTimer(self)
        self._geom_timer.setSingleShot(True)
        self._geom_timer.setInterval(300)
        self._geom_timer.timeout.connect(self._save_geometry)

        if not self.restoreGeometry(config.get_window_geometry()):
            self.resize(960, 680)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)

        title = QLabel(product.NAME)
        title.setObjectName("appTitle")
        subtitle = QLabel("独立小应用" if product.TOOL_ID else "实用小工具集合")
        subtitle.setObjectName("appSubtitle")
        side_layout.addWidget(title)
        side_layout.addWidget(subtitle)

        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        self.nav.setFocusPolicy(Qt.NoFocus)
        side_layout.addWidget(self.nav, stretch=1)

        layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.stack.setObjectName("contentStack")
        layout.addWidget(self.stack, stretch=1)

        self._tools = []
        for tool_cls in load_tools():
            tool = tool_cls()
            self._tools.append(tool)
            item = QListWidgetItem(tool.tool_name)
            item.setToolTip(tool.tool_description)
            self.nav.addItem(item)
            self.stack.addWidget(tool)

        if self.nav.count() > 0:
            self.nav.setCurrentRow(0)

        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        if not diagnostic:
            self._setup_tray()

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._tray = TrayController(self)
        self.setWindowIcon(self._tray.icon)
        self._tray.show_window_requested.connect(self.show_from_tray)
        self._tray.quit_requested.connect(self.quit_app)
        self._tray.show()

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self) -> None:
        self._save_geometry()
        self._force_quit = True
        if self._tray is not None:
            self._tray.hide()
        QApplication.instance().quit()

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

    def _hide_to_tray(self, *, notify: bool = False) -> None:
        self._save_geometry()
        self.hide()
        if notify and self._tray is not None:
            self._tray.notify(product.NAME, "已最小化到系统托盘，双击图标可重新打开。")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._save_geometry()
        if not self._force_quit and self._tray is not None and config.get_close_to_tray():
            event.ignore()
            self._hide_to_tray(notify=True)
            return

        self._force_quit = True
        if self._tray is not None:
            self._tray.hide()
        event.accept()
        QApplication.instance().quit()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() != QEvent.Type.WindowStateChange:
            return
        if self._force_quit or self._tray is None:
            return
        if self.isMinimized() and config.get_minimize_to_tray():
            QTimer.singleShot(0, lambda: self._hide_to_tray(notify=False))
