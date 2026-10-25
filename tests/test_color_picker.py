import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtCore import QPoint,QPointF,QRect,QSize,Qt,QTimer
from PySide6.QtGui import QColor,QImage,QPixmap,QScreen
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtTest import QTest
from app.widgets.color_picker_core import ColorPickerDialog,_screen_pixel,_ScreenPickOverlay
from app.widgets.color_picker import pick_color


class ColorPickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_rgba_hsv_and_hex_preserve_alpha(self):
        picker=ColorPickerDialog(QColor('#804080c0'),allow_alpha=True,recent_loader=lambda:['#ff0000'])
        picker.red.box.setValue(90)
        self.assertEqual(QColor(picker.selected_hex()).alpha(),128)
        picker.sat_bar._edit(.3)
        self.assertEqual(picker._color.alpha(),128)
        picker.val_bar._edit(.8)
        self.assertEqual(picker._color.alpha(),128)
        picker.alpha.box.setValue(42)
        self.assertEqual(QColor(picker.selected_hex()).alpha(),42)
        picker.hex_edit.setText('#10445566');picker._from_hex()
        self.assertEqual(picker.selected_hex(),'#10445566')
        picker.hex_edit.setText('invalid');picker._from_hex()
        self.assertEqual(picker.selected_hex(),'#10445566')
        picker.close()

    def test_cancel_is_invalid_and_does_not_save(self):
        with patch('app.widgets.color_picker.recent_colors',return_value=[]),patch.object(ColorPickerDialog,'exec',return_value=QDialog.Rejected),patch('app.widgets.color_picker.config.settings') as settings:
            self.assertFalse(pick_color(QColor('#ff0000')).isValid())
            settings.assert_not_called()

    def test_shared_component_matches_canonical_source(self):
        canonical=ROOT.parent/'XMComicLibrary/shared/widgets/color_picker_core.py'
        if not canonical.exists(): self.skipTest('Sibling repository is not present')
        self.assertEqual(canonical.read_bytes(),(ROOT/'app/widgets/color_picker_core.py').read_bytes())

    def test_screen_pixel_mapping_fractional_dpi_and_negative_monitor_origin(self):
        image=QImage(1920,1080,QImage.Format_ARGB32);image.fill(QColor('#123456'))
        image.setPixelColor(31,17,QColor('#abcdef'))
        self.assertEqual(_screen_pixel(image,QSize(960,540),QPointF(15.5,8.5)),QPoint(31,17))
        self.assertEqual(_screen_pixel(image,QSize(1280,720),QPoint(10,10)),QPoint(15,15))
        self.assertEqual(_screen_pixel(image,QSize(960,540),QPoint(960,540)),QPoint(1919,1079))
        overlay=_ScreenPickOverlay(QRect(-1920,-200,960,540),image)
        self.assertEqual(overlay.color_at(QPointF(15.5,8.5)).name(),'#abcdef')
        overlay.close()

    def test_screen_capture_selection_updates_channels_and_preserves_alpha(self):
        picker=ColorPickerDialog(QColor('#804080c0'),allow_alpha=True)
        picker.show()
        snapshot=QPixmap(80,60);snapshot.fill(QColor('#e04020'))
        with patch.object(QScreen,'grabWindow',return_value=snapshot) as grab:
            picker._start_screen_pick();picker._pick_timer.stop()
            self.assertEqual(picker.windowOpacity(),0)
            picker._capture_screens()
            self.assertTrue(grab.called)
            self.assertEqual(len(picker._pick_overlays),len(QApplication.screens()))
            overlay=picker._pick_overlays[0]
            QTest.mouseClick(overlay,Qt.LeftButton,pos=QPoint(10,10))
        self.assertFalse(picker._screen_pick_active)
        self.assertEqual(picker._pick_overlays,[])
        self.assertTrue(overlay.image.isNull())
        self.assertTrue(picker.isVisible())
        self.assertEqual(picker.windowOpacity(),1)
        self.assertEqual(picker.selected_hex(),'#80E04020')
        self.assertEqual(picker.red.value(),224)
        self.assertEqual(picker.hex_edit.text(),'#80E04020')
        self.assertEqual(picker.result(),QDialog.Rejected)  # Selection does not accept the dialog.
        picker.close()

    def test_escape_right_click_and_capture_failure_leave_color_unchanged(self):
        for action in ('escape','right','close'):
            picker=ColorPickerDialog(QColor('#123456'));picker.show()
            snapshot=QPixmap(80,60);snapshot.fill(Qt.red)
            with patch.object(QScreen,'grabWindow',return_value=snapshot):
                picker._start_screen_pick();picker._pick_timer.stop();picker._capture_screens()
                overlay=picker._pick_overlays[0]
                if action=='escape':QTest.keyClick(overlay,Qt.Key_Escape)
                elif action=='right':QTest.mouseClick(overlay,Qt.RightButton,pos=QPoint(10,10))
                else:overlay.close()
            self.assertEqual(picker.selected_hex(),'#123456')
            self.assertTrue(picker.isVisible())
            self.assertFalse(picker._screen_pick_active)
            picker.close()
        picker=ColorPickerDialog(QColor('#123456'));picker.show()
        with patch.object(QScreen,'grabWindow',return_value=QPixmap()):
            picker._start_screen_pick();picker._pick_timer.stop();picker._capture_screens()
        self.assertTrue(picker.isVisible())
        self.assertFalse(picker._screen_pick_active)
        self.assertIn('失败',picker.screen_pick_status.text())
        self.assertEqual(picker.selected_hex(),'#123456')
        picker.close()

    def test_dialog_done_cancels_pending_capture(self):
        picker=ColorPickerDialog(QColor('#123456'));picker.show()
        picker._start_screen_pick();picker.done(QDialog.Rejected)
        self.assertFalse(picker._pick_timer.isActive())
        self.assertFalse(picker._screen_pick_active)
        self.assertFalse(picker.isVisible())

    def test_screen_pick_keeps_modal_exec_alive_until_confirmed(self):
        picker=ColorPickerDialog(QColor('#80123456'),allow_alpha=True)
        picker._pick_timer.setInterval(1)
        snapshot=QPixmap(80,60);snapshot.fill(QColor('#abcdef'))
        start=QTimer(picker);start.setSingleShot(True);start.timeout.connect(picker._start_screen_pick)
        finish=QTimer(picker);finish.setSingleShot(True)
        def select_then_confirm():
            picker._screen_color_picked(QColor('#abcdef'))
            picker.accept()
        finish.timeout.connect(select_then_confirm)
        timeout=QTimer(picker);timeout.setSingleShot(True);timeout.timeout.connect(picker.reject)
        with patch.object(QScreen,'grabWindow',return_value=snapshot):
            start.start(0);finish.start(60);timeout.start(1000)
            result=picker.exec()
        for timer in (start,finish,timeout):timer.stop()
        self.assertEqual(result,QDialog.Accepted)
        self.assertEqual(picker.selected_hex(),'#80ABCDEF')
        self.assertFalse(picker._screen_pick_active)


if __name__=='__main__': unittest.main()
