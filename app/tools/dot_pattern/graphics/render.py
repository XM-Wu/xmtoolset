"""Generate portable SVG; preview and PNG export use the same document.

Geometry is expressed in output pixels, independent of preview size and zoom.
No remote scripts, fonts, or image URLs are used.
"""
from __future__ import annotations

import base64
import html
import io
import math
import random
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from PIL import Image

from .catalog import defaults

TAU = math.tau

def fmt(x):
    return f'{x:.3f}'.rstrip('0').rstrip('.') or '0'

def polar(x, y, r, a):
    a = math.radians(a)
    return x + r * math.cos(a), y + r * math.sin(a)

def points_text(points):
    return ' '.join(f'{fmt(x)},{fmt(y)}' for x, y in points)

def rgba(value):
    from PySide6.QtGui import QColor
    color = QColor(str(value))
    if not color.isValid():
        raise ValueError('无效颜色：' + str(value))
    return color.name(), color.alphaF()

def paint(value, attribute='stroke'):
    color, alpha = rgba(value)
    return f'{attribute}="{color}" {attribute}-opacity="{fmt(alpha)}"'

@dataclass
class Document:
    svg: str
    width: int
    height: int
    hits: list = field(default_factory=list)

    def hit(self, x, y, tolerance=8):
        best, distance = None, float('inf')
        for key, points, closed in self.hits:
            if closed and _inside(x, y, points):
                return key
            for a, b in zip(points, points[1:]):
                vx, vy = b[0]-a[0], b[1]-a[1]
                t = max(0, min(1, ((x-a[0])*vx+(y-a[1])*vy)/(vx*vx+vy*vy or 1)))
                d = math.hypot(x-a[0]-t*vx, y-a[1]-t*vy)
                if d < distance:
                    best, distance = key, d
        return best if distance <= tolerance else None

def _inside(x, y, vertices):
    inside = False
    for (ax, ay), (bx, by) in zip(vertices, vertices[1:]+vertices[:1]):
        if (ay > y) != (by > y) and x < (bx-ax)*(y-ay)/(by-ay)+ax:
            inside = not inside
    return inside

