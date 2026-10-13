"""Reusable Qt color picker. Storage is injected by each host application."""
from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QConicalGradient, QImage, QLinearGradient, QMouseEvent, QPainter, QPen, QPolygon
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from collections.abc import Callable


def _hue(color: QColor) -> int:
    hue = color.hue()
    return 0 if hue < 0 else hue


def color_to_hex(color: QColor) -> str:
    return color.name(QColor.HexArgb if color.alpha() < 255 else QColor.HexRgb).upper()


class ColorWheel(QWidget):
    colorChanged = Signal()

    def __init__(self, color: QColor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self._wheel = QImage()
        self._radius = 0
        self._center = QPoint()
        self._dragging = False
        self.setFixedSize(250, 250)

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rebuild()

    def _rebuild(self) -> None:
        side = min(self.width(), self.height())
        self._radius = max(1, side // 2 - 12)
        self._center = QPoint(self.width() // 2, self.height() // 2)
        image = QImage(self.size(), QImage.Format_ARGB32)
        image.fill(Qt.transparent)
        cx, cy, radius = self._center.x(), self._center.y(), self._radius
        radius_sq = radius * radius
        for y in range(self.height()):
            dy = cy - y
            for x in range(self.width()):
                dx = x - cx
                dist_sq = dx * dx + dy * dy
                if dist_sq > radius_sq:
                    continue
                dist = math.sqrt(dist_sq)
                hue = int((math.atan2(dy, dx) * 180 / math.pi) % 360)
                sat = int(dist / radius * 255)
                image.setPixelColor(x, y, QColor.fromHsv(hue, sat, 255))
        self._wheel = image

    def _pos_to_hs(self, pos: QPoint) -> tuple[int, int] | None:
        dx = pos.x() - self._center.x()
        dy = self._center.y() - pos.y()
        dist = math.hypot(dx, dy)
        if dist > self._radius:
            return None
        hue = int((math.atan2(dy, dx) * 180 / math.pi) % 360)
        sat = int(min(1.0, dist / max(1, self._radius)) * 255)
        return hue, sat

    def _apply_pos(self, pos: QPoint) -> None:
        hs = self._pos_to_hs(pos)
        if hs is None:
            return
        hue, sat = hs
        self._color.setHsv(hue, sat, max(1, self._color.value()), self._color.alpha())
        self.colorChanged.emit()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._apply_pos(event.position().toPoint())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._apply_pos(event.position().toPoint())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self._wheel.isNull():
            painter.drawImage(0, 0, self._wheel)
        gradient = QConicalGradient(self._center, 0)
        for stop, hue in ((0.0, 0), (1 / 6, 60), (1 / 3, 120), (0.5, 180), (2 / 3, 240), (5 / 6, 300), (1.0, 0)):
            gradient.setColorAt(stop, QColor.fromHsv(hue, 255, 255))
        painter.setPen(QPen(gradient, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(self._center, self._radius, self._radius)
        dist = self._color.saturation() * self._radius / 255
        angle = math.radians(_hue(self._color))
        indicator = QPoint(
            self._center.x() + int(dist * math.cos(angle)),
            self._center.y() - int(dist * math.sin(angle)),
        )
        painter.setBrush(QColor.fromHsv(_hue(self._color), self._color.saturation(), 255))
        painter.setPen(QPen(Qt.black, 2))
        painter.drawEllipse(indicator, 6, 6)


class ColorBar(QWidget):
    colorChanged = Signal()

    def __init__(self, color: QColor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self._dragging = False
        self.setFixedSize(28, 250)

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def _value(self) -> float:
        return 0.0

    def _edit(self, pos: float) -> None:
        return

    def _stops(self) -> list[tuple[float, QColor]]:
        return []

    def _apply(self, y: int) -> None:
        top = 6
        height = max(1, self.height() - 12)
        pos = 1.0 - max(0.0, min(1.0, (y - top) / height))
        self._edit(pos)
        self.colorChanged.emit()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._apply(event.position().toPoint().y())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._apply(event.position().toPoint().y())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRect(6, 6, self.width() - 12, self.height() - 12)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        for stop, color in self._stops():
            gradient.setColorAt(stop, color)
        painter.fillRect(rect, gradient)
        y = int((1.0 - self._value()) * rect.height()) + rect.top()
        painter.setBrush(Qt.white)
        painter.setPen(Qt.gray)
        left = QPolygon([QPoint(0, y - 5), QPoint(6, y), QPoint(0, y + 5)])
        right = QPolygon([QPoint(self.width() - 1, y - 5), QPoint(self.width() - 7, y), QPoint(self.width() - 1, y + 5)])
        painter.drawPolygon(left)
        painter.drawPolygon(right)


class SaturationBar(ColorBar):
    def _value(self) -> float:
        return self._color.saturation() / 255

    def _edit(self, pos: float) -> None:
        self._color.setHsv(_hue(self._color), int(pos * 255), max(1, self._color.value()), self._color.alpha())

    def _stops(self) -> list[tuple[float, QColor]]:
        return [(0.0, QColor.fromHsv(_hue(self._color), 255, 255)), (1.0, Qt.white)]


class ValueBar(ColorBar):
    def _value(self) -> float:
        return self._color.value() / 255

    def _edit(self, pos: float) -> None:
        self._color.setHsv(_hue(self._color), self._color.saturation(), int(pos * 255), self._color.alpha())

    def _stops(self) -> list[tuple[float, QColor]]:
        return [(0.0, QColor.fromHsv(_hue(self._color), self._color.saturation(), 255)), (1.0, Qt.black)]


class ColorPreview(QWidget):
    def __init__(self, color: QColor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setFixedSize(88, 88)

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#444444"), 1))
        painter.setBrush(self._color)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)


class ChannelRow(QWidget):
    changed = Signal()

    def __init__(self, name: str, maximum: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        label = QLabel(name)
        label.setFixedWidth(16)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, maximum)
        self.box = QSpinBox()
        self.box.setRange(0, maximum)
        self.box.setFixedWidth(64)
        layout.addWidget(label)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.box)
        self.slider.valueChanged.connect(self.box.setValue)
        self.box.valueChanged.connect(self.slider.setValue)
        self.slider.valueChanged.connect(self.changed)

    def set_value(self, value: int) -> None:
        self.slider.blockSignals(True)
        self.box.blockSignals(True)
        self.slider.setValue(value)
        self.box.setValue(value)
        self.slider.blockSignals(False)
        self.box.blockSignals(False)

    def value(self) -> int:
        return self.slider.value()


class RecentColorButton(QPushButton):
    picked = Signal(QColor)

    def __init__(self, color: QColor, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setFixedSize(22, 22)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"QPushButton {{ background: {color_to_hex(color)}; border: 1px solid #555; border-radius: 4px; }}"
            "QPushButton:hover { border: 1px solid #4d8dff; }"
        )
        self.clicked.connect(lambda: self.picked.emit(self._color))


class ColorPickerDialog(QDialog):
    def __init__(self, color: QColor | None = None, parent: QWidget | None = None, *,
                 recent_loader: Callable[[], list[str]] | None = None,
                 allow_alpha: bool = False, allow_clear: bool = True) -> None:
        super().__init__(parent)
        self.setWindowTitle("选择颜色")
        self._recent_loader = recent_loader or (lambda: [])
        self._allow_alpha = allow_alpha
        self.setModal(True)
        self._color = QColor(color if color and color.isValid() else "#4d8dff")
        if not self._color.isValid():
            self._color = QColor("#4d8dff")
        self._updating = False

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        hsv_row = QHBoxLayout()
        hsv_row.setSpacing(10)
        self.wheel = ColorWheel(self._color)
        self.sat_bar = SaturationBar(self._color)
        self.val_bar = ValueBar(self._color)
        self.preview = ColorPreview(self._color)
        hsv_row.addWidget(self.wheel)
        hsv_row.addWidget(self.sat_bar)
        hsv_row.addWidget(self.val_bar)
        preview_col = QVBoxLayout()
        preview_label = QLabel("预览")
        preview_label.setObjectName("muted")
        preview_col.addWidget(preview_label)
        preview_col.addWidget(self.preview)
        preview_col.addStretch(1)
        hsv_row.addLayout(preview_col)
        root.addLayout(hsv_row)

        self.red = ChannelRow("R", 255)
        self.green = ChannelRow("G", 255)
        self.blue = ChannelRow("B", 255)
        self.hue = ChannelRow("H", 359)
        self.sat = ChannelRow("S", 255)
        self.val = ChannelRow("V", 255)
        channels = QGridLayout()
        channels.addWidget(self.red, 0, 0)
        channels.addWidget(self.green, 1, 0)
        channels.addWidget(self.blue, 2, 0)
        channels.addWidget(self.hue, 0, 1)
        channels.addWidget(self.sat, 1, 1)
        channels.addWidget(self.val, 2, 1)
        root.addLayout(channels)
        self.alpha = ChannelRow("A", 255)
        self.alpha.setVisible(allow_alpha)
        root.addWidget(self.alpha)
        self.alpha.changed.connect(self._from_alpha)

        hex_row = QHBoxLayout()
        hex_row.addWidget(QLabel("Hex"))
        self.hex_edit = QLineEdit(color_to_hex(self._color))
        self.hex_edit.setFixedWidth(120)
        self.hex_edit.setToolTip("#RRGGBB 或 #AARRGGBB（透明度在前）")
        hex_row.addWidget(self.hex_edit)
        hex_row.addStretch(1)
        root.addLayout(hex_row)

        recent_label = QLabel("最近使用")
        recent_label.setObjectName("muted")
        root.addWidget(recent_label)
        self.recent_host = QWidget()
        self.recent_layout = QHBoxLayout(self.recent_host)
        self.recent_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_layout.setSpacing(6)
        root.addWidget(self.recent_host)
        self._reload_recent()

        buttons = QHBoxLayout()
        self.clear_btn = QPushButton("清除颜色")
        self.clear_btn.setObjectName("ghostButton")
        self.clear_btn.setVisible(allow_clear)
        ok = QPushButton("确定")
        cancel = QPushButton("取消")
        buttons.addWidget(self.clear_btn)
        buttons.addStretch(1)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        root.addLayout(buttons)

        self.wheel.colorChanged.connect(self._from_wheel)
        self.sat_bar.colorChanged.connect(self._from_wheel)
        self.val_bar.colorChanged.connect(self._from_wheel)
        self.red.changed.connect(self._from_rgb)
        self.green.changed.connect(self._from_rgb)
        self.blue.changed.connect(self._from_rgb)
        self.hue.changed.connect(self._from_hsv)
        self.sat.changed.connect(self._from_hsv)
        self.val.changed.connect(self._from_hsv)
        self.hex_edit.editingFinished.connect(self._from_hex)
        self.clear_btn.clicked.connect(self._clear)
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        self._cleared = False
        self._refresh()

    def _reload_recent(self) -> None:
        while self.recent_layout.count():
            item = self.recent_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        colors = self._recent_loader()
        if not colors:
            empty = QLabel("还没有最近使用的颜色")
            empty.setObjectName("muted")
            self.recent_layout.addWidget(empty)
        else:
            for item in colors:
                color = QColor(item)
                if not color.isValid():
                    continue
                button = RecentColorButton(color)
                button.picked.connect(self._apply_color)
                self.recent_layout.addWidget(button)
        self.recent_layout.addStretch(1)

    def _apply_color(self, color: QColor) -> None:
        self._cleared = False
        self._color = QColor(color)
        self._refresh()

    def _from_wheel(self) -> None:
        self._cleared = False
        self._refresh()

    def _from_rgb(self) -> None:
        if self._updating:
            return
        self._cleared = False
        self._color.setRgb(self.red.value(), self.green.value(), self.blue.value(), self._color.alpha())
        self._refresh()

    def _from_hsv(self) -> None:
        if self._updating:
            return
        self._cleared = False
        self._color.setHsv(self.hue.value(), self.sat.value(), self.val.value(), self._color.alpha())
        self._refresh()

    def _from_alpha(self) -> None:
        if not self._updating:
            self._color.setAlpha(self.alpha.value())
            self._refresh()

    def _from_hex(self) -> None:
        color = QColor(self.hex_edit.text().strip())
        if color.isValid():
            self._apply_color(color)
        else:
            self.hex_edit.setText(color_to_hex(self._color))

    def _clear(self) -> None:
        self._cleared = True
        self.accept()

    def _refresh(self) -> None:
        self._updating = True
        self.wheel.set_color(self._color)
        self.sat_bar.set_color(self._color)
        self.val_bar.set_color(self._color)
        self.preview.set_color(self._color)
        self.red.set_value(self._color.red())
        self.green.set_value(self._color.green())
        self.blue.set_value(self._color.blue())
        self.hue.set_value(_hue(self._color))
        self.sat.set_value(self._color.saturation())
        self.val.set_value(self._color.value())
        self.alpha.set_value(self._color.alpha())
        if not self.hex_edit.hasFocus():
            self.hex_edit.setText(color_to_hex(self._color))
        self._updating = False

    def selected_hex(self) -> str:
        if self._cleared:
            return ""
        return color_to_hex(self._color)

