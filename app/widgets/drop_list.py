"""可拖放文件的列表控件。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QWidget


class DropListWidget(QListWidget):
    """支持拖放文件/文件夹的列表。"""

    def __init__(self, on_paths_dropped, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_paths_dropped = on_paths_dropped
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setAlternatingRowColors(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        paths = [Path(url.toLocalFile()) for url in urls if url.isLocalFile()]
        if paths:
            self._on_paths_dropped(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)
