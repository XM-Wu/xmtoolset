"""图片格式转换工具界面。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.tools.base_tool import BaseTool
from app.tools.image_converter import (
    DEFAULT_FORMAT,
    SUPPORTED_FORMATS,
    collect_image_files,
)
from app.tools.image_converter.worker import ConvertWorker
from app.widgets.drop_list import DropListWidget


class ImageConverterTool(BaseTool):
    tool_id = "image_converter"
    tool_name = "图片格式转换"
    tool_description = "在 AVIF / WebP / JPEG / PNG 之间互转"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._files: list[Path] = []
        self._output_dir: Path | None = None
        self._worker: ConvertWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("图片格式转换")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        hint = QLabel("支持将图片在 AVIF、WebP、JPEG、PNG 之间互转。可拖放文件或文件夹到列表。")
        hint.setObjectName("mutedLabel")
        hint.setWordWrap(True)
        root.addWidget(hint)

        # 文件列表
        file_box = QGroupBox("待转换文件")
        file_layout = QVBoxLayout(file_box)

        self.file_list = DropListWidget(self._add_paths)
        self.file_list.setMinimumHeight(220)
        file_layout.addWidget(self.file_list)

        btn_row = QHBoxLayout()
        self.btn_add_files = QPushButton("添加文件…")
        self.btn_add_folder = QPushButton("添加文件夹…")
        self.btn_remove = QPushButton("移除选中")
        self.btn_clear = QPushButton("清空列表")
        btn_row.addWidget(self.btn_add_files)
        btn_row.addWidget(self.btn_add_folder)
        btn_row.addWidget(self.btn_remove)
        btn_row.addWidget(self.btn_clear)
        btn_row.addStretch()
        file_layout.addLayout(btn_row)
        root.addWidget(file_box)

        # 转换选项
        opt_box = QGroupBox("转换选项")
        form = QFormLayout(opt_box)

        self.format_combo = QComboBox()
        for fmt in SUPPORTED_FORMATS:
            self.format_combo.addItem(fmt, fmt)
        idx = self.format_combo.findData(DEFAULT_FORMAT)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)
        form.addRow("目标格式", self.format_combo)

        quality_row = QHBoxLayout()
        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setObjectName("qualitySlider")
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(100)
        self.quality_label = QLabel("100")
        self.quality_label.setMinimumWidth(28)
        quality_row.addWidget(self.quality_slider)
        quality_row.addWidget(self.quality_label)
        form.addRow("质量 (JPEG/WebP/AVIF)", quality_row)

        out_row = QHBoxLayout()
        self.output_label = QLabel("与源文件同目录")
        self.output_label.setObjectName("mutedLabel")
        self.btn_choose_output = QPushButton("选择…")
        self.btn_reset_output = QPushButton("重置")
        out_row.addWidget(self.output_label, stretch=1)
        out_row.addWidget(self.btn_choose_output)
        out_row.addWidget(self.btn_reset_output)
        form.addRow("输出目录", out_row)

        root.addWidget(opt_box)

        # 进度与操作
        self.progress = QProgressBar()
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("mutedLabel")
        root.addWidget(self.status_label)

        action_row = QHBoxLayout()
        self.btn_convert = QPushButton("开始转换")
        self.btn_convert.setObjectName("primaryButton")
        self.btn_convert.setMinimumHeight(36)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setEnabled(False)
        action_row.addStretch()
        action_row.addWidget(self.btn_cancel)
        action_row.addWidget(self.btn_convert)
        root.addLayout(action_row)
        root.addStretch()

        # 信号
        self.btn_add_files.clicked.connect(self._pick_files)
        self.btn_add_folder.clicked.connect(self._pick_folder)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear.clicked.connect(self._clear_files)
        self.btn_choose_output.clicked.connect(self._pick_output_dir)
        self.btn_reset_output.clicked.connect(self._reset_output_dir)
        self.quality_slider.valueChanged.connect(self._on_quality_changed)
        self.btn_convert.clicked.connect(self._start_convert)
        self.btn_cancel.clicked.connect(self._cancel_convert)
        self.format_combo.currentIndexChanged.connect(self._update_quality_enabled)
        self._update_quality_enabled()

    def _on_quality_changed(self, value: int) -> None:
        self.quality_label.setText(str(value))

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

    def _update_quality_enabled(self) -> None:
        """PNG 不使用质量；用 inactive 属性灰显，勿反复 setEnabled（配合 QSS 易导致无法拖动）。"""
        fmt = self.format_combo.currentData()
        inactive = fmt == "PNG"
        self.quality_slider.setProperty("inactive", inactive)
        self.quality_label.setProperty("inactive", inactive)
        # 始终保持可拖动；PNG 时数值仅被忽略
        if self.btn_convert.isEnabled():
            self.quality_slider.setEnabled(True)
        self._repolish(self.quality_slider)
        self._repolish(self.quality_label)

    def _refresh_list(self) -> None:
        self.file_list.clear()
        for path in self._files:
            item = QListWidgetItem(str(path))
            item.setData(Qt.UserRole, str(path))
            self.file_list.addItem(item)
        self.status_label.setText(f"已添加 {len(self._files)} 个文件")

    def _add_paths(self, paths: list[Path]) -> None:
        new_files = collect_image_files(paths, recursive=True)
        existing = {p.resolve() for p in self._files}
        added = 0
        for f in new_files:
            if f.resolve() not in existing:
                self._files.append(f)
                existing.add(f.resolve())
                added += 1
        self._refresh_list()
        if added == 0 and paths:
            self.status_label.setText("未发现新的支持格式图片")

    def _pick_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择图片文件",
            "",
            "图片文件 (*.avif *.webp *.jpg *.jpeg *.png *.jfif);;所有文件 (*.*)",
        )
        if files:
            self._add_paths([Path(f) for f in files])

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if folder:
            self._add_paths([Path(folder)])

    def _remove_selected(self) -> None:
        selected = {item.data(Qt.UserRole) for item in self.file_list.selectedItems()}
        if not selected:
            return
        self._files = [p for p in self._files if str(p) not in selected]
        self._refresh_list()

    def _clear_files(self) -> None:
        self._files.clear()
        self._refresh_list()
        self.progress.setValue(0)

    def _pick_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if folder:
            self._output_dir = Path(folder)
            self.output_label.setText(str(self._output_dir))

    def _reset_output_dir(self) -> None:
        self._output_dir = None
        self.output_label.setText("与源文件同目录")

    def _set_busy(self, busy: bool) -> None:
        for w in (
            self.btn_add_files,
            self.btn_add_folder,
            self.btn_remove,
            self.btn_clear,
            self.btn_choose_output,
            self.btn_reset_output,
            self.format_combo,
            self.quality_slider,
            self.btn_convert,
        ):
            w.setEnabled(not busy)
        self.btn_cancel.setEnabled(busy)
        if not busy:
            # 转换结束后恢复 slider，再按目标格式刷新 inactive 外观
            self._update_quality_enabled()
            self._repolish(self.quality_slider)

    def _start_convert(self) -> None:
        if not self._files:
            QMessageBox.information(self, "提示", "请先添加要转换的图片。")
            return

        target = self.format_combo.currentData()
        quality = self.quality_slider.value()

        self.progress.setValue(0)
        self.progress.setMaximum(len(self._files))
        self._set_busy(True)
        self.status_label.setText("正在转换…")

        self._worker = ConvertWorker(
            files=list(self._files),
            target_format=target,
            quality=quality,
            output_dir=self._output_dir,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.item_failed.connect(self._on_item_failed)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.start()

    def _cancel_convert(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.status_label.setText("正在取消…")

    def _on_progress(self, current: int, total: int, message: str) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(current)
        self.status_label.setText(message)

    def _on_item_failed(self, path: str, error: str) -> None:
        # 仅更新状态栏，最终汇总时提示
        self.status_label.setText(f"失败: {Path(path).name} — {error}")

    def _on_finished(self, success: int, fail: int) -> None:
        self._set_busy(False)
        self._worker = None
        msg = f"转换完成：成功 {success}，失败 {fail}"
        self.status_label.setText(msg)
        if fail:
            QMessageBox.warning(self, "完成（有失败）", msg)
        else:
            QMessageBox.information(self, "完成", msg)
