"""Load only the selected product's widgets."""
from importlib import import_module
from app import product

def load_tools():
    if product.MODULE is None:
        raise RuntimeError("Use an independent application entry point.")
    definitions = [('image_converter','ImageConverterTool'), ('video_converter','VideoConverterTool'), ('dot_pattern','DotPatternTool')]
    return [getattr(import_module('app.tools.'+module+'.widget'), cls) for module,cls in definitions if product.MODULE == module]
