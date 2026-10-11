"""视频格式转换工具界面。"""

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
    QVBoxLayout,
    QWidget,
)

from app.tools.base_tool import BaseTool
from app.tools.video_converter import (
    DEFAULT_FORMAT,
    DEFAULT_LOSSLESS,
    SUPPORTED_FORMATS,
    collect_video_files,
    get_ffmpeg_exe,
)
from app.tools.video_converter.worker import ConvertWorker
from app.widgets.drop_list import DropListWidget


class VideoConverterTool(BaseTool):
    tool_id = "video_converter"
    tool_name = "视频格式转换"
    tool_description = "在 WMV / MP4 / AVI 之间互转"

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

        title = QLabel("视频格式转换")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        hint = QLabel(
            "支持将视频在 WMV、MP4、AVI 之间互转（默认输出 MP4，默认无损）。"
            "无损体积更大；WMV 无通用无损编码，该格式下为最高质量有损。"
            "可拖放文件或文件夹到列表。转换依赖 ffmpeg。"
        )
        hint.setObjectName("mutedLabel")
        hint.setWordWrap(True)
        root.addWidget(hint)

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

        opt_box = QGroupBox("转换选项")
        form = QFormLayout(opt_box)

        self.format_combo = QComboBox()
        for fmt in SUPPORTED_FORMATS:
            self.format_combo.addItem(fmt, fmt)
        idx = self.format_combo.findData(DEFAULT_FORMAT)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)
        form.addRow("目标格式", self.format_combo)

        self.quality_combo = QComboBox()
        self.quality_combo.addItem("无损", True)
        self.quality_combo.addItem("有损", False)
        quality_idx = self.quality_combo.findData(DEFAULT_LOSSLESS)
        if quality_idx >= 0:
            self.quality_combo.setCurrentIndex(quality_idx)
        form.addRow("质量", self.quality_combo)

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

        self.progress = QProgressBar()
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.file_progress = QProgressBar()
        self.file_progress.setValue(0)
        self.file_progress.setFormat("当前文件 %p%")
        root.addWidget(self.file_progress)

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

        self.btn_add_files.clicked.connect(self._pick_files)
        self.btn_add_folder.clicked.connect(self._pick_folder)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear.clicked.connect(self._clear_files)
        self.btn_choose_output.clicked.connect(self._pick_output_dir)
        self.btn_reset_output.clicked.connect(self._reset_output_dir)
        self.btn_convert.clicked.connect(self._start_convert)
        self.btn_cancel.clicked.connect(self._cancel_convert)

    def _refresh_list(self) -> None:
        self.file_list.clear()
        for path in self._files:
            item = QListWidgetItem(str(path))
            item.setData(Qt.UserRole, str(path))
            self.file_list.addItem(item)
        self.status_label.setText(f"已添加 {len(self._files)} 个文件")

    def _add_paths(self, paths: list[Path]) -> None:
        new_files = collect_video_files(paths, recursive=True)
        existing = {p.resolve() for p in self._files}
        added = 0
        for f in new_files:
            if f.resolve() not in existing:
                self._files.append(f)
                existing.add(f.resolve())
                added += 1
        self._refresh_list()
        if added == 0 and paths:
            self.status_label.setText("未发现新的支持格式视频 (mp4 / wmv / avi)")

    def _pick_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择视频文件",
            "",
            "视频文件 (*.mp4 *.wmv *.avi);;所有文件 (*.*)",
        )
        if files:
            self._add_paths([Path(f) for f in files])

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择视频文件夹")
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
        self.file_progress.setValue(0)

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
            self.quality_combo,
            self.btn_convert,
        ):
            w.setEnabled(not busy)
        self.btn_cancel.setEnabled(busy)

    def _start_convert(self) -> None:
        if not self._files:
            QMessageBox.information(self, "提示", "请先添加要转换的视频。")
            return

        try:
            get_ffmpeg_exe()
        except FileNotFoundError as exc:
            QMessageBox.critical(self, "缺少 ffmpeg", str(exc))
            return

        target = self.format_combo.currentData()
        lossless = bool(self.quality_combo.currentData())
        self.progress.setValue(0)
        self.progress.setMaximum(len(self._files))
        self.file_progress.setValue(0)
        self._set_busy(True)
        self.status_label.setText("正在转换…")

        self._worker = ConvertWorker(
            files=list(self._files),
            target_format=target,
            output_dir=self._output_dir,
            lossless=lossless,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.file_progress.connect(self.file_progress.setValue)
        self._worker.item_failed.connect(self._on_item_failed)
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.start()

    def _cancel_convert(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            self.status_label.setText("正在取消…")

    def _on_progress(self, current: int, total: int, message: str) -> None:
        self.progress.setMaximum(total)
        # current 为正在处理的序号；完成时才等于 current
        self.progress.setValue(max(current - 1, 0))
        self.status_label.setText(message)

    def _on_item_failed(self, path: str, error: str) -> None:
        self.status_label.setText(f"失败: {Path(path).name} — {error}")

    def _on_finished(self, success: int, fail: int) -> None:
        self._set_busy(False)
        total = success + fail
        self.progress.setValue(total if total else 0)
        self._worker = None
        msg = f"转换完成：成功 {success}，失败 {fail}"
        self.status_label.setText(msg)
        if fail:
            QMessageBox.warning(self, "完成（有失败）", msg)
        else:
            QMessageBox.information(self, "完成", msg)