@lru_cache(maxsize=16)
def _image_data(filename, modified):
    path = Path(filename)
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError('图片须小于 20 MB')
    if path.suffix.lower() == '.svg':
        from PySide6.QtCore import QByteArray
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
        renderer = QSvgRenderer(QByteArray(path.read_bytes()))
        if not renderer.isValid():
            raise ValueError('无法读取 SVG 图片')
        size = renderer.defaultSize()
        size.scale(1024, 1024, __import__('PySide6.QtCore', fromlist=['Qt']).Qt.KeepAspectRatio)
        qimage = QImage(size, QImage.Format_RGBA8888)
        qimage.fill(0)
        painter = QPainter(qimage)
        renderer.render(painter)
        painter.end()
        image = Image.frombytes('RGBA', (qimage.width(), qimage.height()), bytes(qimage.bits()))
    else:
        with Image.open(path) as source:
            source.thumbnail((1024, 1024))
            image = source.convert('RGBA')
    buffer = io.BytesIO()
    image.save(buffer, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode(), image

def image_data(filename):
    path = Path(filename)
    return _image_data(str(path), path.stat().st_mtime_ns)

def tile_size(kind, p):
    s = p.get('spacing', 32)
    if kind == 'polygon':
        side = p['side']
        return (3*side, math.sqrt(3)*side) if p['shape']=='hexagon' else (side, math.sqrt(3)*side)
    if kind == 'symbols':
        s = p['size'] + p['spacing']
    if kind == 'matrix' and p['diagonal']:
        s *= math.sqrt(2)
    return max(1,s), max(1,2*s if kind=='lines' and p['direction']=='dots' else s)

def render(kind, values, width=512, height=512, background=None, hidden=(), styles=None):
    p = defaults(kind) | values
    width, height = int(width), int(height)
    if not (16 <= width <= 8192 and 16 <= height <= 8192):
        raise ValueError('画布尺寸应在 16～8192 像素之间')
    hidden, styles = set(hidden), styles or {}
    out, hits = [], []
    cx, cy = width/2, height/2
    color, stroke = p.get('color', '#89b4fa'), p.get('stroke', 2)
    rng = random.Random(p.get('seed', 1))
    angle = p.get('angle', 0)
    point_count = 0

    def poly(points, fill=False, closed=False, key=None, ink=None, line=None, extra=''):
        nonlocal point_count
        point_count += len(points)
        if point_count > 500000:
            raise ValueError('图形过于密集，请增大间距、减小数量或画布尺寸')
        if key is not None:
            hits.append((str(key), points, closed))
            if str(key) in hidden:
                return
        custom = styles.get(str(key), {})
        ink = custom.get('color', ink or color)
        line = custom.get('stroke', stroke if line is None else line)
        tag = 'polygon' if closed else 'polyline'
        dash = custom.get('dash', p.get('dash', 0))
        if dash > 0:
            extra += f' stroke-dasharray="{fmt(dash)} {fmt(p.get("dash_gap", dash))}"'
        fill_attr = paint(ink, 'fill') if fill else 'fill="none"'
        out.append(f'<{tag} points="{points_text(points)}" {fill_attr} {paint(ink)} stroke-width="{fmt(line)}" stroke-linejoin="round" stroke-linecap="{p.get("cap", "butt")}" {extra}/>')

    def ellipse(x,y,rx,ry=None,fill=False,ink=None,line=None):
        ry = rx if ry is None else ry
        if rx <= 0 or ry <= 0:
            return
        ink = ink or color
        out.append(f'<ellipse cx="{fmt(x)}" cy="{fmt(y)}" rx="{fmt(rx)}" ry="{fmt(ry)}" {paint(ink,"fill") if fill else "fill=\"none\""} {paint(ink)} stroke-width="{fmt(stroke if line is None else line)}"/>')

    def shape(x, y, size, form, key=None, fill=True, ink=None, line=0):
        if size <= 0:
            return
        sides = {'circle':32, 'square':4, 'diamond':4, 'triangle':3, 'hexagon':6, 'ring':48}.get(form,4)
        radius = size/2 * (math.sqrt(2) if form=='square' else 1)
        offset = 45 if form=='square' else -90
        pts = [polar(x,y,radius,offset+i*360/sides) for i in range(sides)]
        poly(pts, fill and form!='ring', True, key, ink, max(1,line) if form=='ring' else line)

    def arc(radius, start, sweep):
        return [polar(cx,cy,radius,start+sweep*i/max(1,math.ceil(abs(sweep)))) for i in range(max(1,math.ceil(abs(sweep)))+1)]

    def rotated(points):
        a = math.radians(angle)
        return [(cx+(x-cx)*math.cos(a)-(y-cy)*math.sin(a), cy+(x-cx)*math.sin(a)+(y-cy)*math.cos(a)) for x,y in points]

    if kind == 'concentric':
        for i in range(p['count']):
            t = i/max(1,p['count']-1)
            radius = p['inner']+(p['radius']-p['inner'])*t
            if radius > 0:
                poly(arc(radius,angle,p['sweep']), line=p['inner_stroke']+(stroke-p['inner_stroke'])*t)
    elif kind == 'hud':
        pts = []
        a0 = min(p['sweep'],p['notch_angle'])
        a1 = min(p['sweep'],a0+p['notch_arc'])
        chamfer = max(.001,min(p['chamfer'],(a1-a0)/2))
        for i in range(math.ceil(p['sweep']*2)+1):
            a = min(p['sweep'],i/2)
            mix = max(0,min(1,(a-a0)/chamfer,(a1-a)/chamfer))
            pts.append(polar(cx,cy,max(1,p['radius']+p['depth']*mix),angle+a))
        poly(pts)
        for i,a in ((0,angle),(-1,angle+p['sweep'])):
            x,y=pts[i]
            if p['end']=='dot':
                ellipse(x,y,max(1,p['cap_length']/3),fill=True,line=0)
            elif p['end']!='none':
                poly([(x,y),polar(x,y,p['cap_length'],a+(90 if p['end']=='perp' else p['cap_angle']))])
    elif kind == 'scale':
        for i in range(p['count']):
            a = angle + p['sweep']*i/(p['count'] if p['sweep']==360 else max(1,p['count']-1))
            length = max(.1,p['length']*(p['major_scale'] if i%p['major']==0 else 1)+p['amplitude']*math.sin(math.radians(a)*p['frequency'])+rng.uniform(-p['jitter'],p['jitter']))
            low = p['radius'] - length*({'center':.5,'inner':1,'outer':0}[p['alignment']])
            poly([polar(cx,cy,low,a),polar(cx,cy,low+length,a)])
    elif kind in ('halftone','matrix'):
        spacing = p['spacing']
        row_step = spacing*(math.sqrt(3)/2 if p.get('arrangement')=='hex' else 1)
        finite = p.get('finite',False)
        diagonal_grid = p.get('diagonal') and not finite
        if diagonal_grid:
            row_step=spacing/math.sqrt(2)
            spacing*=math.sqrt(2)
        rows = p['rows'] if finite else math.ceil(height/row_step)+3
        cols = p['columns'] if finite else math.ceil(width/spacing)+3
        if rows*cols>100000:
            raise ValueError('点数量超过 100,000，请增大间距或缩小画布')
        custom = image_data(p['shape_file'])[0] if p.get('shape_file') else None
        mask = image_data(p['mask_file'])[1] if p.get('mask')=='image' and p.get('mask_file') else None
        if p.get('mask')=='image' and mask is None:
            raise ValueError('请选择轮廓图片')
        for row in range(rows):
            for col in range(cols):
                x = (cx+(col-(cols-1)/2)*spacing) if finite else (col-1)*spacing
                y = (cy+(row-(rows-1)/2)*row_step) if finite else (row-1)*row_step
                if p.get('arrangement')=='hex' and row%2:
                    x += spacing/2
                if diagonal_grid and row%2:
                    x += spacing/2
                if p.get('diagonal') and finite:
                    dx,dy=x-cx,y-cy
                    x,y=cx+(dx-dy)/math.sqrt(2),cy+(dx+dy)/math.sqrt(2)
                size = p['size']
                edge=1
                if kind=='halftone':
                    a=math.radians(angle)
                    t = (math.hypot(x-cx,y-cy)/max(1,math.hypot(cx,cy))) if p['gradient']=='radial' else .5+((x-cx)*math.cos(a)+(y-cy)*math.sin(a))/max(1,abs(width*math.cos(a))+abs(height*math.sin(a)))
                    t=max(0,min(1,t))
                    if p['invert']: t=1-t
                    if p['ease']=='exp': t=t*t
                    if p['ease']=='sin': t=(1-math.cos(t*math.pi))/2
                    size=p['min_size']+(p['size']-p['min_size'])*t
                    mw,mh=p['mask_width']/2,p['mask_height']/2
                    dx,dy=abs(x-cx),abs(y-cy)
                    form=p['mask']
                    if form=='circle':
                        edge=(1-math.hypot(dx/mw,dy/mh))*min(mw,mh)
                    elif form=='rect':
                        r=min(p['corner'],mw,mh)
                        edge=min(mw-dx,mh-dy,r-math.hypot(max(0,dx-mw+r),max(0,dy-mh+r))) if r else min(mw-dx,mh-dy)
                    elif form=='hexagon':
                        edge=min(mh-dy, (mw-dx)-dy*mw/(2*mh))
                    elif mask:
                        ix,iy=int((x-cx+mw)*mask.width/(2*mw)),int((y-cy+mh)*mask.height/(2*mh))
                        edge=spacing*mask.getpixel((ix,iy))[3]/255 if 0<=ix<mask.width and 0<=iy<mask.height else -1
                    if edge<0: continue
                    if p['edge_zero'] and form!='full': size*=max(0,min(1,edge/spacing))
                key=f'{row}:{col}'
                if custom:
                    hits.append((key,[(x-size/2,y-size/2),(x+size/2,y-size/2),(x+size/2,y+size/2),(x-size/2,y+size/2)],True))
                    if key not in hidden:
                        out.append(f'<image x="{fmt(x-size/2)}" y="{fmt(y-size/2)}" width="{fmt(size)}" height="{fmt(size)}" xlink:href="{custom}"/>')
                else:
                    shape(x,y,size,p['shape'],key)
    elif kind == 'wave':
        extent=math.hypot(width,height)
        for y in range(-math.ceil(extent),math.ceil(extent),max(1,round(p['spacing']))):
            pts=[(cx+x,cy+y+p['amplitude']*math.sin(x*p['frequency'])) for x in range(-math.ceil(extent),math.ceil(extent)+3,3)]
            poly(rotated(pts))
    elif kind == 'lines':
        s=p['spacing']; direction=p['direction']
        if direction in ('horizontal','vertical'):
            for i in range(math.ceil(max(width,height)/s)+1):
                poly([(0,i*s),(width,i*s)] if direction=='horizontal' else [(i*s,0),(i*s,height)])
        elif direction=='dots':
            for row in range(math.ceil(height/s)+1):
                for col in range(math.ceil(width/s)+1):
                    ellipse(col*s+(row%2)*s/2,row*s,stroke/2,fill=True,line=0)
        else:
            for i in range(-math.ceil(height/s)-1,math.ceil(width/s)+1):
                poly([(i*s,0),(i*s+height,height)])
    elif kind == 'polygon':
        side=p['side']; h=side*math.sqrt(3)/2
        rows=math.ceil(height/h)+3; cols=math.ceil(width/(side/2))+3
        if rows*cols>100000: raise ValueError('网格过密，请增大边长')
        for row in range(-1,rows):
            for col in range(-1,cols):
                if p['shape']=='hexagon':
                    if col%3: continue
                    x,y=col*side/2,row*2*h+(h if (col//3)%2 else 0)
                    pts=[polar(x,y,side,i*60) for i in range(6)]
                else:
                    x,y=col*side/2,row*h
                    pts=[(x,y),(x+side,y),(x+side/2,y+h)] if (row+col)%2==0 else [(x,y+h),(x+side,y+h),(x+side/2,y)]
                if p['grid']: poly(pts,closed=True,ink=p['grid_color'],line=1)
                mx,my=sum(x for x,y in pts)/len(pts),sum(y for x,y in pts)/len(pts)
                pts=[(mx+(x-mx)*p['cell_scale']/100,my+(y-my)*p['cell_scale']/100) for x,y in pts]
                poly(pts,fill=p['fill'],closed=True,key=f'{row}:{col}')
    elif kind == 'nested':
        from PySide6.QtGui import QColor
        c1,c2=QColor(color),QColor(p['end_color'])
        for i in range(p['count']):
            r=p['radius']-i*p['step']
            if r<=0: break
            t=i/max(1,p['count']-1) if p['gradient'] else 0
            mix=QColor(*[round(a+(b-a)*t) for a,b in zip(c1.getRgb(),c2.getRgb())]).name(QColor.HexArgb)
            poly([polar(cx,cy,r,angle-90+i*p['rotation_step']+j*360/p['sides']) for j in range(p['sides'])],closed=True,ink=mix)
    elif kind == 'globe':
        rx,ry=p['axis_w']/2,p['axis_h']/2
        for i in range(p['meridians']+1):
            ratio=math.cos(math.pi*i/max(1,p['meridians']))
            poly(rotated([(cx+rx*ratio*math.cos(t*TAU/240),cy+ry*math.sin(t*TAU/240)) for t in range(241)]))
        poly(rotated([(cx+rx*math.cos(t*TAU/240),cy+ry*math.sin(t*TAU/240)) for t in range(241)]))
        for i in range(1,p['parallels']+1):
            v=-1+2*i/(p['parallels']+1); ex=rx*math.sqrt(1-v*v)
            poly(rotated([(cx-ex,cy+ry*v),(cx+ex,cy+ry*v)]))
    elif kind == 'square':
        s=p['spacing']
        if (width/s+1)*(height/s+1)>50000:
            raise ValueError('网格过密，请增大边长或缩小画布')
        for x in range(math.ceil(width/s)+1):
            poly([(x*s,0),(x*s,height)])
        for y in range(math.ceil(height/s)+1):
            poly([(0,y*s),(width,y*s)])
        for row in range(math.ceil(height/s)+1):
            for col in range(math.ceil(width/s)+1):
                x,y=col*s,row*s
                for diag in range(p['diagonals']):
                    a,b=((x,y),(x+s,y+s)) if diag==0 else ((x+s,y),(x,y+s))
                    for lo,hi in ((p['trim_corner']/100,.5-p['trim_center']/100),(.5+p['trim_center']/100,1-p['trim_corner']/100)):
                        if hi>lo: poly([(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t) for t in (lo,hi)],ink=p['diag_color'],line=p['diag_width'])
                r=p['node_size']/2
                if p['node']=='plus':
                    poly([(x-r,y),(x+r,y)],ink=p['node_color'],line=p['node_width'])
                    poly([(x,y-r),(x,y+r)],ink=p['node_color'],line=p['node_width'])
                elif p['node']=='cross':
                    poly([(x-r,y-r),(x+r,y+r)],ink=p['node_color'],line=p['node_width'])
                    poly([(x-r,y+r),(x+r,y-r)],ink=p['node_color'],line=p['node_width'])
                if p['corner']!='none':
                    for dx,dy in ((1,1),(1,-1),(-1,1),(-1,-1)):
                        shape(x+dx*p['corner_gap'],y+dy*p['corner_gap'],p['corner_size'],p['corner'],line=1)
    elif kind == 'rays':
        a=0; i=0
        while a<360 and i<720:
            span=rng.uniform(min(p['min_angle'],p['max_angle']),max(p['min_angle'],p['max_angle'])) if p['mode']=='random' else 360/p['count']
            span=min(span,360-a)
            start=angle+a; end=start+max(.01,span-min(p['gap'],span*.95))
            outer=math.hypot(width,height) if p['fill_canvas'] else max(p['inner'],p['radius'])
            if p['random_length'] and not p['fill_canvas']: outer=p['inner']+(outer-p['inner'])*rng.uniform(p['min_length']/100,1)
            if p['mode']=='width':
                pts=[polar(cx,cy,p['inner'],start),polar(cx,cy,outer,start)]
                if p['end']=='pointed':
                    x,y=pts[0]; a1=math.radians(start+90)
                    pts=[(x+stroke/2*math.cos(a1),y+stroke/2*math.sin(a1)),pts[1],(x-stroke/2*math.cos(a1),y-stroke/2*math.sin(a1))]
                    poly(pts,True,True,key=str(i),line=0)
                else:
                    poly(pts,key=str(i))
                    if p['end']=='round' and str(i) not in hidden:
                        ellipse(*pts[-1],stroke/2,fill=True,line=0)
            else:
                steps=max(2,math.ceil(end-start))
                if p['end']=='pointed':
                    pts=[polar(cx,cy,p['inner'],start),polar(cx,cy,outer,(start+end)/2),polar(cx,cy,p['inner'],end)]
                else:
                    pts=[polar(cx,cy,outer,start+(end-start)*j/steps) for j in range(steps+1)]
                    pts += [polar(cx,cy,p['inner'],end-(end-start)*j/steps) for j in range(steps+1)]
                poly(pts,True,True,key=str(i),line=0)
                if p['end']=='round' and str(i) not in hidden:
                    mid=(start+end)/2
                    cap_radius=min((outer-p['inner'])/2,outer*math.sin(math.radians((end-start)/2)))
                    ellipse(*polar(cx,cy,outer-cap_radius,mid),max(.1,cap_radius),fill=True,line=0)
                if p['symmetry']!='none':
                    poly([(width-x,y) if p['symmetry']=='lr' else (x,height-y) for x,y in pts],True,True,key=str(i),line=0)
            a+=span; i+=1
    elif kind == 'symbols':
        size=p['size']; gap=p['spacing']; n=p['repeat']; shape_name=p['shape']
        for i in range(n):
            x=cx-(n*size+(n-1)*gap)/2+i*(size+gap); y=cy-size/2
            thick=rng.uniform(min(p['min_width'],p['max_width']),max(p['min_width'],p['max_width'])) if p['random_width'] else p['thickness']
            thick=min(size*.45,thick)
            if shape_name=='arrow': pts=[(0,size/2-thick/2),(size*.55,size/2-thick/2),(size*.55,0),(size,size/2),(size*.55,size),(size*.55,size/2+thick/2),(0,size/2+thick/2)]
            elif shape_name=='slant': pts=[(size*.35,0),(size*.35+thick,0),(thick,size),(0,size)]
            elif shape_name=='chevron': pts=[(0,0),(thick,0),(size*.6,size/2),(thick,size),(0,size),(size*.6-thick,size/2)]
            elif shape_name=='bracket': pts=[(size*.5,0),(0,0),(0,size),(size*.5,size),(size*.5,size-thick),(thick,size-thick),(thick,thick),(size*.5,thick)]
            elif shape_name=='cross':
                lo,hi=(size-thick)/2,(size+thick)/2
                pts=[(lo,0),(hi,0),(hi,lo),(size,lo),(size,hi),(hi,hi),(hi,size),(lo,size),(lo,hi),(0,hi),(0,lo),(lo,lo)]
            else:
                cut=min(size/2,p['corner']); pts=[(cut,0),(size,0),(size,size-cut),(size-cut,size),(0,size),(0,cut)]
            positions=[(cx,cy,angle)] if p['layout']=='single' else [(cx,cy,angle+j*90) for j in range(4)]
            for _,__,a in positions:
                a=math.radians(a); offset=0 if p['layout']=='single' else size*.6
                local=pts
                if p['layout']=='focus': local=[(size-px,size-py) for px,py in pts]
                if p['layout']=='cycle': local=[(size-py,px) for px,py in pts]
                pp=[(x+px+offset,y+py) for px,py in local]
                pp=[(cx+(px-cx)*math.cos(a)-(py-cy)*math.sin(a),cy+(px-cx)*math.sin(a)+(py-cy)*math.cos(a)) for px,py in pp]
                out.append(f'<polygon points="{points_text(pp)}" {paint(color,"fill")} {paint(p["stroke_color"])} stroke-width="{fmt(stroke)}" stroke-linejoin="round"/>')
                if shape_name=='bracket' and p['symmetric']:
                    out.append(f'<polygon points="{points_text([(width-px,py) for px,py in pp])}" {paint(color,"fill")}/>')
    elif kind == 'barcode':
        # Code 128-B, including mandatory weighted checksum and quiet zones.
        codes=[104]
        for ch in p['text']:
            if not 32<=ord(ch)<=126: raise ValueError('条形码内容仅支持 ASCII 可打印字符')
            codes.append(ord(ch)-32)
        if len(codes)>257: raise ValueError('条形码内容最多 256 个字符')
        codes += [(104+sum(i*c for i,c in enumerate(codes[1:],1)))%103,106]
        modules=[int(v) for c in codes for v in CODE128[c]]
        scale=width/(sum(modules)+20); x=10*scale
        for i,m in enumerate(modules):
            if i%2==0:
                out.append(f'<rect x="{fmt(x)}" y="{fmt(height*.08)}" width="{fmt(m*scale)}" height="{fmt(height*(.68 if p["show_text"] else .84))}" {paint(color,"fill")}/>')
            x+=m*scale
        if p['show_text']:
            out.append(f'<text x="{fmt(cx)}" y="{fmt(height*.9)}" text-anchor="middle" font-family="monospace" font-size="{fmt(min(height*.1,width/max(1,len(p["text"]))*1.3))}" {paint(color,"fill")}>{html.escape(p["text"])}</text>')
    elif kind == 'contour':
        step=max(p['step'],math.ceil(max(width,height)/180))
        nx,ny=math.ceil(width/step)+1,math.ceil(height/step)+1
        peaks=[(rng.uniform(0,width),rng.uniform(0,height),rng.uniform(.5,1.5)) for _ in range(p['peaks'])]
        phases=[rng.uniform(0,TAU) for _ in range(p['octaves']*2)]
        sigma=max(width,height)/p['terrain_scale']/3
        def terrain(x,y):
            value=sum(a*math.exp(-((x-px)**2+(y-py)**2)/(2*sigma*sigma)) for px,py,a in peaks)
            for o in range(p['octaves']):
                freq=2**o/sigma
                value+=p['roughness']**(o+1)*math.sin(x*freq+phases[o*2])*math.cos(y*freq+phases[o*2+1])
            return value
        grid=[[terrain(x*step,y*step) for x in range(nx)] for y in range(ny)]
        low=min(map(min,grid)); high=max(map(max,grid))
        levels=[low+(high-low)*i/(p['count']+1) for i in range(p['count']+2)]
        def clipped(vertices, threshold, above):
            result=[]
            for a,b in zip(vertices,vertices[1:]+vertices[:1]):
                ina=(a[2]>=threshold) if above else (a[2]<=threshold)
                inb=(b[2]>=threshold) if above else (b[2]<=threshold)
                if ina: result.append(a)
                if ina!=inb:
                    t=(threshold-a[2])/(b[2]-a[2])
                    result.append((a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,threshold))
            return result
        # Clip triangles against each scalar interval to fill genuine terrain bands.
        for level in range(1,p['count']+1):
            style=p | styles.get(str(level),{})
            if str(level) in hidden or style['fill_type']=='none': continue
            z0,z1=levels[level],levels[level+1]
            ink=style['fill_color']
            if style['fill_type']=='solid':
                for y in range(ny-1):
                    for x in range(nx-1):
                        vertices=[(x*step,y*step,grid[y][x]),((x+1)*step,y*step,grid[y][x+1]),((x+1)*step,(y+1)*step,grid[y+1][x+1]),(x*step,(y+1)*step,grid[y+1][x])]
                        for indices in ((0,1,2),(0,2,3)):
                            band=clipped(clipped([vertices[j] for j in indices],z0,True),z1,False)
                            if len(band)>2: poly([(a,b) for a,b,_ in band],True,True,ink=ink,line=0)
            else:
                spacing=style['fill_spacing']
                for y in range(0,height,max(1,round(spacing))):
                    for x in range(0,width,max(1,round(spacing))):
                        if not z0<=terrain(x,y)<z1: continue
                        if style['fill_type']=='dots': ellipse(x,y,style['fill_size'],fill=True,ink=ink,line=0)
                        else:
                            a=math.radians(style['fill_angle'])
                            pts=[]
                            for j in range(-4,5):
                                px=x+j*spacing/8*math.cos(a);py=y+j*spacing/8*math.sin(a)
                                if z0<=terrain(px,py)<z1: pts.append((px,py))
                                elif len(pts)>1: poly(pts,ink=ink,line=style['fill_size']);pts=[]
                            if len(pts)>1: poly(pts,ink=ink,line=style['fill_size'])
        for level in range(1,p['count']+1):
            z=low+(high-low)*level/(p['count']+1)
            for y in range(ny-1):
                for x in range(nx-1):
                    coords=[(x*step,y*step),((x+1)*step,y*step),((x+1)*step,(y+1)*step),(x*step,(y+1)*step)]
                    values=[grid[y][x],grid[y][x+1],grid[y+1][x+1],grid[y+1][x]]
                    edges=[]
                    for j in range(4):
                        k=(j+1)%4
                        if (values[j]>=z)!=(values[k]>=z):
                            t=(z-values[j])/(values[k]-values[j])
                            edges.append((coords[j][0]+(coords[k][0]-coords[j][0])*t,coords[j][1]+(coords[k][1]-coords[j][1])*t))
                    for i in range(0,len(edges)-1,2): poly(edges[i:i+2],key=str(level))
    else:
        raise ValueError('未知图形类型')
    bg='' if background is None else f'<rect width="100%" height="100%" {paint(background,"fill")}/>'
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}">{bg}{"".join(out)}</svg>'
    return Document(svg,width,height,hits)

# ISO/IEC 15417 symbol widths, indexed by Code 128 symbol value.
CODE128 = ('212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 122132 122231 113222 123122 123221 223211 221132 221231 213212 223112 312131 311222 321122 321221 312212 322112 322211 212123 212321 232121 111323 131123 131321 112313 132113 132311 211313 231113 231311 112133 112331 132131 113123 113321 133121 313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111 314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 112412 122114 122411 142112 142211 241211 221114 413111 241112 134111 111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 214121 412121 111143 111341 131141 114113 114311 411113 411311 113141 114131 311141 411131 211412 211214 211232 2331112').split()

def rasterize(document, scale=1):
    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    renderer=QSvgRenderer(QByteArray(document.svg.encode('utf-8')))
    if not renderer.isValid(): raise ValueError('SVG 渲染失败')
    width,height=round(document.width*scale),round(document.height*scale)
    if width*height>67_108_864: raise ValueError('导出最大支持 6,700 万像素')
    image=QImage(width,height,QImage.Format_ARGB32_Premultiplied)
    if image.isNull(): raise ValueError('图片过大，内存不足')
    image.fill(0)
    painter=QPainter(image)
    renderer.render(painter)
    painter.end()
    return image
