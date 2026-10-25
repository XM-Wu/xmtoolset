"""Isolated diagnostics used for source and frozen release validation."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
from unittest.mock import patch


def run(report: Path) -> int:
    report = report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    checks = []
    def check(value, name):
        if not value:
            raise AssertionError(name)
        checks.append(name)
    result = {'success': False, 'frozen': bool(getattr(sys, 'frozen', False)), 'checks': checks}
    try:
        from PySide6.QtCore import QSettings, Qt
        from PySide6.QtWidgets import QApplication
        from app import product
        from app import config
        from app.theme import apply_dark_theme, _CHECK_ICON
        from app.main_window import MainWindow

        result['version'] = product.VERSION
        result['toolId'] = product.TOOL_ID
        app = QApplication.instance() or QApplication(['PyTools self-test'])
        app.setQuitOnLastWindowClosed(False)
        apply_dark_theme(app)
        with tempfile.TemporaryDirectory(prefix='py-tools-selftest-') as tmp:
            data = Path(tmp)
            isolated = QSettings(str(data/'settings.ini'), QSettings.IniFormat)
            with patch.object(config, 'settings', return_value=isolated):
                check(config._APP == product.TOOL_ID, 'product settings are isolated')
                legacy_source=data/'legacy-source';legacy_source.mkdir();(legacy_source/'keep.txt').write_text('preserve',encoding='utf-8')
                legacy_target=data/'legacy-target'
                legacy_jobs=json.dumps([{'source':str(legacy_source),'destination':str(legacy_target),'interval_sec':30,'enabled':True}])
                isolated.setValue('backup/tasks',legacy_jobs)
                isolated.setValue('archive/tasks',legacy_jobs)
                window = MainWindow(diagnostic=True)
                window.setAttribute(Qt.WA_DontShowOnScreen, True)
                window.show()
                app.processEvents()
                check(window.centralWidget().tool_id == product.MODULE, 'product panel is the central widget')
                check(not any(name.startswith(('app.tools.auto_backup','app.tools.archive')) for name in sys.modules), 'auto backup modules are not imported')
                check(window.grab().save(str(report.with_suffix('.png'))), 'UI screenshot rendered')
                from PySide6.QtWidgets import QSystemTrayIcon
                check(not window.findChildren(QSystemTrayIcon), 'no tray icon')
                window.showMinimized();app.processEvents()
                check(window.isVisible() and window.isMinimized(), 'minimize remains on taskbar')
                window.showNormal();window.close();app.processEvents()
                check(not window.isVisible(), 'close hides window for application exit')
                check(Path(_CHECK_ICON).is_file(), 'bundled stylesheet SVG is present')
                if product.MODULE=='image_converter':
                    from PIL import Image
                    from app.tools.image_converter import convert_image
                    Image.new('RGB',(32,32),(60,120,180)).save(data/'input.png')
                    for fmt in ('PNG','JPEG','WEBP','AVIF'):
                        output = data/('output.'+fmt.lower())
                        convert_image(data/'input.png', output, fmt)
                        with Image.open(output) as image:
                            image.load();check(image.size==(32,32), fmt+' conversion and decoding')
                if product.MODULE=='video_converter':
                    from app.tools.video_converter import get_ffmpeg_exe, convert_video
                    ffmpeg = get_ffmpeg_exe()
                    if getattr(sys, 'frozen', False):
                        check(Path(ffmpeg).resolve().is_relative_to(Path(sys._MEIPASS).resolve()), 'FFmpeg comes from the package, not system PATH')
                    flags = subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
                    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=blue:s=32x32:d=0.3','-y',str(data/'input.mp4')],check=True,capture_output=True,timeout=30,creationflags=flags)
                    convert_video(data/'input.mp4', data/'output.wmv', 'WMV', lossless=False)
                    check((data/'output.wmv').stat().st_size>0, 'bundled FFmpeg video conversion')
                if product.MODULE in ('dot_pattern','pleated_skirt'):
                    from app.widgets.color_picker_core import ColorPickerDialog, _screen_pixel
                    from PySide6.QtGui import QColor
                    picker=ColorPickerDialog(QColor('#804080c0'),allow_alpha=True,allow_clear=False)
                    picker.alpha.box.setValue(77)
                    check(QColor(picker.selected_hex()).alpha()==77,'shared color picker preserves alpha')
                    check(picker.screen_pick_btn.text()=='屏幕取色','screen picker entry is bundled')
                    from PySide6.QtCore import QSize, QPointF, QPoint
                    from PySide6.QtGui import QImage
                    sample=QImage(200,100,QImage.Format_RGB32);sample.fill(QColor('#abcdef'))
                    check(_screen_pixel(sample,QSize(100,50),QPointF(15.5,8.5))==QPoint(31,17),'screen picker high-DPI coordinate mapping')
                    picker.setAttribute(Qt.WA_DontShowOnScreen,True)
                    picker._start_screen_pick();picker._screen_color_picked(QColor('#abcdef'))
                    check(picker.selected_hex()=='#4DABCDEF' and not picker._pick_timer.isActive(),'screen picker selection preserves alpha and completes')
                    picker.close()
                if product.MODULE=='dot_pattern':
                    from app.tools.dot_pattern import DotPatternParams, render_pattern, render_pattern_svg
                    from PySide6.QtCore import QByteArray
                    from PySide6.QtSvg import QSvgRenderer
                    params=DotPatternParams(64,64,12,3,8,64,'left_right',90,(255,0,0,255),(0,0,0,0))
                    output=render_pattern(params)
                    output.save(data/'pattern.png')
                    check(output.size==(64,64) and output.getbbox() is not None, 'dot pattern renders and exports PNG')
                    svg=render_pattern_svg(params)
                    check(QSvgRenderer(QByteArray(svg.encode())).isValid() and '<image' not in svg, 'dot pattern exports vector SVG')
                    from app.tools.dot_pattern.graphics.catalog import CATALOG
                    from app.tools.dot_pattern.graphics.render import rasterize
                    window.resize(1120,760)
                    for kind in CATALOG:
                        window.tool.mode.setCurrentIndex(window.tool.mode.findData(kind))
                        app.processEvents()
                        doc=window.tool.document
                        check(doc is not None, kind+' controls and SVG render')
                        check(rasterize(doc).save(str(data/(kind+'.png'))), kind+' PNG export')
                    window.tool.mode.setCurrentIndex(window.tool.mode.findData('scale'))
                    app.processEvents()
                    check(window.grab().save(str(report.with_suffix('.png'))), 'graphic workbench screenshot rendered')
                if product.MODULE=='view_splitter':
                    from PIL import Image, ImageDraw
                    from app.tools.view_splitter import export_slices
                    sample=Image.new('RGBA',(901,420),(0,0,0,0))
                    draw=ImageDraw.Draw(sample)
                    for left,color in ((20,'#89b4fa'),(320,'#a6e3a1'),(620,'#f5c2e7')):
                        draw.rounded_rectangle((left,35,left+260,385),radius=35,fill=color)
                        draw.ellipse((left+85,90,left+175,180),fill='#313244')
                        draw.rectangle((left+75,200,left+185,330),fill='#45475a')
                    sample.save(data/'three-views.png')
                    check(window.tool.load(str(data/'three-views.png')), 'PNG loads into splitter')
                    check(window.tool.last_cuts==[300,600], 'default three-way split')
                    files=export_slices(window.tool.image,window.tool.last_cuts,data,'three-views')
                    check(len(files)==3,'all slices exported')
                    merged=Image.new('RGBA',sample.size)
                    x=0
                    for file in files:
                        with Image.open(file) as part:
                            merged.paste(part,(x,0));x+=part.width
                    check(merged.tobytes()==sample.tobytes(),'export preserves all pixels and transparency')
                    window.resize(1120,760);app.processEvents()
                    check(window.grab().save(str(report.with_suffix('.png'))),'splitter screenshot rendered')
                if product.MODULE=='file_renamer':
                    from app.tools.file_renamer import apply_renames
                    folder=data/'notes'
                    folder.mkdir()
                    (folder/'a.txt').write_text('a',encoding='utf-8')
                    (folder/'b.jpg').write_text('b',encoding='utf-8')
                    nested=folder/'keep'
                    nested.mkdir()
                    (nested/'c.txt').write_text('c',encoding='utf-8')
                    window.resize(1120,760)
                    window.tool.set_directory(folder)
                    window.tool.extension.setText('png')
                    app.processEvents()
                    check(window.tool.table.rowCount()==2 and window.tool.rename_button.isEnabled(), 'renamer preview lists the folder')
                    done=apply_renames(window.tool.plans)
                    check({dest.name for _,dest in done}=={'a.png','b.png'}, 'renames every file in the folder')
                    check((folder/'a.png').read_text(encoding='utf-8')=='a' and (nested/'c.txt').is_file(), 'extension rename keeps contents and subfolders')
                    check(window.grab().save(str(report.with_suffix('.png'))), 'renamer screenshot rendered')
                if product.MODULE=='pleated_skirt':
                    import xml.etree.ElementTree as ET
                    from PIL import Image
                    window.tool.stage.setCurrentIndex(0);window.tool.refresh()
                    window.tool.save_image(data/'weave.png','png')
                    with Image.open(data/'weave.png') as image:
                        check(len(image.convert('RGB').getcolors(3) or [])==2,'black and white weave structure')
                    window.tool.stage.setCurrentIndex(1);window.tool.refresh()
                    window.tool.save_image(data/'plaid.svg','svg')
                    window.tool.save_image(data/'plaid.png','png')
                    check(ET.parse(data/'plaid.svg').getroot().tag.endswith('svg'),'plaid SVG export')
                    with Image.open(data/'plaid.png') as image:
                        check(image.size==window.tool.params().dimensions(),'plaid PNG uses seamless tile size')
                    window.resize(1200,860);app.processEvents()
                    check(window.grab().save(str(report.with_suffix('.png'))),'plaid editor screenshot rendered')
                check(not legacy_target.exists() and isolated.value('archive/tasks')==legacy_jobs and isolated.value('backup/tasks')==legacy_jobs, 'retired jobs remain inert')
                isolated.sync()
        result['success']=True
    except Exception:
        result['error']=traceback.format_exc()
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if result['success'] else 1
