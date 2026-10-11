"""波点图案生成：波点直径沿指定方向、在渐变距离内从初始大小过渡到最终大小。"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from PIL import Image

ARRANGEMENTS = ("grid", "hex", "radial")
DEFAULT_ARRANGEMENT = "grid"

DIRECTIONS = (
    "left_right",
    "right_left",
    "top_bottom",
    "bottom_top",
    "center_out",
    "edge_in",
)
DEFAULT_DIRECTION = "left_right"

_MIN_AA = 0.5
_STAMP_QUANT = 4.0  # 半径按 0.25px 量化，复用图章
_DEFAULT_SHARPNESS = 90.0


@dataclass(frozen=True)
class DotPatternParams:
    width: int
    height: int
    pattern_size: float
    start_size: float
    end_size: float
    gradient_distance: float
    direction: str
    sharpness: float
    dot_rgba: tuple[int, int, int, int]
    bg_rgba: tuple[int, int, int, int]
    arrangement: str = DEFAULT_ARRANGEMENT

    def scaled(self, factor: float, width: int, height: int) -> DotPatternParams:
        """按预览缩放比例生成等效参数。"""
        factor = max(1e-6, float(factor))
        return replace(
            self,
            width=max(1, int(width)),
            height=max(1, int(height)),
            pattern_size=max(0.5, self.pattern_size * factor),
            start_size=self.start_size * factor,
            end_size=self.end_size * factor,
            gradient_distance=self.gradient_distance * factor,
        )


def render_pattern(params: DotPatternParams) -> Image.Image:
    """按目标尺寸绘制波点图案。"""
    width = max(1, int(params.width))
    height = max(1, int(params.height))
    spacing = max(0.5, float(params.pattern_size))
    start_d = max(0.0, float(params.start_size))
    end_d = max(0.0, float(params.end_size))
    distance = max(0.0, float(params.gradient_distance))
    direction = params.direction if params.direction in DIRECTIONS else DEFAULT_DIRECTION
    arrangement = params.arrangement if params.arrangement in ARRANGEMENTS else DEFAULT_ARRANGEMENT
    sharpness = max(0.0, min(100.0, float(params.sharpness)))
    rgba = _clamp_rgba(params.dot_rgba)
    bg = _clamp_rgba(params.bg_rgba)

    canvas = Image.new("RGBA", (width, height), bg)
    extra = max(start_d, end_d) / 2.0 + spacing
    stamps: dict[tuple[int, int], Image.Image | None] = {}

    for cx, cy in _iter_centers(width, height, spacing, arrangement, extra):
        t = _size_progress(cx, cy, width, height, distance, direction)
        diameter = start_d + (end_d - start_d) * t
        radius = diameter / 2.0
        falloff = _edge_falloff(radius, sharpness)
        stamp = _get_stamp(stamps, radius, falloff, rgba)
        if stamp is not None:
            _composite_stamp(canvas, stamp, cx, cy)

    return canvas


def _size_progress(
    x: float,
    y: float,
    width: int,
    height: int,
    distance: float,
    direction: str,
) -> float:
    """0 = 初始大小，1 = 最终大小。渐变距离为 0 时全部使用初始大小。"""
    if distance <= 1e-6:
        return 0.0
    w = float(width)
    h = float(height)
    if direction == "right_left":
        pos = w - x
    elif direction == "top_bottom":
        pos = y
    elif direction == "bottom_top":
        pos = h - y
    elif direction == "center_out":
        pos = math.hypot(x - w * 0.5, y - h * 0.5)
    elif direction == "edge_in":
        pos = math.hypot(w * 0.5, h * 0.5) - math.hypot(x - w * 0.5, y - h * 0.5)
    else:
        pos = x
    t = pos / distance
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t


def _iter_centers(
    width: int,
    height: int,
    spacing: float,
    arrangement: str,
    extra: float,
):
    if arrangement == "radial":
        yield from _iter_radial_centers(width, height, spacing, extra)
        return

    if arrangement == "hex":
        row_h = spacing * math.sqrt(3) / 2.0
        if row_h < 0.5:
            row_h = 0.5
        j0 = int(math.floor(-extra / row_h)) - 1
        j1 = int(math.ceil((height + extra) / row_h)) + 1
        i0 = int(math.floor(-extra / spacing)) - 1
        i1 = int(math.ceil((width + extra) / spacing)) + 1
        for j in range(j0, j1 + 1):
            ox = spacing * 0.5 if (j & 1) else 0.0
            for i in range(i0, i1 + 1):
                yield (i * spacing + ox, j * row_h)
        return

    i0 = int(math.floor((-extra - spacing * 0.5) / spacing))
    i1 = int(math.ceil((width + extra - spacing * 0.5) / spacing))
    j0 = int(math.floor((-extra - spacing * 0.5) / spacing))
    j1 = int(math.ceil((height + extra - spacing * 0.5) / spacing))
    for j in range(j0, j1 + 1):
        for i in range(i0, i1 + 1):
            yield (spacing * (i + 0.5), spacing * (j + 0.5))


def _iter_radial_centers(
    width: int,
    height: int,
    spacing: float,
    extra: float,
):
    """从画布中心向外，按同心圆放置波点；环间距与环上弧长均约等于图案大小。"""
    ox = width / 2.0
    oy = height / 2.0
    yield (ox, oy)

    max_r = math.hypot(width / 2.0, height / 2.0) + extra
    ring = 1
    r = spacing
    while r <= max_r and ring <= 8192:
        count = max(6, int(round(2.0 * math.pi * r / spacing)))
        offset = 0.0 if ring % 2 == 0 else math.pi / count
        step = 2.0 * math.pi / count
        for i in range(count):
            ang = offset + i * step
            yield (ox + r * math.cos(ang), oy + r * math.sin(ang))
        ring += 1
        r = ring * spacing


def _edge_falloff(radius: float, sharpness: float) -> float:
    """锐度 100 为硬边（仅保留抗锯齿），0 为整颗波点从中心柔化到边缘。"""
    s = max(0.0, min(100.0, sharpness)) / 100.0
    falloff = radius * (1.0 - s)
    if falloff < _MIN_AA:
        return min(radius, _MIN_AA)
    if falloff > radius:
        return radius
    return falloff


def _get_stamp(
    cache: dict[tuple[int, int], Image.Image | None],
    radius: float,
    falloff: float,
    rgba: tuple[int, int, int, int],
) -> Image.Image | None:
    r_key = int(round(radius * _STAMP_QUANT))
    f_key = int(round(falloff * _STAMP_QUANT))
    key = (r_key, f_key)
    if key in cache:
        return cache[key]
    stamp = _circle_stamp(r_key / _STAMP_QUANT, f_key / _STAMP_QUANT, rgba)
    cache[key] = stamp
    return stamp


def _circle_stamp(
    radius: float,
    falloff: float,
    rgba: tuple[int, int, int, int],
) -> Image.Image | None:
    if radius < 0.25:
        return None
    falloff = max(_MIN_AA, min(radius, float(falloff)))
    size = int(math.ceil((radius + 1.0) * 2.0 + 2.0))
    if size < 1:
        return None
    cx = cy = size / 2.0
    inner = max(0.0, radius - falloff)
    inv = 1.0 / falloff
    buf = bytearray(size * size)
    for y in range(size):
        py = y + 0.5 - cy
        row = y * size
        py2 = py * py
        for x in range(size):
            px = x + 0.5 - cx
            dist = math.sqrt(px * px + py2)
            if dist <= inner:
                buf[row + x] = 255
            elif dist >= radius:
                buf[row + x] = 0
            else:
                t = (radius - dist) * inv
                t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
                buf[row + x] = int(t * 255.0 + 0.5)

    r, g, b, a = rgba
    mask = Image.frombytes("L", (size, size), bytes(buf))
    if a < 255:
        mask = mask.point(lambda p, alpha=a: p * alpha // 255)
    stamp = Image.new("RGBA", (size, size), (r, g, b, 255))
    stamp.putalpha(mask)
    return stamp


def _composite_stamp(canvas: Image.Image, stamp: Image.Image, cx: float, cy: float) -> None:
    sw, sh = stamp.size
    x0 = int(round(cx - sw / 2.0))
    y0 = int(round(cy - sh / 2.0))
    cw, ch = canvas.size
    if x0 >= cw or y0 >= ch or x0 + sw <= 0 or y0 + sh <= 0:
        return
    sx0 = 0 if x0 >= 0 else -x0
    sy0 = 0 if y0 >= 0 else -y0
    sx1 = min(sw, cw - x0)
    sy1 = min(sh, ch - y0)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    dest_x = max(x0, 0)
    dest_y = max(y0, 0)
    piece = stamp if (sx0, sy0, sx1, sy1) == (0, 0, sw, sh) else stamp.crop((sx0, sy0, sx1, sy1))
    canvas.alpha_composite(piece, dest=(dest_x, dest_y))


def _clamp_rgba(color: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    r, g, b, a = (max(0, min(255, int(c))) for c in color)
    return r, g, b, a
