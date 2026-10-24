"""Editable style presets, with references; not registered tartan thread counts."""
from dataclasses import dataclass
from . import Band, PlaidParams, REFERENCE_PRESET, REFERENCE_PRESET_NAME


@dataclass(frozen=True)
class Preset:
    key: str
    name: str
    description: str
    params: PlaidParams
    source: str = ''


def cloth(bands, *, over=2, under=2, repeat=2, size=2):
    sequence=tuple(Band(color,count) for color,count in bands)
    return PlaidParams(warp=sequence,weft=sequence,over=over,under=under,
                       thread_size=size,repeats_x=repeat,repeats_y=repeat)


CHECKS='https://theplaidstudio.com/blog/gingham-vs-tartan-vs-plaid.html'
HOUNDSTOOTH='https://en.wikipedia.org/wiki/Houndstooth'
GLEN='https://en.wikipedia.org/wiki/Glen_plaid'
WHITE='#f5f2e9'
BLACK='#24252b'
PRESETS=(
    Preset('reference',REFERENCE_PRESET_NAME,'之前截图的奶油黄、金棕、深棕与蓝色格纹。',REFERENCE_PRESET),
    Preset('royal_red','经典红色苏格兰格（风格参考）','红底搭配深蓝、绿、黄白细线；线数为近似设计，可继续调整。',
        cloth([('#b62532',48),(BLACK,4),('#243b66',12),(BLACK,4),('#e6c950',4),(BLACK,4),('#285642',20),(WHITE,4),('#285642',20),(BLACK,4),('#e6c950',4),(BLACK,4),('#243b66',12),(BLACK,4)]),
        'https://www.kinlochanderson.com/tartan/stewart-royal'),
    Preset('black_watch','墨绿藏蓝格（Black Watch 风格）','深绿、藏蓝和黑色宽窄交替，低明度学院风。',
        cloth([('#1c493e',32),(BLACK,4),('#22354c',16),(BLACK,4),('#1c493e',8),(BLACK,4),('#22354c',28),(BLACK,4),('#1c493e',8),(BLACK,4),('#22354c',16),(BLACK,4)]),
        'https://www.tartanregister.gov.uk/qResults?searchString=black+watch'),
    Preset('buffalo','红黑大格（Buffalo Check）','等宽红黑色带，较大的方格。',
        cloth([('#bb3039',32),('#24232a',32)],repeat=3),
        'https://www.woolrich.com/gb/en/the-birth-of-an-icon.html'),
    Preset('gingham_blue','蓝白小格（Gingham）','蓝白等宽色带，1 上 / 1 下平纹交织。',
        cloth([('#5f8fbd',16),(WHITE,16)],over=1,under=1,repeat=4),CHECKS),
    Preset('gingham_pink','粉白小格（Gingham）','柔粉与暖白的小方格，平纹交织。',
        cloth([('#d995a8',16),(WHITE,16)],over=1,under=1,repeat=4),CHECKS),
    Preset('houndstooth','黑白千鸟格（Houndstooth）','黑白各 4 根线，2 上 / 2 下交织形成断裂尖角格。',
        cloth([(BLACK,4),(WHITE,4)],repeat=8,size=4),HOUNDSTOOTH),
    Preset('glen','灰白复合格（Glen Check 风格）','细格与大格分区交替，形成灰白复合格纹。',
        cloth([(BLACK,4),(WHITE,4)]*4+[(BLACK,16),(WHITE,16)]*2,repeat=2),GLEN),
    Preset('windowpane','藏蓝窗格（Windowpane）','大面积藏蓝底配浅灰细线，疏朗的窗框格。',
        cloth([('#27384f',92),('#c7cbd0',4)],over=1,under=1,repeat=2),CHECKS),
)
PRESET_BY_KEY={preset.key:preset for preset in PRESETS}
