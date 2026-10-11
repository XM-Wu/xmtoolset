"""Process-local identity, selected before importing widgets or settings."""
TOOL_ID = None
NAME = "Py 工具集"
VERSION = "0.2.0"
ENTRY = "main_app.py"
MODULE = None

def select(tool_id, name, version, entry, module):
    global TOOL_ID, NAME, VERSION, ENTRY, MODULE
    TOOL_ID, NAME, VERSION, ENTRY, MODULE = tool_id, name, version, entry, module
