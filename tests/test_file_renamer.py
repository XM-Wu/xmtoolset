import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6.QtWidgets import QApplication, QMessageBox
from app.tools.file_renamer import apply_renames, normalize_extension, plan_renames
from app.tools.file_renamer.widget import FileRenamerTool


class RenamerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'artifacts')
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_extension_text(self):
        self.assertEqual(normalize_extension(' png '), '.png')
        self.assertEqual(normalize_extension('.JPG'), '.JPG')
        for text in ('', '.', '..', 'a.b', 'png/jpg', 'a*', 'png.'):
            with self.assertRaises(ValueError):
                normalize_extension(text)

    def test_renames_files_in_folder_and_keeps_subfolders(self):
        (self.folder / 'a.txt').write_text('keep', encoding='utf-8')
        (self.folder / 'archive.tar.gz').write_text('bundle', encoding='utf-8')
        (self.folder / '.gitignore').write_text('hidden', encoding='utf-8')
        nested = self.folder / 'nested'
        nested.mkdir()
        (nested / 'c.txt').write_text('inside', encoding='utf-8')
        (self.folder / 'notes').mkdir()
        done = apply_renames(plan_renames(self.folder, 'png'))
        self.assertEqual(sorted(path.name for _, path in done), ['.gitignore.png', 'a.png', 'archive.tar.png'])
        self.assertEqual((self.folder / 'a.png').read_text(encoding='utf-8'), 'keep')
        self.assertEqual((self.folder / 'archive.tar.png').read_text(encoding='utf-8'), 'bundle')
        self.assertFalse((self.folder / 'a.txt').exists())
        self.assertEqual((nested / 'c.txt').read_text(encoding='utf-8'), 'inside')
        self.assertTrue((self.folder / 'notes').is_dir())

    def test_recursive_includes_nested_files(self):
        (self.folder / 'a.txt').write_text('a', encoding='utf-8')
        nested = self.folder / 'nested'
        nested.mkdir()
        (nested / 'b.txt').write_text('b', encoding='utf-8')
        done = apply_renames(plan_renames(self.folder, '.md', recursive=True))
        self.assertEqual({path.relative_to(self.folder).as_posix() for _, path in done}, {'a.md', 'nested/b.md'})

    def test_skips_unchanged_and_conflicts(self):
        (self.folder / 'ready.txt').write_text('yes', encoding='utf-8')
        (self.folder / 'kept.png').write_text('stay', encoding='utf-8')
        (self.folder / 'blocked.png').write_text('taken', encoding='utf-8')
        (self.folder / 'blocked.jpg').write_text('no', encoding='utf-8')
        (self.folder / 'photo.jpeg').write_text('one', encoding='utf-8')
        (self.folder / 'photo.png').write_text('two', encoding='utf-8')
        plans = plan_renames(self.folder, 'png')
        by_name = {plan.source.name: plan.status for plan in plans}
        self.assertEqual(by_name['ready.txt'], 'ready')
        self.assertEqual(by_name['kept.png'], 'unchanged')
        self.assertEqual(by_name['blocked.jpg'], 'conflict')
        self.assertEqual(by_name['photo.jpeg'], 'conflict')
        self.assertEqual(by_name['photo.png'], 'unchanged')
        done = apply_renames(plans)
        self.assertEqual([path.name for _, path in done], ['ready.png'])
        self.assertEqual((self.folder / 'blocked.jpg').read_text(encoding='utf-8'), 'no')
        self.assertEqual((self.folder / 'photo.png').read_text(encoding='utf-8'), 'two')

    def test_duplicate_targets_are_not_renamed(self):
        (self.folder / 'shot.jpg').write_text('a', encoding='utf-8')
        (self.folder / 'shot.jpeg').write_text('b', encoding='utf-8')
        plans = plan_renames(self.folder, 'png')
        self.assertTrue(all(plan.status == 'conflict' for plan in plans))
        self.assertEqual(apply_renames(plans), [])
        self.assertTrue((self.folder / 'shot.jpg').is_file())
        self.assertTrue((self.folder / 'shot.jpeg').is_file())

    def test_case_only_suffix_change(self):
        (self.folder / 'Photo.JPG').write_text('pic', encoding='utf-8')
        done = apply_renames(plan_renames(self.folder, 'jpg'))
        self.assertEqual([path.name for _, path in done], ['Photo.jpg'])
        self.assertEqual([path.name for path in self.folder.iterdir()], ['Photo.jpg'])
        self.assertEqual((self.folder / 'Photo.jpg').read_text(encoding='utf-8'), 'pic')

    def test_failure_restores_original_names(self):
        (self.folder / 'a.txt').write_text('a', encoding='utf-8')
        (self.folder / 'b.txt').write_text('b', encoding='utf-8')
        original = Path.rename
        failed = False

        def fail_final(self_path, target):
            nonlocal failed
            if not failed and target.suffix == '.png' and '.xmrename' not in target.name:
                failed = True
                raise OSError('disk full')
            return original(self_path, target)

        with patch.object(Path, 'rename', fail_final):
            with self.assertRaises(OSError):
                apply_renames(plan_renames(self.folder, 'png'))
        self.assertEqual(sorted(path.name for path in self.folder.iterdir()), ['a.txt', 'b.txt'])
        self.assertEqual((self.folder / 'a.txt').read_text(encoding='utf-8'), 'a')

    def test_widget_previews_confirms_and_renames(self):
        (self.folder / 'a.txt').write_text('keep', encoding='utf-8')
        nested = self.folder / 'sub'
        nested.mkdir()
        (nested / 'b.txt').write_text('nest', encoding='utf-8')
        tool = FileRenamerTool()
        tool.set_directory(self.folder)
        tool.extension.setText('md')
        self.assertEqual(tool.table.rowCount(), 1)
        self.assertEqual(tool.table.item(0, 2).text(), '将改名')
        self.assertTrue(tool.rename_button.isEnabled())
        tool.recursive.setChecked(True)
        self.assertEqual(tool.table.rowCount(), 2)
        with patch('app.tools.file_renamer.widget.QMessageBox.question', return_value=QMessageBox.No):
            tool.rename()
        self.assertTrue((self.folder / 'a.txt').is_file())
        with patch('app.tools.file_renamer.widget.QMessageBox.question', return_value=QMessageBox.Yes), \
             patch('app.tools.file_renamer.widget.QMessageBox.information'):
            tool.rename()
        self.assertEqual((self.folder / 'a.md').read_text(encoding='utf-8'), 'keep')
        self.assertEqual((nested / 'b.md').read_text(encoding='utf-8'), 'nest')
        self.assertFalse(tool.rename_button.isEnabled())


if __name__ == '__main__':
    unittest.main()
