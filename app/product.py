"""Process-local identity, selected before importing widgets or settings."""
TOOL_ID = None
NAME = "XM 小应用"
VERSION = ""
ENTRY = ""
MODULE = None

def select(tool_id, name, version, entry, module):
    global TOOL_ID, NAME, VERSION, ENTRY, MODULE
    TOOL_ID, NAME, VERSION, ENTRY, MODULE = tool_id, name, version, entry, module
