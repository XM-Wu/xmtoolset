"""Load only the selected product's widgets."""
from importlib import import_module
from app import product
from app.tools.settings.widget import SettingsTool

def load_tools():
    definitions = [('image_converter','ImageConverterTool'), ('video_converter','VideoConverterTool'), ('dot_pattern','DotPatternTool')]
    return [getattr(import_module('app.tools.'+module+'.widget'), cls) for module,cls in definitions if product.MODULE is None or product.MODULE == module] + [SettingsTool]
