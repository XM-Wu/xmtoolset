"""Lossless vertical PNG splitting, independent of preview transforms."""
from pathlib import Path
from PIL import Image, ImageOps

MAX_PIXELS = 67_108_864


def load_png(path):
    with Image.open(path) as source:
        if source.format != 'PNG':
            raise ValueError('请选择 PNG 图片')
        if source.width * source.height > MAX_PIXELS:
            raise ValueError('图片超过 6,700 万像素，请先缩小图片')
        source.load()
        image = ImageOps.exif_transpose(source)
        return image.copy()


def equal_cuts(width, count=3):
    count = max(1, min(int(count), width))
    return [width * i // count for i in range(1, count)]


def intervals(width, cuts):
    values = sorted(set(int(x) for x in cuts))
    if any(x <= 0 or x >= width for x in values):
        raise ValueError('切割线必须位于图片内部')
    boundaries = [0, *values, width]
    return list(zip(boundaries, boundaries[1:]))


def export_slices(image, cuts, directory, stem):
    """Create a new output folder; never overwrite existing files or the source."""
    ranges = intervals(image.width, cuts)
    parent = Path(directory)
    if not parent.is_dir():
        raise ValueError('导出目录不存在')
    # The caller normally passes a source stem; normalize for filesystem safety.
    stem = ''.join(c if c not in '<>:"/\\|?*' and ord(c) >= 32 else '_' for c in stem).strip(' .')[:100] or 'image'
    index = 1
    while True:
        folder = parent / (stem + '_切分' + (f'_{index}' if index > 1 else ''))
        try:
            folder.mkdir()
            break
        except FileExistsError:
            index += 1
    files = []
    metadata = {key: image.info[key] for key in ('icc_profile', 'dpi') if key in image.info}
    try:
        for i, (left, right) in enumerate(ranges, 1):
            dest = folder / f'{stem}_{i:02d}.png'
            files.append(dest)
            image.crop((left, 0, right, image.height)).save(dest, 'PNG', **metadata)
    except Exception:
        for file in files:
            file.unlink(missing_ok=True)
        folder.rmdir()
        raise
    return files
