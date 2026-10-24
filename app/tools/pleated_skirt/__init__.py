"""Twill weave masks and rule-colored tartan base-color textures."""
from dataclasses import dataclass, field, asdict
from math import lcm
import re


@dataclass(frozen=True)
class Band:
    color: str
    threads: int


def default_bands():
    cream, gold, brown, blue, yellow = '#f4edce', '#c58a2b', '#594b30', '#424b94', '#efda8b'
    return tuple(Band(color, count) for color, count in [
        (cream,64),(gold,4),(cream,4),(gold,4),(cream,8),(gold,6),
        (yellow,20),(brown,32),(cream,16),(blue,2),(brown,12),(blue,6),
        (cream,8),(gold,4),(cream,4),(blue,6),(cream,6),(gold,4),(cream,18)])


@dataclass(frozen=True)
class PlaidParams:
    warp: tuple[Band, ...] = field(default_factory=default_bands)
    weft: tuple[Band, ...] = field(default_factory=default_bands)
    thread_size: int = 2
    over: int = 2
    under: int = 2
    reverse: bool = False
    repeats_x: int = 1
    repeats_y: int = 1

    def dimensions(self):
        validate(self)
        period = self.over + self.under
        return (lcm(sum(b.threads for b in self.warp), period)*self.thread_size,
                lcm(sum(b.threads for b in self.weft), period)*self.thread_size)


REFERENCE_PRESET_NAME = '奶油金棕蓝格纹'
REFERENCE_PRESET = PlaidParams()


def validate(p):
    for value, low, high in [(p.thread_size,1,16),(p.over,1,8),(p.under,1,8),(p.repeats_x,1,8),(p.repeats_y,1,8)]:
        if type(value) is not int or not low <= value <= high:
            raise ValueError('线宽、交织与重复次数超出范围')
    if type(p.reverse) is not bool:
        raise ValueError('斜纹方向无效')
    for bands in (p.warp,p.weft):
        if not 1 <= len(bands) <= 64:
            raise ValueError('每个方向需要 1～64 条色带')
        for band in bands:
            if not isinstance(band.color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',band.color):
                raise ValueError('颜色应为 #RRGGBB')
            if type(band.threads) is not int or not 1 <= band.threads <= 512:
                raise ValueError('每条色带的线数应为 1～512')
        if sum(b.threads for b in bands)>2048:
            raise ValueError('每个方向的色带线数总计不能超过 2048')


def from_dict(data):
    if not isinstance(data,dict) or data.get('schema') != 1:
        raise ValueError('不是有效的格纹规则文件')
    values=data['params'].copy()
    for axis in ('warp','weft'):
        values[axis]=tuple(Band(**b) for b in values[axis])
    p=PlaidParams(**values)
    render_svg(p)
    return p


def to_dict(p):
    return {'schema':1,'params':asdict(p)}


def _colors(bands, size):
    cycle=[band.color for band in bands for _ in range(band.threads)]
    return [cycle[i%len(cycle)] for i in range(size)]


def render_svg(p: PlaidParams, stage='color', tile=False):
    """Black = warp on top. White = weft on top. Colors never alpha-blend."""
    if stage not in ('structure','color'):
        raise ValueError('未知预览阶段')
    tw,th=p.dimensions()
    rx,ry=(1,1) if tile else (p.repeats_x,p.repeats_y)
    width,height=tw*rx,th*ry
    if width>8192 or height>8192:
        raise ValueError(f'无缝单元为 {tw} × {th} px；重复后超出 8192 px，请减少线数、线宽或重复次数')
    size=p.thread_size
    nx,ny=tw//size,th//size
    period=p.over+p.under
    warp=_colors(p.warp,nx) if stage=='color' else ['#000000']*nx
    weft=_colors(p.weft,ny) if stage=='color' else ['#ffffff']*ny
    # Each phase is one row of warp segments; reusing it keeps SVG size bounded.
    definitions=[]
    for phase in range(period):
        paths={}
        start=0
        while start<nx:
            visible=((start+(-phase if p.reverse else phase))%period)<p.over
            if not visible:
                start+=1;continue
            end=start+1
            while end<nx and warp[end]==warp[start] and (end+(-phase if p.reverse else phase))%period<p.over:
                end+=1
            span=(end-start)*size
            paths.setdefault(warp[start],[]).append(f'M{start*size} 0h{span}v{size}h{-span}z')
            start=end
        content=''.join(f'<path fill="{color}" d="{"".join(path)}"/>' for color,path in paths.items())
        definitions.append(f'<g id="row{phase}">{content}</g>')
    base=[];start=0
    while start<ny:
        end=start+1
        while end<ny and weft[end]==weft[start]:end+=1
        base.append(f'<rect x="0" y="{start*size}" width="{tw}" height="{(end-start)*size}" fill="{weft[start]}"/>')
        start=end
    base.extend(f'<use xlink:href="#row{y%period}" y="{y*size}"/>' for y in range(ny))
    definitions.append('<g id="tile">'+''.join(base)+'</g>')
    tiles=''.join(f'<use xlink:href="#tile" x="{x*tw}" y="{y*th}"/>' for y in range(ry) for x in range(rx))
    return f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}" shape-rendering="crispEdges"><defs>{"".join(definitions)}</defs>{tiles}</svg>'
