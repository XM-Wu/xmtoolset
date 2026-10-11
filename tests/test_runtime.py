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
    def test_independent_product_settings_and_versions(self):
        root=Path(__file__).resolve().parents[1]
        products=json.loads((root/'apps.json').read_text(encoding='utf-8'))
        paths=[]
        for tool_id,identity in products.items():
            script="import runpy,json; runpy.run_path("+repr(str(root/(tool_id+'.py')))+",run_name='identity_check'); from app import config,product; print(json.dumps([config._APP,config.settings().fileName(),product.VERSION]))"
            result=json.loads(subprocess.check_output([sys.executable,'-c',script],cwd=root,text=True))
            self.assertEqual(result[0],tool_id)
            self.assertEqual(result[2],identity['version'])
            paths.append(result[1])
        self.assertEqual(len(set(paths)),3)

    def test_legacy_startup_cleanup_is_product_scoped(self):
        from unittest.mock import MagicMock
        registry=MagicMock()
        with patch.dict(sys.modules,winreg=registry),patch.object(config,'settings'):
            config.retire_legacy_startup()
        registry.DeleteValue.assert_called_once_with(registry.OpenKey.return_value.__enter__.return_value,product.TOOL_ID)
        registry.SetValueEx.assert_not_called()

    def test_missing_legacy_startup_is_harmless(self):
        from unittest.mock import MagicMock
        registry=MagicMock();registry.DeleteValue.side_effect=FileNotFoundError()
        with patch.dict(sys.modules,winreg=registry),patch.object(config,'settings'):
            config.retire_legacy_startup()

    def test_version_is_release_triplet(self):
        self.assertRegex(product.VERSION,r'^\d+\.\d+\.\d+$')

if __name__=='__main__':unittest.main()
