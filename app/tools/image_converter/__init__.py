"""图片格式转换逻辑。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

# 注册 AVIF 编解码支持
try:
    import pillow_avif  # noqa: F401
except ImportError:
    pass

SUPPORTED_FORMATS = ("PNG", "AVIF", "WEBP", "JPEG")
DEFAULT_FORMAT = "PNG"
FORMAT_EXTENSIONS = {
    "AVIF": ".avif",
    "WEBP": ".webp",
    "JPEG": ".jpg",
    "PNG": ".png",
}
INPUT_EXTENSIONS = {
    ".avif",
    ".webp",
    ".jpg",
    ".jpeg",
    ".png",
    ".jfif",
}


def detect_format(path: Path) -> str | None:
    """根据扩展名推断输入格式。"""
    ext = path.suffix.lower()
    mapping = {
        ".avif": "AVIF",
        ".webp": "WEBP",
        ".jpg": "JPEG",
        ".jpeg": "JPEG",
        ".jfif": "JPEG",
        ".png": "PNG",
    }
    return mapping.get(ext)


def collect_image_files(paths: list[Path], recursive: bool = False) -> list[Path]:
    """从文件/目录路径收集可转换的图片文件。"""
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


def convert_image(
    src: Path,
    dst: Path,
    target_format: str,
    quality: int = 100,
) -> Path:
    """
    将单张图片转换为目标格式并写入 dst。

    quality 对 JPEG / WEBP / AVIF 生效；PNG 忽略质量参数。
    """
    target_format = target_format.upper()
    if target_format not in SUPPORTED_FORMATS:
        raise ValueError(f"不支持的目标格式: {target_format}")

    dst.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as img:
        save_kwargs: dict = {}

        if target_format == "JPEG":
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                rgba = img.convert("RGBA")
                background.paste(rgba, mask=rgba.split()[-1])
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")
            save_kwargs = {"quality": quality, "optimize": True}
        elif target_format == "PNG":
            if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                img = img.convert("RGBA")
            save_kwargs = {"optimize": True}
        elif target_format == "WEBP":
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
            save_kwargs = {"quality": quality, "method": 6}
        elif target_format == "AVIF":
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
            save_kwargs = {"quality": quality}

        img.save(dst, format=target_format, **save_kwargs)

    return dst


def build_output_path(
    src: Path,
    output_dir: Path | None,
    target_format: str,
) -> Path:
    """根据源路径与输出目录生成目标文件路径。"""
    ext = FORMAT_EXTENSIONS[target_format.upper()]
    folder = output_dir if output_dir is not None else src.parent
    return folder / f"{src.stem}{ext}"
