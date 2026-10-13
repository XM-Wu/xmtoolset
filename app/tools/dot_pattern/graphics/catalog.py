"""Generator controls: key, label, default, minimum/choices, maximum."""

def num(key, label, default, low, high):
    return (key, label, default, low, high)

def choice(key, label, default, options):
    return (key, label, default, options, None)

def flag(key, label, default=False):
    return (key, label, default, None, None)

def color(key, label, default='#89b4fa'):
    return (key, label, default, 'color', None)

ANGLE = num('angle', '旋转角度', 0, -360, 360)
WIDTH = num('stroke', '线条粗细', 2.0, 0.1, 80)
SPACING = num('spacing', '间距', 32.0, 4, 512)
RADIUS = num('radius', '半径', 180.0, 1, 3000)
COUNT = num('count', '数量', 20, 1, 360)
SEED = num('seed', '随机种子', 1, 0, 999999)
INK = color('color', '图形颜色')
CAP = choice('cap', '端点样式', 'butt', [('平头', 'butt'), ('圆头', 'round')])
DASH = num('dash', '虚线长度（0 为实线）', 0.0, 0, 100)
GAP = num('dash_gap', '虚线间隔', 8.0, 0.1, 100)
SHAPE = choice('shape', '点形状', 'circle', [('圆形', 'circle'), ('方形', 'square'), ('菱形', 'diamond'), ('三角形', 'triangle'), ('六边形', 'hexagon')])

