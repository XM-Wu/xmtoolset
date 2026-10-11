import os, json
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata
root=Path(os.environ['PYTOOLS_BUILD_SOURCE']); staging=Path(os.environ['PYTOOLS_BUILD_META'])
product=json.loads(os.environ['PYTOOLS_PRODUCT'])
datas=[(str(root/'app'/'icons'),'app/icons')]; binaries=[]
hidden=['PySide6.QtSvg','app.tools.'+product['module']+'.widget']
if product['module']=='image_converter':
    d,b,h=collect_all('pillow_avif'); datas+=d; binaries+=b; hidden+=h+['PIL.AvifImagePlugin']
    datas+=copy_metadata('pillow-avif-plugin')
if product['module']=='video_converter':
    datas+=collect_data_files('imageio_ffmpeg')+copy_metadata('imageio-ffmpeg')
a=Analysis([str(root/(product['id']+'.py'))],pathex=[str(root)],binaries=binaries,datas=datas,
    hiddenimports=hidden,excludes=['PyQt5','PyQt6','PySide2','tkinter','matplotlib','numpy','pandas','torch','IPython','pyzipper','Cryptodome'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name=product['exe'],console=False,debug=False,strip=False,upx=False,version=str(staging/'version.txt'))
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name=product['exe'])
