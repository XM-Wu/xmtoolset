"""视频格式转换逻辑（依赖 ffmpeg，由 imageio-ffmpeg 提供）。"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

SUPPORTED_FORMATS = ("MP4", "WMV", "AVI")
DEFAULT_FORMAT = "MP4"
DEFAULT_LOSSLESS = True
FORMAT_EXTENSIONS = {
    "MP4": ".mp4",
    "WMV": ".wmv",
    "AVI": ".avi",
}
INPUT_EXTENSIONS = {".mp4", ".wmv", ".avi"}

# 有损：体积小，画质会下降
_LOSSY_ENCODER_ARGS: dict[str, list[str]] = {
    "MP4": ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart"],
    "AVI": ["-c:v", "mpeg4", "-q:v", "5", "-c:a", "libmp3lame", "-q:a", "4"],
    "WMV": ["-c:v", "wmv2", "-c:a", "wmav2"],
}

# 无损 / 接近无损（默认）；WMV 容器无通用无损编解码器，退化为最高质量有损
_LOSSLESS_ENCODER_ARGS: dict[str, list[str]] = {
    "MP4": [
        "-c:v",
        "libx264",
        "-crf",
        "0",
        "-preset",
        "fast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "flac",
        "-movflags",
        "+faststart",
    ],
    "AVI": ["-c:v", "ffv1", "-c:a", "pcm_s16le"],
    "WMV": ["-c:v", "wmv2", "-qscale:v", "1", "-c:a", "wmav2", "-b:a", "320k"],
}

_DURATION_RE = re.compile(
    r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
)
_TIME_RE = re.compile(
    r"time=(\d+):(\d+):(\d+(?:\.\d+)?)",
)


def get_ffmpeg_exe() -> str:
    """解析 ffmpeg 可执行文件路径。"""
    bundled = None
    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        bundled = None

    if bundled and Path(bundled).is_file():
        return bundled

    which = shutil.which("ffmpeg")
    if which:
        return which

    raise FileNotFoundError(
        "未找到 ffmpeg。请安装 imageio-ffmpeg，或将系统 ffmpeg 加入 PATH。"
    )


def collect_video_files(paths: list[Path], recursive: bool = False) -> list[Path]:
    """从文件/目录路径收集可转换的视频文件。"""
    results: list[Path] = []
    seen: set[Path] = set()

    for path in paths:
        path = path.resolve()
        if path.is_file():
            if path.suffix.lower() in INPUT_EXTENSIONS and path not in seen:
                results.append(path)
                seen.add(path)
        elif path.is_dir():
            pattern = "**/*" if recursive else "*"
            for child in sorted(path.glob(pattern)):
                if (
                    child.is_file()
                    and child.suffix.lower() in INPUT_EXTENSIONS
                    and child not in seen
                ):
                    results.append(child)
                    seen.add(child)
    return results


def build_output_path(
    src: Path,
    output_dir: Path | None,
    target_format: str,
) -> Path:
    """根据源路径与输出目录生成目标文件路径。"""
    ext = FORMAT_EXTENSIONS[target_format.upper()]
    folder = output_dir if output_dir is not None else src.parent
    return folder / f"{src.stem}{ext}"


def _hms_to_seconds(h: str, m: str, s: str) -> float:
    return int(h) * 3600 + int(m) * 60 + float(s)


def probe_duration_seconds(ffmpeg: str, src: Path) -> float | None:
    """用 ffmpeg 探测时长（秒）；失败返回 None。"""
    try:
        proc = subprocess.run(
            [ffmpeg, "-i", str(src)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        text = (proc.stderr or "") + (proc.stdout or "")
        match = _DURATION_RE.search(text)
        if match:
            return _hms_to_seconds(*match.groups())
    except OSError:
        return None
    return None


def convert_video(
    src: Path,
    dst: Path,
    target_format: str,
    *,
    lossless: bool = DEFAULT_LOSSLESS,
    on_progress=None,
    cancel_check=None,
) -> Path:
    """
    将单个视频转换为目标格式。

    lossless=True（默认）时使用无损或接近无损编码；False 时使用有损压缩。
    on_progress(ratio: float) 可选，ratio ∈ [0, 1]
    cancel_check() 返回 True 时中止转换
    """
    target_format = target_format.upper()
    if target_format not in SUPPORTED_FORMATS:
        raise ValueError(f"不支持的目标格式: {target_format}")

    ffmpeg = get_ffmpeg_exe()
    dst.parent.mkdir(parents=True, exist_ok=True)

    duration = probe_duration_seconds(ffmpeg, src)
    encoder_map = _LOSSLESS_ENCODER_ARGS if lossless else _LOSSY_ENCODER_ARGS
    encoder = encoder_map[target_format]

    cmd = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-i",
        str(src),
        *encoder,
        str(dst),
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert proc.stderr is not None
    stderr_lines: list[str] = []
    try:
        for line in proc.stderr:
            stderr_lines.append(line)
            if cancel_check and cancel_check():
                proc.kill()
                proc.wait(timeout=10)
                raise RuntimeError("转换已取消")

            if on_progress and duration and duration > 0:
                match = _TIME_RE.search(line)
                if match:
                    current = _hms_to_seconds(*match.groups())
                    on_progress(min(current / duration, 0.99))
    finally:
        code = proc.wait()

    if cancel_check and cancel_check():
        if dst.exists():
            dst.unlink(missing_ok=True)
        raise RuntimeError("转换已取消")

    if code != 0:
        if dst.exists():
            dst.unlink(missing_ok=True)
        tail = "".join(stderr_lines[-20:]).strip() or "未知错误"
        raise RuntimeError(f"ffmpeg 失败 (code={code}): {tail}")

    if on_progress:
        on_progress(1.0)
    return dst
