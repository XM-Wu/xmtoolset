"""视频格式转换后台工作线程。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.tools.video_converter import build_output_path, convert_video


class ConvertWorker(QThread):
    """在后台批量转换视频，避免阻塞 UI。"""

    progress = Signal(int, int, str)  # current_index, total, message
    file_progress = Signal(int)  # 0-100 for current file
    finished_ok = Signal(int, int)  # success_count, fail_count
    item_failed = Signal(str, str)  # path, error

    def __init__(
        self,
        files: list[Path],
        target_format: str,
        output_dir: Path | None,
        *,
        lossless: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._files = files
        self._target_format = target_format
        self._output_dir = output_dir
        self._lossless = lossless
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

            self.file_progress.emit(0)
            self.progress.emit(index, total, f"转换中: {src.name}")

            try:
                dst = build_output_path(src, self._output_dir, self._target_format)
                if dst.resolve() == src.resolve():
                    dst = dst.with_name(f"{dst.stem}_converted{dst.suffix}")

                def on_progress(ratio: float, _i=index, _t=total, _name=src.name) -> None:
                    self.file_progress.emit(int(ratio * 100))
                    self.progress.emit(
                        _i,
                        _t,
                        f"转换中: {_name} ({int(ratio * 100)}%)",
                    )

                convert_video(
                    src,
                    dst,
                    self._target_format,
                    lossless=self._lossless,
                    on_progress=on_progress,
                    cancel_check=lambda: self._cancelled,
                )
                success += 1
                self.file_progress.emit(100)
                self.progress.emit(index, total, f"完成: {src.name} → {dst.name}")
            except Exception as exc:  # noqa: BLE001
                if self._cancelled and "取消" in str(exc):
                    self.progress.emit(index, total, "已取消")
                    break
                fail += 1
                self.item_failed.emit(str(src), str(exc))
                self.progress.emit(index, total, f"失败: {src.name}")

        self.finished_ok.emit(success, fail)
