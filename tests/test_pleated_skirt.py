import os
from pathlib import Path
import sys
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch
import xml.etree.ElementTree as ET
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QByteArray,QSettings,QRectF,Qt
from PySide6.QtGui import QImage,QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication
from app import config
from app.tools.pleated_skirt import Band,PlaidParams,render_svg,from_dict,to_dict
from app.tools.pleated_skirt.widget import PleatedSkirtTool,PleatPreview
from app.tools.pleated_skirt.presets import PRESETS,PRESET_BY_KEY


def raster(p,stage='color',tile=False):
    svg=render_svg(p,stage,tile);root=ET.fromstring(svg)
    image=QImage(int(root.attrib['width']),int(root.attrib['height']),QImage.Format_ARGB32)
    image.fill(0);painter=QPainter(image)
    renderer=QSvgRenderer(QByteArray(svg.encode()));renderer.render(painter);painter.end()
    return image


class PlaidTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_all_presets_render_and_apply_without_mutating_saved_reference(self):
        self.assertEqual(len(PRESETS),9)
        self.assertEqual(len(PRESET_BY_KEY),9)
        with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as folder:
            settings=QSettings(str(Path(folder)/'settings.ini'),QSettings.IniFormat)
            with patch.object(config,'settings',return_value=settings):
                widget=PleatedSkirtTool()
                original=widget.params()
                widget.preset_combo.setCurrentIndex(widget.preset_combo.findData('gingham_blue'))
                self.assertEqual(widget.params(),original)
                for preset in PRESETS:
                    with self.subTest(preset=preset.key):
                        widget.preset_combo.setCurrentIndex(widget.preset_combo.findData(preset.key))
                        widget.apply_preset()
                        self.assertEqual(widget.params(),preset.params)
                        self.assertTrue(widget.preview.renderer.isValid())
                        image=raster(preset.params,tile=True)
                        self.assertFalse(image.isNull())
                        self.assertEqual(image.pixelColor(0,0).alpha(),255)
                        self.assertEqual(from_dict(to_dict(preset.params)),preset.params)
                widget.controls['over'].setValue(7)
                widget.reset()
                self.assertEqual(widget.params(),PRESET_BY_KEY['reference'].params)
                widget.timer.stop();widget.close()

    def test_cached_preview_matches_export_and_does_not_rerender_on_zoom(self):
        p=PlaidParams(warp=(Band('#ff0000',3),Band('#0000ff',2)),weft=(Band('#00ff00',3),),thread_size=2,repeats_x=2,repeats_y=2)
        tw,th=p.dimensions()
        preview=PleatPreview();svg=render_svg(p,tile=True)
        preview.show_svg(svg,tw*2,th*2)
        cached=preview._tile.cacheKey()
        image=QImage(tw*2,th*2,QImage.Format_ARGB32);image.fill(0)
        painter=QPainter(image)
        preview.scene().render(painter,QRectF(0,0,image.width(),image.height()),preview.sceneRect(),Qt.IgnoreAspectRatio);painter.end()
        self.assertEqual(image,raster(p))
        with patch.object(QSvgRenderer,'render',side_effect=AssertionError('Zoom must reuse the tile')):
            preview.show_svg(svg,tw*4,th*4)
            for zoom in (.5,1,2,8):
                image=QImage(120,80,QImage.Format_ARGB32);image.fill(0);painter=QPainter(image)
                preview.scene().render(painter,QRectF(0,0,120,80),QRectF(3,5,120/zoom,80/zoom),Qt.IgnoreAspectRatio);painter.end()
            self.assertEqual(preview._tile.cacheKey(),cached)
        preview.show_svg(render_svg(p,'structure',True),tw,th)
        self.assertNotEqual(preview._tile.cacheKey(),cached)
        preview.close()

    def test_mask_and_colors_follow_same_interlacing(self):
        p=PlaidParams(warp=(Band('#ff0000',3),Band('#0000ff',2)),weft=(Band('#00ff00',2),Band('#ffff00',1)),thread_size=3)
        for reverse in (False,True):
            p=replace(p,reverse=reverse)
            structure=raster(p,'structure');color=raster(p)
            w,h=p.dimensions();self.assertEqual((w,h),(60,36))
            for y in range(h//3):
                for x in range(w//3):
                    warp_top=(x+(-y if reverse else y))%4<2
                    self.assertEqual(structure.pixelColor(x*3+1,y*3+1).name(),'#000000' if warp_top else '#ffffff')
                    expected=('#ff0000' if x%5<3 else '#0000ff') if warp_top else ('#00ff00' if y%3<2 else '#ffff00')
                    self.assertEqual(color.pixelColor(x*3+1,y*3+1).name(),expected)

    def test_tiling_exactly_repeats_and_svg_is_vector(self):
        p=PlaidParams(warp=(Band('#123456',3),),weft=(Band('#abcdef',5),),thread_size=2,repeats_x=2,repeats_y=2)
        tw,th=p.dimensions();tile=raster(p,tile=True);image=raster(p)
        for row in range(2):
            for col in range(2):self.assertEqual(image.copy(col*tw,row*th,tw,th),tile)
        self.assertNotIn('<image',render_svg(p))
        self.assertEqual(from_dict(to_dict(p)),p)
        with self.assertRaises(ValueError):render_svg(replace(p,warp=(Band('invalid',3),)))
        with self.assertRaises(ValueError):render_svg(replace(p,over=0))
        with self.assertRaises(ValueError):render_svg(replace(p,warp=(Band('#ffffff',512),),thread_size=16,repeats_x=2))

    def test_ui_rules_presets_stage_exports_and_reload(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'artifacts') as folder:
            settings=QSettings(str(Path(folder)/'settings.ini'),QSettings.IniFormat)
            with patch.object(config,'settings',return_value=settings):
                widget=PleatedSkirtTool();widget.resize(1200,860);widget.show()
                self.assertTrue(widget.preview.renderer.isValid())
                widget.warp.set_bands((Band('#ff0000',4),Band('#ffffff',4)))
                widget.refresh();self.assertEqual(widget.params().warp,widget.params().weft)
                widget.linked.setChecked(False)
                widget.weft.set_bands((Band('#0000ff',8),));widget.refresh()
                self.assertNotEqual(widget.params().warp,widget.params().weft)
                for stage in (0,1):
                    widget.stage.setCurrentIndex(stage);widget.refresh()
                    for extension in ('png','svg'):
                        path=Path(folder)/f'result-{stage}.{extension}';widget.save_image(path,extension)
                        if extension=='svg':self.assertEqual(path.read_text(encoding='utf-8'),render_svg(widget.params(),widget.stage.currentData()))
                        else:self.assertEqual(QImage(str(path)).convertToFormat(QImage.Format_RGBA8888),raster(widget.params(),widget.stage.currentData()).convertToFormat(QImage.Format_RGBA8888))
                again=PleatedSkirtTool();self.assertEqual(again.params(),widget.params())
                again.warp.table.selectRow(0);again.warp.move(1)
                self.assertEqual(again.params().warp[0].color,'#ffffff')
                again.reset();self.assertEqual(again.params(),PlaidParams())
                for w in (widget,again):w.timer.stop();w.close()

if __name__=='__main__':unittest.main()
