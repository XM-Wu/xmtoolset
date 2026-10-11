"""主窗口：左侧工具导航 + 右侧工具面板。"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
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
    QVBoxLayout,
    QWidget,
)

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
