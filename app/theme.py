"""全局深色主题：Fusion Palette + QSS。

样式表唯一入口：由 main_app 调用 apply_dark_theme()。
业务代码只通过 objectName / dynamic property 挂样式，禁止 setStyleSheet。

配色与控件样式对齐 XMComicLibrary 的 shared/theme.qss。
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# 中性深色 + 蓝色强调，与 XMComicLibrary 一致
BG = "#1a1a1a"
BG_ELEVATED = "#141414"
SURFACE = "#2a2a2a"
SURFACE_HOVER = "#353535"
BORDER = "#2c2c2c"
BORDER_STRONG = "#333333"
TEXT = "#e8e8e8"
TEXT_MUTED = "#8a8a8a"
ACCENT = "#2f6fed"
ACCENT_HOVER = "#3b7cff"
ACCENT_LINE = "#4d8dff"
DANGER = "#e06c75"
SUCCESS = "#6fbf8a"
WARN = "#e0b85a"
BASE = "#111111"
DISABLED = "#555555"

_CHECK_ICON = (Path(__file__).resolve().parent / "icons" / "check.svg").as_posix()


def apply_dark_theme(app: QApplication) -> None:
    """为整个应用应用深色主题（Palette + 全局 QSS）。"""
    app.setStyle("Fusion")
    app.setPalette(_build_palette())
    app.setStyleSheet(_build_stylesheet())


def _build_palette() -> QPalette:
    p = QPalette()
    chrome = QColor(BG_ELEVATED)
    surface = QColor(SURFACE)
    text = QColor(TEXT)
    muted = QColor(TEXT_MUTED)
    accent = QColor(ACCENT)
    base = QColor(BASE)

    p.setColor(QPalette.Window, chrome)
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, base)
    p.setColor(QPalette.AlternateBase, surface)
    p.setColor(QPalette.ToolTipBase, base)
    p.setColor(QPalette.ToolTipText, text)
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.Button, surface)
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.BrightText, QColor("#ffffff"))
    p.setColor(QPalette.Link, QColor(ACCENT_LINE))
    p.setColor(QPalette.Highlight, accent)
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.PlaceholderText, muted)

    disabled = QColor(DISABLED)
    p.setColor(QPalette.Disabled, QPalette.WindowText, disabled)
    p.setColor(QPalette.Disabled, QPalette.Text, disabled)
    p.setColor(QPalette.Disabled, QPalette.ButtonText, disabled)
    p.setColor(QPalette.Disabled, QPalette.Highlight, QColor("#3a3a3a"))
    p.setColor(QPalette.Disabled, QPalette.HighlightedText, disabled)
    return p


def _build_stylesheet() -> str:
    return f"""
    /* ---- 基础 ---- */
    QWidget {{
        background-color: {BG};
        color: {TEXT};
        font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
        font-size: 13px;
    }}
    QMainWindow, QDialog {{
        background-color: {BG_ELEVATED};
    }}
    QLabel {{
        background: transparent;
        color: {TEXT};
    }}
    QLabel#pageTitle {{
        font-size: 18px;
        font-weight: bold;
        color: #ffffff;
    }}
    QLabel#mutedLabel {{
        color: {TEXT_MUTED};
    }}
    QLabel#diffAdd {{
        color: {SUCCESS};
        font-weight: 600;
        background: transparent;
    }}
    QLabel#diffModify {{
        color: {WARN};
        font-weight: 600;
        background: transparent;
    }}
    QLabel#diffDelete {{
        color: {DANGER};
        font-weight: 600;
        background: transparent;
    }}
    QLabel#pathLink {{
        color: {ACCENT_LINE};
        background: transparent;
    }}

    /* ---- 主窗口布局 ---- */
    QFrame#sidebar {{
        background-color: {BG_ELEVATED};
        border-right: 1px solid {SURFACE};
    }}
    QLabel#appTitle {{
        color: #ffffff;
        font-size: 16px;
        font-weight: bold;
        padding: 16px 16px 8px 16px;
        background: transparent;
    }}
    QLabel#appSubtitle {{
        color: {TEXT_MUTED};
        font-size: 12px;
        padding: 0 16px 12px 16px;
        background: transparent;
    }}
    QListWidget#navList {{
        background: transparent;
        border: none;
        outline: none;
        padding: 4px 8px;
        color: {TEXT};
        alternate-background-color: transparent;
    }}
    QListWidget#navList::item {{
        padding: 8px 12px;
        border-radius: 6px;
        margin: 2px 0;
        color: #d0d0d0;
        background: transparent;
    }}
    QListWidget#navList::item:selected {{
        background: {ACCENT};
        color: #ffffff;
    }}
    QListWidget#navList::item:hover:!selected {{
        background: #252525;
        color: #ffffff;
    }}
    QStackedWidget#contentStack {{
        background-color: {BG};
    }}

    /* ---- GroupBox ---- */
    QGroupBox {{
        background-color: #212121;
        border: 1px solid {BORDER};
        border-radius: 8px;
        margin-top: 12px;
        padding: 12px 10px 10px 10px;
        font-weight: 600;
        color: {TEXT};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: #d0d0d0;
        background: transparent;
    }}

    /* ---- List ---- */
    QListWidget {{
        background-color: {BG_ELEVATED};
        border: 1px solid {BORDER};
        border-radius: 8px;
        outline: none;
        padding: 4px 2px;
        color: #d0d0d0;
        alternate-background-color: #191919;
    }}
    QListWidget::item {{
        padding: 6px 8px;
        border-radius: 4px;
        color: #d0d0d0;
    }}
    QListWidget::item:selected {{
        background-color: {ACCENT};
        color: #ffffff;
    }}
    QListWidget::item:hover:!selected {{
        background-color: {SURFACE};
    }}

    /* ---- Button ---- */
    QPushButton {{
        background-color: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER_STRONG};
        border-radius: 6px;
        padding: 6px 12px;
    }}
    QPushButton:hover {{
        background-color: {SURFACE_HOVER};
    }}
    QPushButton:pressed {{
        background-color: #222222;
    }}
    QPushButton:disabled {{
        color: {DISABLED};
        background-color: #222222;
        border-color: {SURFACE};
    }}
    QPushButton:checked {{
        background-color: {ACCENT};
        color: #ffffff;
        border-color: {ACCENT};
    }}
    QPushButton:checked:hover {{
        background-color: {ACCENT_HOVER};
        color: #ffffff;
    }}
    QPushButton#primaryButton {{
        background-color: {ACCENT};
        color: #ffffff;
        border: none;
        font-weight: 600;
    }}
    QPushButton#primaryButton:hover {{
        background-color: {ACCENT_HOVER};
    }}
    QPushButton#primaryButton:pressed {{
        background-color: #275fce;
    }}
    QPushButton#primaryButton:disabled {{
        background-color: #3a4a6a;
        color: #9aa3b2;
    }}

    /* ---- CheckBox ---- */
    QCheckBox {{
        background: transparent;
        color: {TEXT};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 17px;
        height: 17px;
        border: 1px solid #8a8a8a;
        border-radius: 5px;
        background: transparent;
    }}
    QCheckBox::indicator:checked {{
        background: {ACCENT};
        border-color: {ACCENT};
        image: url("{_CHECK_ICON}");
    }}
    QCheckBox::indicator:disabled {{
        border-color: {DISABLED};
    }}
    QCheckBox::indicator:checked:disabled {{
        background: #3a4a6a;
        border-color: #3a4a6a;
    }}

    /* ---- 输入 ---- */
    QLineEdit, QPlainTextEdit, QTextEdit {{
        background: {BASE};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 6px 8px;
        color: #eeeeee;
        selection-background-color: #2a5a9a;
        selection-color: #ffffff;
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
        border: 1px solid {ACCENT_LINE};
    }}
    QPlainTextEdit:read-only {{
        background: {BASE};
    }}

    /* ---- ComboBox ---- */
    QComboBox {{
        background-color: {BASE};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 4px 8px;
        min-height: 22px;
    }}
    QComboBox:hover, QComboBox:focus {{
        border-color: {ACCENT_LINE};
    }}
    QComboBox:disabled {{
        color: {DISABLED};
        background-color: #1c1c1c;
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background-color: #1f1f1f;
        color: {TEXT};
        border: 1px solid {BORDER_STRONG};
        selection-background-color: {ACCENT};
        selection-color: #ffffff;
        outline: none;
    }}

    /* ---- Slider（禁用态用颜色，禁止 opacity，否则重启用后无法拖动） ---- */
    QSlider {{
        min-height: 22px;
        background: transparent;
    }}
    QSlider::groove:horizontal {{
        height: 4px;
        background: {BORDER_STRONG};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        width: 14px;
        height: 14px;
        margin: -5px 0;
        background: #d0d0d0;
        border-radius: 7px;
    }}
    QSlider::sub-page:horizontal {{
        background: {ACCENT_LINE};
        border-radius: 2px;
    }}
    QSlider::add-page:horizontal {{
        background: {BORDER_STRONG};
        border-radius: 2px;
    }}
    QSlider::groove:horizontal:disabled {{
        background: #222222;
    }}
    QSlider::add-page:horizontal:disabled {{
        background: #222222;
    }}
    QSlider::sub-page:horizontal:disabled {{
        background: #3a4a6a;
    }}
    QSlider::handle:horizontal:disabled {{
        background: {DISABLED};
    }}
    QSlider[inactive="true"]::groove:horizontal {{
        background: #222222;
    }}
    QSlider[inactive="true"]::add-page:horizontal {{
        background: #222222;
    }}
    QSlider[inactive="true"]::sub-page:horizontal {{
        background: #3a4a6a;
    }}
    QSlider[inactive="true"]::handle:horizontal {{
        background: {DISABLED};
    }}
    QLabel[inactive="true"] {{
        color: {DISABLED};
    }}

    /* ---- SpinBox ---- */
    QSpinBox, QDoubleSpinBox {{
        background-color: {BASE};
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 4px 8px;
        min-height: 22px;
    }}
    QSpinBox:hover, QSpinBox:focus,
    QDoubleSpinBox:hover, QDoubleSpinBox:focus {{
        border-color: {ACCENT_LINE};
    }}
    QSpinBox:disabled, QDoubleSpinBox:disabled {{
        color: {DISABLED};
        background-color: #1c1c1c;
    }}

    /* ---- 颜色色板 / 预览框 ---- */
    QLabel#colorSwatch {{
        border: 1px solid {BORDER_STRONG};
        border-radius: 4px;
        background-color: {BASE};
        padding: 0px;
    }}
    QFrame#previewFrame {{
        background-color: {BASE};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}
    QLabel#previewImage {{
        background: transparent;
        border: none;
    }}

    /* ---- Color dialog ---- */
    QColorDialog {{
        background-color: {BG};
    }}
    QColorDialog QLabel {{
        color: {TEXT};
    }}

    /* ---- Table ---- */
    QTableWidget {{
        background-color: {BG_ELEVATED};
        color: #d0d0d0;
        border: 1px solid {BORDER};
        border-radius: 8px;
        gridline-color: {SURFACE};
        outline: none;
    }}
    QTableWidget::item {{
        padding: 6px 8px;
    }}
    QTableWidget::item:selected {{
        background-color: {ACCENT};
        color: #ffffff;
    }}
    QHeaderView::section {{
        background-color: #1f1f1f;
        color: #d0d0d0;
        border: none;
        border-bottom: 1px solid {BORDER};
        border-right: 1px solid {BORDER};
        padding: 6px 8px;
        font-weight: 600;
    }}
    QTableCornerButton::section {{
        background-color: #1f1f1f;
        border: none;
    }}
    QWidget#backupEnableCell {{
        background: transparent;
    }}
    QPushButton#enableChip {{
        min-width: 52px;
        min-height: 28px;
        padding: 0px;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 600;
    }}
    QPushButton#enableChip[on="true"] {{
        background-color: {ACCENT};
        color: #ffffff;
        border: none;
    }}
    QPushButton#enableChip[on="true"]:hover {{
        background-color: {ACCENT_HOVER};
        color: #ffffff;
    }}
    QPushButton#enableChip[on="false"] {{
        background-color: {SURFACE};
        color: {TEXT_MUTED};
        border: 1px solid {BORDER_STRONG};
    }}
    QPushButton#enableChip[on="false"]:hover {{
        background-color: {SURFACE_HOVER};
        color: #ffffff;
    }}

    QSplitter::handle {{
        background-color: {SURFACE};
    }}
    QSplitter::handle:horizontal {{
        width: 4px;
    }}
    QSplitter::handle:vertical {{
        height: 4px;
    }}

    /* ---- Tree（对比差异） ---- */
    QTreeWidget {{
        background-color: {BG_ELEVATED};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 4px 2px;
        color: #d0d0d0;
        outline: none;
        alternate-background-color: #191919;
    }}
    QTreeWidget::item {{
        padding: 3px 6px;
        border-radius: 4px;
        min-height: 22px;
    }}
    QTreeWidget::item:selected {{
        background-color: {ACCENT};
        color: #ffffff;
    }}
    QTreeWidget::item:hover:!selected {{
        background-color: {SURFACE};
    }}
    QTreeWidget::branch {{
        background: transparent;
    }}

    /* ---- Progress ---- */
    QProgressBar {{
        background-color: #222222;
        border: 1px solid {BORDER_STRONG};
        border-radius: 4px;
        text-align: center;
        color: {TEXT};
        min-height: 16px;
        max-height: 16px;
    }}
    QProgressBar::chunk {{
        background-color: {ACCENT};
        border-radius: 3px;
    }}

    /* ---- Scroll / Tip / Menu / Message ---- */
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: #3a3a3a;
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: #505050;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        height: 0;
        background: none;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
    }}
    QScrollBar::handle:horizontal {{
        background: #3a3a3a;
        border-radius: 5px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: #505050;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
        width: 0;
        background: none;
    }}
    QMenu {{
        background: #1f1f1f;
        border: 1px solid {BORDER_STRONG};
        padding: 4px;
        color: {TEXT};
    }}
    QMenu::item {{
        padding: 6px 20px;
        border-radius: 4px;
        background: transparent;
    }}
    QMenu::item:selected {{
        background: {ACCENT};
        color: #ffffff;
    }}
    QToolTip {{
        background-color: {BASE};
        color: #eeeeee;
        border: 1px solid {BORDER_STRONG};
        padding: 4px 8px;
    }}
    QMessageBox {{
        background-color: {BG};
    }}
    QMessageBox QLabel {{
        color: {TEXT};
    }}
    """
