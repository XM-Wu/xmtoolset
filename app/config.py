"""应用设置持久化与 Windows 开机启动。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QSettings

# 与 main_app 中 Organization / Application 名称保持一致
_ORG = "py_tools"
from app import product
_APP = product.TOOL_ID
_AUTOSTART_NAME = product.TOOL_ID

PROJECT_ROOT = Path(__file__).resolve().parent.parent
START_BAT = PROJECT_ROOT / "start.bat"


def settings() -> QSettings:
    return QSettings(_ORG, _APP)


def get_close_to_tray() -> bool:
    """关闭窗口时是否最小化到托盘（默认 True）。"""
    return settings().value("ui/close_to_tray", True, type=bool)


def set_close_to_tray(enabled: bool) -> None:
    settings().setValue("ui/close_to_tray", enabled)


def get_minimize_to_tray() -> bool:
    """点击最小化时是否隐藏到托盘（默认 True）。"""
    return settings().value("ui/minimize_to_tray", True, type=bool)


def set_minimize_to_tray(enabled: bool) -> None:
    settings().setValue("ui/minimize_to_tray", enabled)


def get_window_geometry() -> QByteArray:
    """上次关闭时的窗口几何信息；无效时返回空。"""
    value = settings().value("ui/geometry")
    if isinstance(value, QByteArray) and not value.isEmpty():
        return value
    return QByteArray()


def set_window_geometry(geometry: QByteArray) -> None:
    settings().setValue("ui/geometry", geometry)
    settings().sync()


def get_autostart() -> bool:
    """开机启动是否开启（以系统注册表为准，并回写设置）。"""
    enabled = is_autostart_enabled()
    settings().setValue("system/autostart", enabled)
    return enabled


def set_autostart(enabled: bool) -> None:
    if enabled:
        enable_autostart()
    else:
        disable_autostart()
    settings().setValue("system/autostart", enabled)


def _resolve_pythonw() -> Path | None:
    """解析用于无控制台启动的解释器。"""
    candidates = [
        PROJECT_ROOT / ".venv" / "Scripts" / "pythonw.exe",
        PROJECT_ROOT / "venv" / "Scripts" / "pythonw.exe",
    ]
    for path in candidates:
        if path.is_file():
            return path

    exe = Path(sys.executable)
    # python.exe → 同目录 pythonw.exe
    if exe.name.lower() == "python.exe":
        pythonw = exe.with_name("pythonw.exe")
        if pythonw.is_file():
            return pythonw
    if exe.name.lower() == "pythonw.exe":
        return exe
    if exe.is_file():
        return exe
    return None


def autostart_command() -> str:
    """开机启动命令：优先 pythonw 静默启动；否则回退到 start.bat。"""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}"'
    script = PROJECT_ROOT / product.ENTRY
    pythonw = _resolve_pythonw()
    if pythonw is not None and script.is_file():
        return f'"{pythonw}" "{script}"'
    raise FileNotFoundError("未找到 Python 解释器或 start.bat，无法设置开机启动。")


def is_autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        ) as key:
            winreg.QueryValueEx(key, _AUTOSTART_NAME)
            return True
    except OSError:
        return False


def enable_autostart() -> None:
    if sys.platform != "win32":
        raise OSError("开机启动目前仅支持 Windows。")
    import winreg

    command = autostart_command()
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, _AUTOSTART_NAME, 0, winreg.REG_SZ, command)


def disable_autostart() -> None:
    if sys.platform != "win32":
        return
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, _AUTOSTART_NAME)
    except OSError:
        pass
