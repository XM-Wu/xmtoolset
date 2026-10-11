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
            def deny_startup_write(*args, **kwargs):
                raise AssertionError('Self-test must not write Windows startup settings')
            with patch.object(config, 'settings', return_value=isolated), patch.object(config, 'is_autostart_enabled', return_value=False), patch.object(config, 'enable_autostart', side_effect=deny_startup_write), patch.object(config, 'disable_autostart', side_effect=deny_startup_write):
                check(config._APP == product.TOOL_ID, 'product settings are isolated')
                legacy_source=data/'legacy-source';legacy_source.mkdir();(legacy_source/'keep.txt').write_text('preserve',encoding='utf-8')
                legacy_target=data/'legacy-target'
                legacy_jobs=json.dumps([{'source':str(legacy_source),'destination':str(legacy_target),'interval_sec':30,'enabled':True}])
                isolated.setValue('backup/tasks',legacy_jobs)
                isolated.setValue('archive/tasks',legacy_jobs)
                window = MainWindow(diagnostic=True)
                window.setAttribute(Qt.WA_DontShowOnScreen, True)
                window.show()
                for index in range(window.stack.count()):
                    window.nav.setCurrentRow(index);app.processEvents()
                check(window.stack.count() == 2 and window._tools[0].tool_id == product.MODULE, 'only product and settings pages load')
                check(not any(name.startswith(('app.tools.auto_backup','app.tools.archive')) for name in sys.modules), 'auto backup modules are not imported')
                window.nav.setCurrentRow(0);app.processEvents()
                check(window.grab().save(str(report.with_suffix('.png'))), 'UI screenshot rendered')
                window._geom_timer.stop();window._force_quit = True;window.close();app.processEvents()
                check(Path(_CHECK_ICON).is_file(), 'bundled stylesheet SVG is present')
                if getattr(sys, 'frozen', False):
                    check(config.autostart_command() == f'"{Path(sys.executable)}"', 'frozen autostart targets the executable')
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
                if product.MODULE=='dot_pattern':
                    from app.tools.dot_pattern import DotPatternParams, render_pattern
                    params=DotPatternParams(64,64,12,3,8,64,'left_right',90,(255,0,0,255),(0,0,0,0))
                    output=render_pattern(params)
                    output.save(data/'pattern.png')
                    check(output.size==(64,64) and output.getbbox() is not None, 'dot pattern renders and exports PNG')
                check(not legacy_target.exists() and isolated.value('archive/tasks')==legacy_jobs and isolated.value('backup/tasks')==legacy_jobs, 'retired jobs remain inert')
                isolated.sync()
        result['success']=True
    except Exception:
        result['error']=traceback.format_exc()
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if result['success'] else 1
