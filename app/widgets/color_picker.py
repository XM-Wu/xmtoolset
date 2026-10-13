"""Application adapter; shared implementation is synced from XMComicLibrary."""
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog
from app import config
from app.widgets.color_picker_core import ColorPickerDialog


def recent_colors():
    values=config.settings().value('colors/recent',[])
    if isinstance(values,str): values=[values]
    return [c for c in (values or []) if isinstance(c,str) and QColor(c).isValid()][:16]


def pick_color(initial, parent=None, title='选择颜色'):
    dialog=ColorPickerDialog(QColor(initial),parent,recent_loader=recent_colors,allow_alpha=True,allow_clear=False)
    dialog.setWindowTitle(title)
    if dialog.exec()!=QDialog.Accepted: return QColor()
    color=QColor(dialog.selected_hex())
    if color.isValid():
        value=color.name(QColor.HexArgb)
        config.settings().setValue('colors/recent',[value]+[c for c in recent_colors() if c!=value][:15])
    return color
