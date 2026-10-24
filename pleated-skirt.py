import json
from pathlib import Path
from app import product
identity = json.loads(Path(__file__).with_name('apps.json').read_text(encoding='utf-8'))['pleated-skirt']
product.select('pleated-skirt', identity['name'], identity['version'], 'pleated-skirt.py', identity['module'])
from app.runtime import main
if __name__ == '__main__':
    raise SystemExit(main())
