"""应用设置页面。"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.tools.base_tool import BaseTool


class SettingsTool(BaseTool):
    tool_id = "settings"
    tool_name = "设置"
    tool_description = "开机启动、托盘与关闭行为"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("设置")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        hint = QLabel("选项会立即保存。托盘相关行为在下次关闭 / 最小化时生效。")
        hint.setObjectName("mutedLabel")
        hint.setWordWrap(True)
        root.addWidget(hint)

        boot_box = QGroupBox("启动")
        boot_form = QFormLayout(boot_box)
        self.autostart_check = QCheckBox("开机时自动启动")
        boot_form.addRow(self.autostart_check)
        boot_hint = QLabel(
            "写入当前用户开机启动项（静默启动主程序）。"
            "日常也可双击项目根目录的 start.bat 一键打开。"
        )
        boot_hint.setObjectName("mutedLabel")
        boot_hint.setWordWrap(True)
        boot_form.addRow(boot_hint)
        root.addWidget(boot_box)

        tray_box = QGroupBox("系统托盘")
        tray_form = QFormLayout(tray_box)

        self.minimize_to_tray_check = QCheckBox("最小化时隐藏到托盘")
        tray_form.addRow(self.minimize_to_tray_check)

        self.close_combo = QComboBox()
        self.close_combo.addItem("最小化到托盘", True)
        self.close_combo.addItem("直接退出程序", False)
        tray_form.addRow("点击关闭时", self.close_combo)

        tray_hint = QLabel("托盘图标可右键显示窗口或退出。")
        tray_hint.setObjectName("mutedLabel")
        tray_hint.setWordWrap(True)
        tray_form.addRow(tray_hint)
        root.addWidget(tray_box)

        root.addStretch()

        self.autostart_check.toggled.connect(self._on_autostart_toggled)
        self.minimize_to_tray_check.toggled.connect(self._on_minimize_toggled)
        self.close_combo.currentIndexChanged.connect(self._on_close_changed)

    def _load(self) -> None:
        self.autostart_check.blockSignals(True)
        self.minimize_to_tray_check.blockSignals(True)
        self.close_combo.blockSignals(True)

        self.autostart_check.setChecked(config.get_autostart())
        self.minimize_to_tray_check.setChecked(config.get_minimize_to_tray())
        idx = self.close_combo.findData(config.get_close_to_tray())
        if idx >= 0:
            self.close_combo.setCurrentIndex(idx)

        self.autostart_check.blockSignals(False)
        self.minimize_to_tray_check.blockSignals(False)
        self.close_combo.blockSignals(False)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # 进入页面时与系统开机启动状态同步
        self._load()

    def _on_autostart_toggled(self, checked: bool) -> None:
        try:
            config.set_autostart(checked)
        except OSError as exc:
            self.autostart_check.blockSignals(True)
            self.autostart_check.setChecked(False)
            self.autostart_check.blockSignals(False)
            QMessageBox.warning(self, "开机启动失败", str(exc))

    def _on_minimize_toggled(self, checked: bool) -> None:
        config.set_minimize_to_tray(checked)

    def _on_close_changed(self, _index: int) -> None:
        config.set_close_to_tray(bool(self.close_combo.currentData()))
