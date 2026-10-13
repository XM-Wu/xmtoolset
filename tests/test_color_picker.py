import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QDialog
from app.widgets.color_picker_core import ColorPickerDialog
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


if __name__=='__main__': unittest.main()
