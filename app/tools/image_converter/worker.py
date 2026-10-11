"""图片格式转换后台工作线程。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.tools.image_converter import build_output_path, convert_image


class ConvertWorker(QThread):
    """在后台批量转换图片，避免阻塞 UI。"""

    progress = Signal(int, int, str)  # current, total, message
    finished_ok = Signal(int, int)  # success_count, fail_count
    item_failed = Signal(str, str)  # path, error

    def __init__(
        self,
        files: list[Path],
        target_format: str,
        quality: int,
        output_dir: Path | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._files = files
        self._target_format = target_format
        self._quality = quality
        self._output_dir = output_dir
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        total = len(self._files)
        success = 0
        fail = 0

        for index, src in enumerate(self._files, start=1):
            if self._cancelled:
                break

            try:
                dst = build_output_path(src, self._output_dir, self._target_format)
                # 禁止覆盖源文件（同路径同格式时追加后缀）
                if dst.resolve() == src.resolve():
                    dst = dst.with_name(f"{dst.stem}_converted{dst.suffix}")

                convert_image(src, dst, self._target_format, self._quality)
                success += 1
                self.progress.emit(index, total, f"完成: {src.name} → {dst.name}")
            except Exception as exc:  # noqa: BLE001
                fail += 1
                self.item_failed.emit(str(src), str(exc))
                self.progress.emit(index, total, f"失败: {src.name}")

        self.finished_ok.emit(success, fail)
