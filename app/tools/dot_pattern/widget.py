"""波点生成生成器界面。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.tools.dot_pattern.graphics.render import Document, rasterize
from app import config
from app.widgets.color_picker import pick_color
from app.tools.base_tool import BaseTool
from app.tools.dot_pattern import (
    ARRANGEMENTS,
    DEFAULT_ARRANGEMENT,
    DEFAULT_DIRECTION,
    DIRECTIONS,
    DotPatternParams,
    render_pattern_svg,
)

_DEFAULT_DOT = "#ff89b4fa"
_DEFAULT_BG = "#ffffffff"

_DIRECTION_LABELS = (
    ("从左到右", "left_right"),
    ("从右到左", "right_left"),
    ("从上到下", "top_bottom"),
    ("从下到上", "bottom_top"),
    ("从中心向外", "center_out"),
    ("从外向中心", "edge_in"),
)


class LegacyDotPatternTool(BaseTool):
    tool_id = "dot_pattern"
    tool_name = "波点生成"
    tool_description = "生成大小渐变的波点生成"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dot_color = QColor(_DEFAULT_DOT)
        self._bg_color = QColor(_DEFAULT_BG)
        self._last_export: Path | None = None
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(60)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self._build_ui()
        self._load_prefs()
        self._wire()
        self._refresh_preview()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("波点生成")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        hint = QLabel(
            "波点直径从初始大小起，沿渐变方向在渐变距离内过渡到最终大小；"
            "超过该距离后保持最终大小。渐变距离为 0 时全部使用初始大小。"
            "径向放射从画面中心向外按同心圆排布。"
            "图案锐度越高边缘越硬，越低越柔和。"
        )
        hint.setObjectName("mutedLabel")
        hint.setWordWrap(True)
        root.addWidget(hint)

        mid = QHBoxLayout()
        mid.setSpacing(12)

        opt_box = QGroupBox("图案参数")
        form = QFormLayout(opt_box)
        form.setSpacing(8)

        self.dot_swatch, self.dot_hex, dot_row = self._make_color_row()
        form.addRow("波点颜色", dot_row)

        self.bg_swatch, self.bg_hex, bg_row = self._make_color_row()
        form.addRow("背景颜色", bg_row)

        self.transparent_check = QCheckBox("透明背景")
        form.addRow(self.transparent_check)

        self.pattern_spin = QSpinBox()
        self.pattern_spin.setRange(8, 1024)
        self.pattern_spin.setValue(64)
        self.pattern_spin.setSuffix(" px")
        self.pattern_spin.setToolTip("相邻波点中心的间距；径向模式下同时作为环间距与环上弧长")
        form.addRow("图案大小", self.pattern_spin)

        self.start_spin = QSpinBox()
        self.start_spin.setRange(0, 1024)
        self.start_spin.setValue(24)
        self.start_spin.setSuffix(" px")
        self.start_spin.setToolTip("渐变起点处的波点直径")
        form.addRow("初始大小", self.start_spin)

        self.end_spin = QSpinBox()
        self.end_spin.setRange(0, 1024)
        self.end_spin.setValue(56)
        self.end_spin.setSuffix(" px")
        self.end_spin.setToolTip("渐变结束处的波点直径")
        form.addRow("最终大小", self.end_spin)

        self.gradient_spin = QSpinBox()
        self.gradient_spin.setRange(0, 16384)
        self.gradient_spin.setValue(512)
        self.gradient_spin.setSuffix(" px")
        self.gradient_spin.setToolTip("从初始大小过渡到最终大小所跨越的像素长度")
        form.addRow("渐变距离", self.gradient_spin)

        self.direction_combo = QComboBox()
        for label, value in _DIRECTION_LABELS:
            self.direction_combo.addItem(label, value)
        form.addRow("渐变方向", self.direction_combo)

        self.arrange_combo = QComboBox()
        self.arrange_combo.addItem("方形网格", "grid")
        self.arrange_combo.addItem("六边形密铺", "hex")
        self.arrange_combo.addItem("径向放射", "radial")
        form.addRow("排列方式", self.arrange_combo)

        sharp_row = QHBoxLayout()
        self.sharp_slider = QSlider(Qt.Horizontal)
        self.sharp_slider.setRange(0, 100)
        self.sharp_slider.setValue(90)
        self.sharp_slider.setToolTip("100 为硬边，0 为从中心柔化到边缘")
        self.sharp_label = QLabel("90")
        self.sharp_label.setMinimumWidth(28)
        sharp_row.addWidget(self.sharp_slider)
        sharp_row.addWidget(self.sharp_label)
        form.addRow("图案锐度", sharp_row)

        size_row = QHBoxLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(16, 8192)
        self.width_spin.setValue(512)
        self.width_spin.setSuffix(" px")
        self.height_spin = QSpinBox()
        self.height_spin.setRange(16, 8192)
        self.height_spin.setValue(512)
        self.height_spin.setSuffix(" px")
        size_x = QLabel("×")
        size_x.setObjectName("mutedLabel")
        size_row.addWidget(self.width_spin)
        size_row.addWidget(size_x)
        size_row.addWidget(self.height_spin)
        form.addRow("图片大小", size_row)

        self.square_check = QCheckBox("宽高相同")
        self.square_check.setChecked(True)
        form.addRow(self.square_check)

        preset_row = QHBoxLayout()
        for value in (256, 512, 1024, 2048):
            btn = QPushButton(str(value))
            btn.clicked.connect(lambda _=False, v=value: self._apply_size_preset(v))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        form.addRow("常用尺寸", preset_row)

        mid.addWidget(opt_box, stretch=0, alignment=Qt.AlignTop)

        preview_box = QGroupBox("预览")
        preview_layout = QVBoxLayout(preview_box)
        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("previewFrame")
        frame_layout = QVBoxLayout(self.preview_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        from app.tools.dot_pattern.graphics.widget import Preview
        self.preview_label = Preview()
        frame_layout.addWidget(self.preview_label)
        preview_layout.addWidget(self.preview_frame, stretch=1)

        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("mutedLabel")
        self.status_label.setWordWrap(True)
        preview_layout.addWidget(self.status_label)

        mid.addWidget(preview_box, stretch=1)
        root.addLayout(mid, stretch=1)

        action_row = QHBoxLayout()
        self.btn_open_folder = QPushButton("打开文件夹")
        self.btn_open_folder.setEnabled(False)
        self.btn_reset = QPushButton("恢复默认")
        self.btn_export = QPushButton("导出 PNG…")
        self.btn_export.setObjectName("primaryButton")
        self.btn_export.setMinimumHeight(36)
        action_row.addWidget(self.btn_open_folder)
        action_row.addStretch()
        action_row.addWidget(self.btn_reset)
        self.btn_export_svg = QPushButton("导出 SVG…")
        self.btn_export_svg.clicked.connect(lambda: self._export("svg"))
        action_row.addWidget(self.btn_export_svg)
        action_row.addWidget(self.btn_export)
        root.addLayout(action_row)

        self._paint_swatch(self.dot_swatch, self._dot_color)
        self._paint_swatch(self.bg_swatch, self._bg_color)
        self._update_hex_labels()

    def _make_color_row(self) -> tuple[QLabel, QLabel, QHBoxLayout]:
        row = QHBoxLayout()
        swatch = QLabel()
        swatch.setObjectName("colorSwatch")
        swatch.setFixedSize(28, 28)
        hex_label = QLabel()
        hex_label.setObjectName("mutedLabel")
        btn = QPushButton("选择…")
        btn.clicked.connect(lambda: self._pick_color(swatch))
        row.addWidget(swatch)
        row.addWidget(hex_label, stretch=1)
        row.addWidget(btn)
        return swatch, hex_label, row

    def _wire(self) -> None:
        self.pattern_spin.valueChanged.connect(self._on_params_changed)
        self.start_spin.valueChanged.connect(self._on_params_changed)
        self.end_spin.valueChanged.connect(self._on_params_changed)
        self.gradient_spin.valueChanged.connect(self._on_params_changed)
        self.sharp_slider.valueChanged.connect(self._on_sharpness_changed)
        self.direction_combo.currentIndexChanged.connect(self._on_params_changed)
        self.arrange_combo.currentIndexChanged.connect(self._on_arrange_changed)
        self.width_spin.valueChanged.connect(self._on_width_changed)
        self.height_spin.valueChanged.connect(self._on_height_changed)
        self.square_check.toggled.connect(self._on_square_toggled)
        self.transparent_check.toggled.connect(self._on_params_changed)
        self.btn_export.clicked.connect(lambda: self._export("png"))
        self.btn_reset.clicked.connect(self._reset_defaults)
        self.btn_open_folder.clicked.connect(self._open_export_folder)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.preview_label and event.type() == QEvent.Type.Resize:
            self._schedule_preview()
        return super().eventFilter(watched, event)

    def _pick_color(self, swatch: QLabel) -> None:
        current = self._dot_color if swatch is self.dot_swatch else self._bg_color
        color = pick_color(
            current,
            self,
            "选择颜色",
        )
        if not color.isValid():
            return
        if swatch is self.dot_swatch:
            self._dot_color = color
            self._paint_swatch(self.dot_swatch, color)
        else:
            self._bg_color = color
            self._paint_swatch(self.bg_swatch, color)
            if color.alpha() == 0:
                self.transparent_check.setChecked(True)
            elif self.transparent_check.isChecked() and color.alpha() > 0:
                self.transparent_check.setChecked(False)
        self._update_hex_labels()
        self._on_params_changed()

    def _on_sharpness_changed(self, value: int) -> None:
        self.sharp_label.setText(str(value))
        self._on_params_changed()

    def _on_arrange_changed(self) -> None:
        if self.arrange_combo.currentData() == "radial":
            idx = self.direction_combo.findData("center_out")
            if idx >= 0:
                self.direction_combo.blockSignals(True)
                self.direction_combo.setCurrentIndex(idx)
                self.direction_combo.blockSignals(False)
        self._on_params_changed()

    def _apply_size_preset(self, size: int) -> None:
        self.width_spin.blockSignals(True)
        self.height_spin.blockSignals(True)
        self.width_spin.setValue(size)
        self.height_spin.setValue(size)
        self.width_spin.blockSignals(False)
        self.height_spin.blockSignals(False)
        self.square_check.setChecked(True)
        self._on_params_changed()

    def _on_width_changed(self, value: int) -> None:
        if self.square_check.isChecked():
            self.height_spin.blockSignals(True)
            self.height_spin.setValue(value)
            self.height_spin.blockSignals(False)
        self._on_params_changed()

    def _on_height_changed(self, value: int) -> None:
        if self.square_check.isChecked():
            self.width_spin.blockSignals(True)
            self.width_spin.setValue(value)
            self.width_spin.blockSignals(False)
        self._on_params_changed()

    def _on_square_toggled(self, checked: bool) -> None:
        if checked:
            self.height_spin.setValue(self.width_spin.value())
        self._on_params_changed()

    def _on_params_changed(self, *_args) -> None:
        self._save_prefs()
        self._schedule_preview()

    def _schedule_preview(self) -> None:
        self._preview_timer.start()

    def _current_params(self) -> DotPatternParams:
        bg = QColor(self._bg_color)
        if self.transparent_check.isChecked():
            bg.setAlpha(0)
        arrangement = self.arrange_combo.currentData()
        if arrangement not in ARRANGEMENTS:
            arrangement = DEFAULT_ARRANGEMENT
        direction = self.direction_combo.currentData()
        if direction not in DIRECTIONS:
            direction = DEFAULT_DIRECTION
        return DotPatternParams(
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            pattern_size=float(self.pattern_spin.value()),
            start_size=float(self.start_spin.value()),
            end_size=float(self.end_spin.value()),
            gradient_distance=float(self.gradient_spin.value()),
            direction=direction,
            sharpness=float(self.sharp_slider.value()),
            dot_rgba=_qcolor_to_rgba(self._dot_color),
            bg_rgba=_qcolor_to_rgba(bg),
            arrangement=arrangement,
        )

    def _svg_document(self) -> Document:
        params = self._current_params()
        return Document(render_pattern_svg(params), params.width, params.height)

    def _refresh_preview(self) -> None:
        params = self._current_params()
        try:
            previous = self.preview_label.renderer
            self.preview_label.show_document(self._svg_document())
            if previous is not None:
                previous.deleteLater()
        except (ValueError, MemoryError) as exc:
            self.preview_label.scene().clear()
            self.status_label.setText("无法生成：" + str(exc))
            return

        direction_name = self.direction_combo.currentText()
        self.status_label.setText(
            f"导出 {params.width} × {params.height}  ·  "
            f"{int(params.start_size)} → {int(params.end_size)} px  ·  "
            f"{direction_name} {int(params.gradient_distance)} px  ·  "
            f"锐度 {int(params.sharpness)}"
        )

    def _export(self, extension="png") -> None:
        suggested = str(self._last_export.with_suffix("." + extension)) if self._last_export else "polka_dot." + extension
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 " + extension.upper(),
            suggested,
            extension.upper() + " 图片 (*." + extension + ")",
        )
        if not path:
            return
        dest = Path(path)
        if dest.suffix.lower() != "." + extension:
            dest = dest.with_suffix("." + extension)
        try:
            document = self._svg_document()
            dest.parent.mkdir(parents=True, exist_ok=True)
            if extension == "svg":
                dest.write_text(document.svg, encoding="utf-8")
            elif not rasterize(document).save(str(dest), "PNG"):
                raise OSError("无法写入 PNG 文件")
        except (OSError, ValueError, MemoryError) as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
            return

        self._last_export = dest
        self.btn_open_folder.setEnabled(True)
        s = config.settings()
        s.setValue("dot_pattern/last_export", str(dest))
        self.status_label.setText(f"已保存：{dest}")
        QMessageBox.information(self, "已导出", f"已保存到：\n{dest}")

    def _open_export_folder(self) -> None:
        if self._last_export is None:
            return
        folder = self._last_export.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _reset_defaults(self) -> None:
        self.pattern_spin.setValue(64)
        self.start_spin.setValue(24)
        self.end_spin.setValue(56)
        self.gradient_spin.setValue(512)
        self.sharp_slider.setValue(90)
        self.sharp_label.setText("90")
        self.width_spin.setValue(512)
        self.height_spin.setValue(512)
        self.square_check.setChecked(True)
        self.transparent_check.setChecked(True)
        idx = self.arrange_combo.findData("grid")
        if idx >= 0:
            self.arrange_combo.setCurrentIndex(idx)
        idx = self.direction_combo.findData(DEFAULT_DIRECTION)
        if idx >= 0:
            self.direction_combo.setCurrentIndex(idx)
        self._dot_color = QColor(_DEFAULT_DOT)
        self._bg_color = QColor(_DEFAULT_BG)
        self._paint_swatch(self.dot_swatch, self._dot_color)
        self._paint_swatch(self.bg_swatch, self._bg_color)
        self._update_hex_labels()
        self._on_params_changed()

    def _update_hex_labels(self) -> None:
        self.dot_hex.setText(_color_hex(self._dot_color))
        self.bg_hex.setText(_color_hex(self._bg_color))

    def _load_prefs(self) -> None:
        s = config.settings()
        self.pattern_spin.setValue(s.value("dot_pattern/pattern_size", 64, type=int))
        self.start_spin.setValue(s.value("dot_pattern/start_size", 24, type=int))
        self.end_spin.setValue(s.value("dot_pattern/end_size", 56, type=int))
        self.gradient_spin.setValue(s.value("dot_pattern/gradient_distance", 512, type=int))
        sharp = max(0, min(100, s.value("dot_pattern/sharpness", 90, type=int)))
        self.sharp_slider.setValue(sharp)
        self.sharp_label.setText(str(sharp))
        self.width_spin.setValue(s.value("dot_pattern/width", 512, type=int))
        self.height_spin.setValue(s.value("dot_pattern/height", 512, type=int))
        self.square_check.setChecked(s.value("dot_pattern/square", True, type=bool))
        self.transparent_check.setChecked(s.value("dot_pattern/transparent", True, type=bool))
        arrangement = s.value("dot_pattern/arrangement", DEFAULT_ARRANGEMENT, type=str)
        idx = self.arrange_combo.findData(arrangement)
        if idx >= 0:
            self.arrange_combo.setCurrentIndex(idx)
        direction = s.value("dot_pattern/direction", DEFAULT_DIRECTION, type=str)
        idx = self.direction_combo.findData(direction)
        if idx >= 0:
            self.direction_combo.setCurrentIndex(idx)
        self._dot_color = QColor(s.value("dot_pattern/dot_color", _DEFAULT_DOT))
        if not self._dot_color.isValid():
            self._dot_color = QColor(_DEFAULT_DOT)
        self._bg_color = QColor(s.value("dot_pattern/bg_color", _DEFAULT_BG))
        if not self._bg_color.isValid():
            self._bg_color = QColor(_DEFAULT_BG)
        last = s.value("dot_pattern/last_export", "", type=str)
        if last:
            self._last_export = Path(last)
            self.btn_open_folder.setEnabled(self._last_export.parent.is_dir())
        self._paint_swatch(self.dot_swatch, self._dot_color)
        self._paint_swatch(self.bg_swatch, self._bg_color)
        self._update_hex_labels()

    def _save_prefs(self) -> None:
        s = config.settings()
        s.setValue("dot_pattern/pattern_size", self.pattern_spin.value())
        s.setValue("dot_pattern/start_size", self.start_spin.value())
        s.setValue("dot_pattern/end_size", self.end_spin.value())
        s.setValue("dot_pattern/gradient_distance", self.gradient_spin.value())
        s.setValue("dot_pattern/sharpness", self.sharp_slider.value())
        s.setValue("dot_pattern/direction", self.direction_combo.currentData())
        s.setValue("dot_pattern/width", self.width_spin.value())
        s.setValue("dot_pattern/height", self.height_spin.value())
        s.setValue("dot_pattern/square", self.square_check.isChecked())
        s.setValue("dot_pattern/transparent", self.transparent_check.isChecked())
        s.setValue("dot_pattern/arrangement", self.arrange_combo.currentData())
        s.setValue("dot_pattern/dot_color", self._dot_color.name(QColor.HexArgb))
        s.setValue("dot_pattern/bg_color", self._bg_color.name(QColor.HexArgb))

    @staticmethod
    def _paint_swatch(label: QLabel, color: QColor) -> None:
        size = 28
        pm = _checkerboard_pixmap(size, size, cell=4)
        painter = QPainter(pm)
        painter.fillRect(0, 0, size, size, color)
        painter.end()
        label.setPixmap(pm)


def _qcolor_to_rgba(color: QColor) -> tuple[int, int, int, int]:
    return color.red(), color.green(), color.blue(), color.alpha()


def _color_hex(color: QColor) -> str:
    if color.alpha() >= 255:
        return color.name(QColor.HexRgb).upper()
    return color.name(QColor.HexArgb).upper()


def _checkerboard_pixmap(width: int, height: int, cell: int = 8) -> QPixmap:
    pm = QPixmap(width, height)
    painter = QPainter(pm)
    c1 = QColor("#313244")
    c2 = QColor("#45475a")
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            color = c1 if ((x // cell + y // cell) % 2 == 0) else c2
            painter.fillRect(x, y, cell, cell, color)
    painter.end()
    return pm


def _pil_to_pixmap(image) -> QPixmap:
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    data = image.tobytes("raw", "RGBA")
    qimg = QImage(
        data,
        image.width,
        image.height,
        4 * image.width,
        QImage.Format.Format_RGBA8888,
    )
    return QPixmap.fromImage(qimg.copy())


# Keep the registered entry point and settings identity for installed upgrades.
from app.tools.dot_pattern.graphics.widget import GraphicsTool as DotPatternTool
