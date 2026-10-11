"""应用设置与旧版自启动项清理。"""
import sys
from PySide6.QtCore import QByteArray, QSettings
from app import product
_ORG = "py_tools"
_APP = product.TOOL_ID

def settings() -> QSettings:
    return QSettings(_ORG, _APP)

def get_window_geometry() -> QByteArray:
    """上次关闭时的窗口几何信息；无效时返回空。"""
    value = settings().value("ui/geometry")
    if isinstance(value, QByteArray) and not value.isEmpty():
        return value
    return QByteArray()


def set_window_geometry(geometry: QByteArray) -> None:
    settings().setValue("ui/geometry", geometry)
    settings().sync()


def retire_legacy_startup() -> None:
    """Remove only this product's old startup entry; never register new ones."""
    if sys.platform != "win32":
        return
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_SET_VALUE) as key:
            try:
                winreg.DeleteValue(key, product.TOOL_ID)
            except FileNotFoundError:
                pass
    except FileNotFoundError:
        pass
    s = settings()
    for name in ("system/autostart", "ui/minimize_to_tray", "ui/close_to_tray"):
        s.remove(name)
    s.sync()