CATALOG = {
    'concentric': ('同心圆', [COUNT, num('inner', '内半径', 25.0, 0, 3000), RADIUS,
        num('inner_stroke', '最内圈粗细', 8.0, 0.1, 80), WIDTH,
        num('sweep', '绘制角度', 360.0, 1, 360), ANGLE, DASH, GAP, CAP, INK]),
    'halftone': ('半调波点', [SPACING, num('size', '最大直径', 28.0, 1, 512), num('min_size', '最小直径', 2.0, 0, 512),
        SHAPE, choice('arrangement', '排列', 'grid', [('标准网格', 'grid'), ('蜂窝交错', 'hex')]),
        choice('gradient', '渐变类型', 'linear', [('单向渐变', 'linear'), ('中心放射', 'radial')]),
        choice('ease', '渐变规律', 'linear', [('线性', 'linear'), ('指数', 'exp'), ('正弦', 'sin')]), ANGLE,
        flag('invert', '反转渐变'), choice('mask', '整体形状', 'full', [('全画布','full'),('圆形','circle'),('圆角矩形','rect'),('六边形','hexagon'),('图片轮廓','image')]),
        num('mask_width', '轮廓宽度', 400.0, 1, 8192), num('mask_height', '轮廓高度', 400.0, 1, 8192),
        num('corner', '轮廓圆角', 24.0, 0, 2000), flag('edge_zero', '边缘点归零'),
        ('shape_file', '自定义形状 PNG / SVG', '', 'file', None), ('mask_file', '轮廓图片', '', 'file', None), INK]),
    'hud': ('HUD 线条', [RADIUS, num('sweep', '弧度跨度', 270.0, 1, 360), ANGLE,
        num('notch_angle', '台阶位置（度）', 120.0, 0, 360), num('notch_arc', '台阶弧度', 35.0, 0, 180),
        num('depth', '台阶深度', 25.0, -200, 200), num('chamfer', '斜角过渡（度）', 6.0, 0, 45),
        choice('end', '两端样式', 'tick', [('无','none'),('斜向出角线','tick'),('垂直卡槽线','perp'),('圆点','dot')]),
        num('cap_length', '端点长度', 14.0, 0, 200), num('cap_angle', '出角倾斜角度', 45.0, -180, 180), WIDTH, DASH, GAP, INK]),
    'scale': ('刻度圆', [num('count', '线段数量', 180, 1, 720), RADIUS, num('length', '线段长度', 20.0, 1, 1000),
        choice('alignment', '对齐基准', 'center', [('居中','center'),('向内','inner'),('向外','outer')]),
        num('sweep', '圆弧跨度', 360.0, 1, 360), ANGLE, WIDTH, CAP, DASH, GAP,
        num('major', '主刻度间隔', 10, 1, 100), num('major_scale', '主刻度倍率', 1.8, 1, 8),
        num('frequency', '波浪频次', 0.0, 0, 40), num('amplitude', '波浪振幅', 0.0, 0, 200),
        num('jitter', '随机长度噪波', 0.0, 0, 100), SEED, INK]),
    'barcode': ('条形码', [('text', '内容（ASCII）', 'XM GRAPHICS 2026', 'text', None), flag('show_text', '显示文字', True), INK]),
    'wave': ('波浪纹理', [ANGLE, SPACING, num('amplitude', '波浪幅度', 24.0, 0, 300),
        num('frequency', '波浪频率', 0.02, 0.002, 0.2), WIDTH, INK]),
    'lines': ('重复线条', [choice('direction', '线条方向', 'diagonal', [('横线','horizontal'),('竖线','vertical'),('斜线','diagonal'),('点阵斜线','dots')]), SPACING, WIDTH, INK]),
    'matrix': ('点阵', [SHAPE, num('size', '点大小', 10.0, 1, 512), SPACING, flag('diagonal', '45° 斜向排列'),
        flag('finite', '有限点阵'), num('rows', '行数', 12, 1, 100), num('columns', '列数', 12, 1, 100), INK]),
    'polygon': ('多边形网格', [choice('shape','单元形状','hexagon',[('六边形','hexagon'),('三角形','triangle')]),
        num('side', '边长', 36.0, 8, 512), num('cell_scale','图形大小（%）',90.0,1,150), flag('fill', '填充单元', True),
        flag('grid', '显示网格线', True), color('grid_color', '网格线颜色', '#45475a'), num('stroke','描边宽度',1.0,0,30), INK]),
    'contour': ('等高线', [num('peaks','山峰数量',4,1,16), num('terrain_scale','地形缩放',1.0,0.2,5),
        num('step','采样步长',8,4,32), num('count','等高线层数',14,2,40), num('octaves','倍频复杂度',3,1,6),
        num('roughness','细节粗糙度',0.45,0,0.9), WIDTH, DASH, GAP, SEED, INK,
        choice('fill_type','带状区间填充','none',[('无','none'),('纯色','solid'),('波点','dots'),('斜线','hatch')]),
        color('fill_color','填充颜色','#806366f1'), num('fill_spacing','填充间距',14.0,4,100),
        num('fill_size','波点半径 / 线宽',2.0,0.5,20), num('fill_angle','斜线角度',45.0,-90,90)]),
    'symbols': ('常见图形', [choice('shape','图形','arrow',[('箭头','arrow'),('斜线块','slant'),('折线箭头','chevron'),('括号','bracket'),('十字','cross'),('切角方形','cut')]),
        num('size','尺寸',100.0,8,1000), num('thickness','粗细',18.0,1,200), num('corner','圆角 / 切角',8.0,0,200),
        choice('layout','布局','single',[('默认','single'),('发散','diverge'),('聚焦','focus'),('循环','cycle')]),
        num('repeat','水平重复次数',1,1,40), num('spacing','水平间距',20.0,0,500), ANGLE,
        flag('random_width','随机粗细'), num('min_width','随机下限',8.0,1,200), num('max_width','随机上限',30.0,1,200), SEED,
        flag('symmetric','对称括号'), num('stroke','描边宽度',0.0,0,40), color('stroke_color','描边颜色','#1e1e2e'), INK]),
    'nested': ('嵌套多边形', [num('sides','边数',6,3,12), RADIUS, num('step','半径步差',12.0,1,500),
        num('count','嵌套圈数',12,1,100), num('rotation_step','旋转角度步差',5.0,-180,180), ANGLE, WIDTH,
        flag('gradient','渐变描边'), INK, color('end_color','渐变终点','#f5c2e7')]),
    'globe': ('经纬球', [num('axis_w','水平直径',360.0,20,6000), num('axis_h','垂直直径',360.0,20,6000),
        num('meridians','经线数量',10,0,40), num('parallels','纬线数量',8,0,40), ANGLE, WIDTH, INK]),
    'square': ('方形网格', [num('spacing','边长',64.0,8,512), WIDTH, INK,
        num('diagonals','对角线数量',0,0,2), num('diag_width','对角线粗细',1.0,0.1,40), color('diag_color','对角线颜色','#a6adc8'),
        num('trim_corner','四角截断（%）',0.0,0,49), num('trim_center','中心截断（%）',0.0,0,49),
        choice('node','衔接点装饰','none',[('无','none'),('×','cross'),('十字','plus')]),
        num('node_size','装饰长度',12.0,1,100), num('node_width','装饰粗细',2.0,0.1,40), color('node_color','装饰颜色','#f5c2e7'),
        choice('corner','四角装饰','none',[('无','none'),('三角形','triangle'),('方形','square'),('圆形','circle'),('圆环','ring')]),
        num('corner_size','四角大小',6.0,1,100), num('corner_gap','边框距离',8.0,0,100)]),
    'rays': ('射线', [choice('mode','射线模式','arc',[('固定粗细','width'),('固定角度','arc'),('随机角度','random')]),
        num('count','射线数量',32,1,120), num('inner','内半径',35.0,0,3000), RADIUS, flag('fill_canvas','铺满画布',True),
        WIDTH, num('gap','间隔角度',4.0,0,90), flag('random_length','随机长度'),
        num('min_length','最短长度（%）',40.0,0,100), num('min_angle','扇形角度下限',2.0,0.5,90),
        num('max_angle','扇形角度上限',20.0,0.5,180),
        choice('symmetry','随机对称','none',[('无','none'),('左右','lr'),('上下','tb')]),
        choice('end','射线末端','flat',[('平','flat'),('圆','round'),('尖','pointed')]), ANGLE, SEED, INK]),
}

TILE_KINDS = {'lines', 'matrix', 'square', 'polygon', 'symbols'}
EDIT_KINDS = {'matrix', 'polygon', 'rays', 'contour', 'halftone'}

def defaults(kind):
    return {field[0]: field[2] for field in CATALOG[kind][1]}
