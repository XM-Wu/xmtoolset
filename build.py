"""Build, test and package Py Tools locally. Never installs packages or uploads."""
from __future__ import annotations
import argparse
import ast
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parent

def dependencies():
    packages={}
    for line in (ROOT/'requirements-build.lock.txt').read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):continue
        name,expected=line.split('==')
        actual=metadata.version(name)
        if actual!=expected:raise RuntimeError(f'{name}: expected {expected}, found {actual}. Prepare a separate build environment from requirements-build.lock.txt.')
        packages[name]=actual
    return packages

def smoke(executable: Path, working: Path, report: Path):
    env=os.environ.copy()
    for key in list(env):
        if key.startswith(('PYTHON','QT_')) or key in ('QML2_IMPORT_PATH','IMAGEIO_FFMPEG_EXE'):env.pop(key,None)
    env['PATH']=str(Path(os.environ['SystemRoot'])/'System32')
    env['QT_QPA_PLATFORM']='windows'
    completed=subprocess.run([str(executable),'--self-test','--report',str(report)],cwd=working,env=env,
        timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    if completed.returncode!=0 or not report.is_file():raise RuntimeError('Frozen smoke test failed: '+str(report))
    result=json.loads(report.read_text(encoding='utf-8'))
    if not result['success'] or not result['frozen']:raise RuntimeError('Frozen diagnostic failed: '+str(report))
    print(f"Frozen smoke test: {len(result['checks'])} checks passed",flush=True)

def build(output: Path, tool_id: str):
    if sys.platform!='win32' or platform.machine().lower() not in ('amd64','x86_64') or sys.version_info[:2]!=(3,13):
        raise RuntimeError('Release build requires Windows x64 and Python 3.13.')
    product=json.loads((ROOT/'apps.json').read_text(encoding='utf-8'))[tool_id]
    release_version=product['version']; executable=product['exe']; packages=dependencies();destination=output.resolve()/tool_id/release_version
    if destination.exists():raise FileExistsError(f'Release already exists: {destination}. Use a new version or a separate output root.')
    subprocess.run([sys.executable,str(ROOT/'tests'/'test_runtime.py')],cwd=ROOT,check=True)
    output.mkdir(parents=True,exist_ok=True)
    # The unique owned temporary directory contains only build inputs and generated files.
    with tempfile.TemporaryDirectory(prefix='py-tools-build-') as temporary:
        work=Path(temporary).resolve();source=work/'source';source.mkdir()
        (source/(tool_id+'.py')).write_text(f"from app import product\nproduct.select({tool_id!r}, {product['name']!r}, {release_version!r}, {tool_id+'.py'!r}, {product['module']!r})\nfrom app.runtime import main\nif __name__ == '__main__':\n    raise SystemExit(main())\n",encoding='utf-8')
        shutil.copytree(ROOT/'app',source/'app',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for sibling in ('image_converter','video_converter','dot_pattern'):
            if sibling != product['module']:
                target=source/'app'/'tools'/sibling
                assert target.resolve().is_relative_to(source.resolve())
                shutil.rmtree(target)
        parts=tuple(int(p) for p in release_version.split('.'))+(0,)
        windows_version=f"VSVersionInfo(ffi=FixedFileInfo(filevers={parts!r},prodvers={parts!r},mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),kids=[StringFileInfo([StringTable('040904B0',[StringStruct('ProductName','{executable}'),StringStruct('FileDescription','{executable}'),StringStruct('FileVersion','{release_version}'),StringStruct('ProductVersion','{release_version}'),StringStruct('OriginalFilename','{executable}.exe')])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])"
        (work/'version.txt').write_text(windows_version,encoding='utf-8')
        env=os.environ.copy();env['PYTOOLS_BUILD_SOURCE']=str(source);env['PYTOOLS_BUILD_META']=str(work)
        env['PYTOOLS_PRODUCT']=json.dumps(dict(product, id=tool_id));env['PYTHONPATH']=str(source);env['PYINSTALLER_CONFIG_DIR']=str(work/'pyinstaller-cache')
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--distpath',str(work/'dist'),
            '--workpath',str(work/'pyinstaller'),str(ROOT/'pack'/'SmallApp.spec')],cwd=source,env=env,check=True)
        bundle=work/'dist'/executable
        (bundle/'VERSION').write_text(release_version+'\n',encoding='utf-8')
        license_root=bundle/'THIRD_PARTY';license_root.mkdir()
        for name in packages:
            dist=metadata.distribution(name)
            for item in dist.files or []:
                lowered=str(item).lower()
                if '.dist-info/' in lowered and ('/licenses/' in lowered or Path(lowered).name.startswith(('license','copying','notice'))):
                    file=Path(dist.locate_file(item))
                    if file.is_file():
                        target=license_root/name/str(item).split('.dist-info/',1)[1];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
        # Relocate the bundle before testing, then remove the staging source from import lookup.
        relocated=work/'relocated 中文 path'/executable;relocated.parent.mkdir()
        shutil.move(str(bundle),str(relocated))
        original_source=source;source=work/'source-not-on-import-path';original_source.rename(source)
        report=work/'smoke-report.json';smoke(relocated/(executable+'.exe'),work,report)
        package_name=f'{tool_id}-{release_version}-win-x64.zip';package=work/package_name
        with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
            for file in sorted(relocated.rglob('*')):
                if file.is_file():archive.write(file,file.relative_to(relocated))
        with package.open('rb') as stream:
            sha=hashlib.file_digest(stream,'sha256').hexdigest()
        descriptor={'schemaVersion':1,'toolId':tool_id,'version':release_version,'platform':'win-x64','packageFile':package_name,
            'size':package.stat().st_size,'sha256':sha,'entryPoint':(executable+'.exe'),'minimumLauncherVersion':'0.1.0','runtimeMode':'self-contained','dataSchemaVersion':1}
        manifest=work/f'{tool_id}-{release_version}-win-x64.unsigned.json';manifest.write_text(json.dumps(descriptor,indent=2)+'\n',encoding='utf-8')
        # Test bytes extracted from the actual release ZIP, not just the pre-package folder.
        extracted=work/'zip-check';extracted.mkdir()
        with zipfile.ZipFile(package) as archive:archive.extractall(extracted)
        smoke(extracted/(executable+'.exe'),work,work/'zip-smoke-report.json')
        destination.mkdir(parents=True)
        shutil.copytree(relocated,destination/executable)
        for file in (package,manifest,report,report.with_suffix('.png'),work/'zip-smoke-report.json'):
            shutil.copy2(file,destination/file.name)
        info={'toolId':tool_id,'version':release_version,'python':platform.python_version(),'packages':packages,
            'package':package_name,'sha256':sha,'uploaded':False,'signed':False}
        (destination/'build-info.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
    print('BUILD OK: '+str(destination),flush=True)
    return destination

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=ROOT/'artifacts')
    parser.add_argument('--tool',choices=['all','image-converter','video-converter','dot-pattern'],default='all')
    args=parser.parse_args()
    try:
        for tool_id in (json.loads((ROOT/'apps.json').read_text(encoding='utf-8')) if args.tool=='all' else [args.tool]):
            build(args.output_dir,tool_id)
    except Exception as exc:
        print('BUILD FAILED: '+str(exc),file=sys.stderr);raise SystemExit(1)
