from pathlib import Path
import sys
import unittest
import subprocess
import json
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import product
product.select("image-converter","图片转换","0.1.1","image-converter.py","image_converter")
from app import config


class RuntimeTests(unittest.TestCase):
    def test_frozen_startup_does_not_depend_on_source_or_python(self):
        with patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',r'D:\Tool Apps\PyTools.exe'),patch.object(config,'_resolve_pythonw',side_effect=AssertionError('must not resolve Python')):
            self.assertEqual(config.autostart_command(),'"D:\\Tool Apps\\PyTools.exe"')
    def test_source_mode_preserved(self):
        with patch.object(sys,'frozen',False,create=True):
            command=config.autostart_command()
            self.assertTrue('image-converter.py' in command)
    def test_independent_product_settings_versions_and_startup(self):
        root=Path(__file__).resolve().parents[1]
        products=json.loads((root/'apps.json').read_text(encoding='utf-8'))
        settings_paths=[]
        for tool_id,identity in products.items():
            script="import runpy,json; runpy.run_path("+repr(str(root/(tool_id+'.py')))+",run_name='identity_check'); from app import config,product; print(json.dumps([config._APP,config._AUTOSTART_NAME,config.autostart_command(),config.settings().fileName(),product.VERSION]))"
            result=json.loads(subprocess.check_output([sys.executable,'-c',script],cwd=root,text=True))
            self.assertEqual(result[0:2],[tool_id,tool_id])
            self.assertIn(tool_id+'.py',result[2])
            self.assertEqual(result[4],identity['version'])
            settings_paths.append(result[3])
        self.assertEqual(len(set(settings_paths)),3)

    def test_version_is_release_triplet(self):
        self.assertRegex(product.VERSION,r'^\d+\.\d+\.\d+$')

if __name__=='__main__':unittest.main()
