import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PIL import Image
from PySide6.QtCore import QMimeData, QSettings, QUrl, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from app.tools.view_splitter import equal_cuts, export_slices, intervals, load_png
from app.tools.view_splitter.widget import ViewSplitterTool
from app import config


class SplitterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'artifacts')
        self.folder=Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_pixels_alpha_and_odd_width(self):
        image=Image.new('RGBA',(101,17))
        image.putdata([(x%256,(x*13)%256,(x*31)%256,x%256) for x in range(101*17)])
        cuts=equal_cuts(101)
        self.assertEqual(cuts,[33,67])
        files=export_slices(image,cuts,self.folder,'views')
        rebuilt=Image.new('RGBA',image.size)
        x=0
        for file in files:
            with Image.open(file) as crop:
                self.assertEqual(crop.height,17)
                rebuilt.paste(crop,(x,0));x+=crop.width
        self.assertEqual(image.tobytes(),rebuilt.tobytes())
        second=export_slices(image,cuts,self.folder,'views')
        self.assertNotEqual(files[0].parent,second[0].parent)
        self.assertTrue(all(p.is_file() for p in files))

    def test_input_validation_and_single_pixel(self):
        self.assertEqual(equal_cuts(1),[])
        self.assertEqual(intervals(5,[]),[(0,5)])
        for cuts in ([-1],[0],[5]):
            with self.assertRaises(ValueError): intervals(5,cuts)
        source=self.folder/'fake.png'
        Image.new('RGB',(8,8)).save(source,'JPEG')
        with self.assertRaises(ValueError): load_png(source)

    def test_failed_export_does_not_leave_partial_folder(self):
        image=Image.new('RGBA',(12,10))
        original=Image.Image.save
        calls=0
        def fail_second(obj,*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==2: raise OSError('disk full')
            return original(obj,*args,**kwargs)
        with patch.object(Image.Image,'save',fail_second):
            with self.assertRaises(OSError): export_slices(image,[4,8],self.folder,'views')
        self.assertEqual(list(self.folder.iterdir()),[])

    def test_ui_drag_coordinates_undo_and_drop_filter(self):
        source=self.folder/'input.png';Image.new('RGBA',(901,420),(60,70,80,90)).save(source)
        settings=QSettings(str(self.folder/'settings.ini'),QSettings.IniFormat)
        with patch.object(config,'settings',return_value=settings):
            tool=ViewSplitterTool();tool.resize(1120,760);tool.show();self.app.processEvents()
            self.assertTrue(tool.load(str(source)));self.app.processEvents()
            self.assertEqual(tool.last_cuts,[300,600])
            view=tool.view
            point=view.mapFromScene(300,210)
            target=view.mapFromScene(350,210)
            QTest.mousePress(view.viewport(),Qt.LeftButton,pos=point)
            QTest.mouseMove(view.viewport(),target)
            QTest.mouseRelease(view.viewport(),Qt.LeftButton,pos=target)
            self.assertLessEqual(abs(tool.last_cuts[0]-350),2)
            tool.undo();self.assertEqual(tool.last_cuts,[300,600])
            view.lines[0].setPos(900,0);view.cutsChanged.emit()
            self.assertEqual(tool.last_cuts,[599,600])
            tool.undo();tool.add_cut(450);self.assertEqual(tool.last_cuts,[300,450,600])
            tool.set_cut(1,480);self.assertEqual(tool.last_cuts,[300,480,600])
            tool.table.selectRow(1);tool.delete_selected();self.assertEqual(tool.last_cuts,[300,600])
            mime=QMimeData();mime.setUrls([QUrl.fromLocalFile(str(source))])
            self.assertEqual(Path(tool.dropped_png(mime)),source)
            mime.setUrls([QUrl.fromLocalFile(str(source))]*2);self.assertIsNone(tool.dropped_png(mime))
            tool.close()


if __name__=='__main__': unittest.main()
