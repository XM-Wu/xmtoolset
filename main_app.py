#!/usr/bin/env python3
"""Py 工具集入口。"""

import sys

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from app.main_window import MainWindow
from app.theme import apply_dark_theme


def main() -> int:
    if "--self-test" in sys.argv:
        import argparse
        from pathlib import Path
        from app.build_selftest import run
        parser = argparse.ArgumentParser()
        parser.add_argument("--self-test", action="store_true")
        parser.add_argument("--report", type=Path, required=True)
        args = parser.parse_args()
        return run(args.report)
    app = QApplication(sys.argv)
    from app.version import __version__
    from app import product
    app.setApplicationVersion(product.VERSION)
    from app import product
    app.setApplicationName(product.NAME)
    app.setOrganizationName("py_tools")
    # 关闭主窗口（隐藏到托盘）时不要退出进程
    if QSystemTrayIcon.isSystemTrayAvailable():
        app.setQuitOnLastWindowClosed(False)
    apply_dark_theme(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
