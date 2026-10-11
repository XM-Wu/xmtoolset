"""工具基类：所有工具面板继承此类。"""

from PySide6.QtWidgets import QWidget


class BaseTool(QWidget):
    """工具基类，子类需定义 tool_id / tool_name / tool_description。"""

    tool_id: str = ""
    tool_name: str = "未命名工具"
    tool_description: str = ""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
