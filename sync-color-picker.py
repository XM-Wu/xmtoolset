"""Sync the dependency-free color picker; no sibling repo is needed at runtime.

Usage: python sync-color-picker.py [--check] [--source /path/to/color_picker_core.py]
"""
import argparse
from pathlib import Path

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=root.parent/'XMComicLibrary/shared/widgets/color_picker_core.py')
parser.add_argument('--check',action='store_true')
args=parser.parse_args()
destination=root/'app/widgets/color_picker_core.py'
source=args.source.read_bytes()
if args.check:
    if destination.read_bytes()!=source: raise SystemExit('Color picker differs; run sync-color-picker.py')
    print('Shared color picker is in sync')
else:
    destination.write_bytes(source)
    print('Updated '+str(destination))
