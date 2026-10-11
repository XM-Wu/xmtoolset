import json
from pathlib import Path
from app import product
identity = json.loads(Path(__file__).with_name('apps.json').read_text(encoding='utf-8'))['video-converter']
product.select('video-converter', identity['name'], identity['version'], 'video-converter.py', identity['module'])
from main_app import main
if __name__ == '__main__':
    raise SystemExit(main())
