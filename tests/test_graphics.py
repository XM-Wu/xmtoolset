"""End-to-end SVG/PNG parity and workbench regression tests."""
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from app import product
product.select('dot-pattern','图形生成工具','0.2.0','dot-pattern.py','dot_pattern')
from app import config
from app.tools.dot_pattern.graphics.catalog import CATALOG, defaults
from app.tools.dot_pattern.graphics.render import render, rasterize, CODE128

class GraphicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_every_generator_exports_valid_nonempty_svg_and_png(self):
        for kind in CATALOG:
            with self.subTest(kind=kind):
                document=render(kind,{},512,384)
                root=ET.fromstring(document.svg)
                self.assertEqual(root.attrib['viewBox'],'0 0 512 384')
                image=rasterize(document)
                self.assertEqual((image.width(),image.height()),(512,384))
                self.assertTrue(any(image.pixelColor(x,y).alpha() for y in range(0,384,3) for x in range(0,512,3)))

    def test_random_scenes_are_stable_and_seed_changes_geometry(self):
        for kind,values in [('contour',{}),('rays',{'mode':'random'}),('scale',{'jitter':20})]:
            with self.subTest(kind=kind):
                a=render(kind,values)
                self.assertEqual(a.svg,render(kind,values).svg)
                self.assertNotEqual(a.svg,render(kind,values|{'seed':23}).svg)

    def test_edit_hidden_element_stays_hittable_for_restore(self):
        first=render('matrix',{'finite':True,'rows':1,'columns':1})
        self.assertEqual(first.hit(256,256),'0:0')
        removed=render('matrix',{'finite':True,'rows':1,'columns':1},hidden=['0:0'])
        self.assertNotEqual(first.svg,removed.svg)
        self.assertEqual(removed.hit(256,256),'0:0')
        self.assertEqual(rasterize(removed).pixelColor(256,256).alpha(),0)

    def test_background_and_barcode_text_escape(self):
        doc=render('barcode',{'text':'A<&"B'},background='#80ffffff')
        ET.fromstring(doc.svg)
        self.assertIn('A&lt;&amp;&quot;B',doc.svg)
        self.assertLessEqual(abs(rasterize(doc).pixelColor(0,0).alpha()-128),1)
        self.assertEqual(len(CODE128),107)
        self.assertTrue(all(sum(map(int,s))==11 for s in CODE128[:106]))
        self.assertEqual(sum(map(int,CODE128[106])),13)
        with self.assertRaises(ValueError): render('barcode',{'text':'中文'})

    def test_shapes_and_alternative_modes_render(self):
        cases=[('halftone',{'mask':m}) for m in ('circle','rect','hexagon')]
        cases += [('halftone',{'shape':s,'arrangement':'hex','ease':'sin'}) for s in ('square','triangle','diamond','hexagon')]
        cases += [('symbols',{'shape':s}) for s in ('arrow','slant','chevron','bracket','cross','cut')]
        cases += [('rays',{'mode':m,'end':e}) for m in ('width','arc','random') for e in ('flat','round','pointed')]
        cases += [('polygon',{'shape':'triangle'}),('globe',{'angle':45}),('square',{'diagonals':2,'node':'cross','corner':'ring'})]
        cases += [('contour',{'fill_type':s}) for s in ('solid','dots','hatch')]
        for kind,p in cases:
            with self.subTest(kind=kind,p=p):
                image=rasterize(render(kind,p))
                self.assertFalse(image.isNull())

    def test_custom_shape_and_image_mask_are_embedded(self):
        from PIL import Image
        path=Path(__file__).resolve().parents[1]/'artifacts'/'graphics-test-shape.png'
        Image.new('RGBA',(20,20),(255,100,0,255)).save(path)
        try:
            doc=render('halftone',{'shape_file':str(path),'mask':'image','mask_file':str(path)})
            self.assertIn('data:image/png;base64,',doc.svg)
            self.assertNotIn(str(path),doc.svg)
            self.assertFalse(rasterize(doc).isNull())
        finally: path.unlink(missing_ok=True)

    def test_contour_individual_fill_and_dense_scene_guard(self):
        original=render('contour',{})
        edited=render('contour',{},styles={'5':{'fill_type':'solid','fill_color':'#80ff0000'}})
        self.assertNotEqual(original.svg,edited.svg)
        with self.assertRaises(ValueError): render('square',{'spacing':8},8192,8192)

    def test_workbench_switch_persist_reset_undo(self):
        from app.tools.dot_pattern.widget import DotPatternTool
        path=Path(__file__).resolve().parents[1]/'artifacts'/'graphics-test-settings.ini'
        settings=QSettings(str(path),QSettings.IniFormat);settings.clear()
        with patch.object(config,'settings',return_value=settings):
            widget=DotPatternTool();widget.resize(1060,740);widget.show()
            for kind in CATALOG:
                widget.mode.setCurrentIndex(widget.mode.findData(kind))
                self.app.processEvents()
                self.assertIsNotNone(widget.document,widget.status.text())
            widget.mode.setCurrentIndex(widget.mode.findData('matrix'))
            widget.controls['finite'].setChecked(True)
            widget.controls['rows'].setValue(1);widget.controls['columns'].setValue(1)
            widget.refresh();widget.pick(256,256,False);widget.refresh()
            self.assertIn('0:0',widget.hidden)
            widget.undo();self.assertFalse(widget.hidden)
            widget.controls['size'].setValue(19)
            widget.mode.setCurrentIndex(widget.mode.findData('globe'))
            widget.mode.setCurrentIndex(widget.mode.findData('matrix'))
            self.assertEqual(widget.values()['size'],19)
            widget.close();widget.timer.stop()
            again=DotPatternTool()
            self.assertEqual(again.kind,'matrix')
            self.assertEqual(again.values()['size'],19)
            again.reset();self.assertEqual(again.values()['size'],defaults('matrix')['size'])
            again.timer.stop();again.close()
        settings.clear();settings.sync();path.unlink(missing_ok=True)

if __name__=='__main__': unittest.main()
