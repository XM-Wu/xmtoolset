"""Change the extension of every file in a selected folder."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app import config
from app.tools.base_tool import BaseTool
from app.tools.file_renamer import RenamePlan, apply_renames, plan_renames


class FileRenamerTool(BaseTool):
    tool_id = 'file_renamer'
    tool_name = '文件改名'
    tool_description = '批量把文件夹中的文件改成指定后缀'

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.directory: Path | None = None
        self.plans: list[RenamePlan] = []
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel(self.tool_name)
        title.setObjectName('pageTitle')
        root.addWidget(title)

        hint = QLabel('选择一个文件夹，把其中文件的后缀改成同一个。先看预览，确认后才会修改原文件。')
        hint.setObjectName('mutedLabel')
        hint.setWordWrap(True)
        root.addWidget(hint)

        folder_box = QGroupBox('文件夹')
        folder_row = QHBoxLayout(folder_box)
        self.folder_label = QLabel('尚未选择')
        self.folder_label.setObjectName('mutedLabel')
        self.folder_label.setWordWrap(True)
        self.choose_button = QPushButton('选择文件夹…')
        self.choose_button.clicked.connect(self.choose_folder)
        folder_row.addWidget(self.folder_label, 1)
        folder_row.addWidget(self.choose_button)
        root.addWidget(folder_box)

        option_box = QGroupBox('后缀')
        options = QVBoxLayout(option_box)
        extension_row = QHBoxLayout()
        extension_row.addWidget(QLabel('新后缀'))
        self.extension = QLineEdit()
        self.extension.setPlaceholderText('png')
        self.extension.setClearButtonEnabled(True)
        extension_row.addWidget(self.extension, 1)
        options.addLayout(extension_row)
        self.recursive = QCheckBox('包含子文件夹')
        options.addWidget(self.recursive)
        root.addWidget(option_box)

        preview = QGroupBox('预览')
        preview_layout = QVBoxLayout(preview)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['原文件', '新文件', '结果'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(220)
        preview_layout.addWidget(self.table)
        root.addWidget(preview, 1)

        self.summary = QLabel('请选择文件夹。')
        self.summary.setObjectName('mutedLabel')
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        actions = QHBoxLayout()
        actions.addStretch()
        self.rename_button = QPushButton('开始改名')
        self.rename_button.setObjectName('primaryButton')
        self.rename_button.setMinimumHeight(36)
        self.rename_button.setEnabled(False)
        self.rename_button.clicked.connect(self.rename)
        actions.addWidget(self.rename_button)
        root.addLayout(actions)

        self.extension.textChanged.connect(self.refresh)
        self.recursive.toggled.connect(self.refresh)

    def choose_folder(self) -> None:
        start = config.settings().value('renamer/directory', '', type=str)
        folder = QFileDialog.getExistingDirectory(self, '选择文件夹', start)
        if not folder:
            return
        self.set_directory(folder)
        config.settings().setValue('renamer/directory', folder)

    def set_directory(self, path: str | Path) -> None:
        folder = Path(path)
        if not folder.is_dir():
            QMessageBox.warning(self, '无法打开文件夹', '请选择一个文件夹。')
            return
        self.directory = folder
        self.folder_label.setText(str(folder))
        self.refresh()

    def refresh(self) -> None:
        self.plans = []
        self.table.setRowCount(0)
        if self.directory is None:
            self.summary.setText('请选择文件夹。')
            self.rename_button.setEnabled(False)
            return
        if not self.extension.text().strip():
            self.summary.setText('请填写新的后缀名，例如 png。')
            self.rename_button.setEnabled(False)
            return
        try:
            self.plans = plan_renames(
                self.directory,
                self.extension.text(),
                recursive=self.recursive.isChecked(),
            )
        except ValueError as exc:
            self.summary.setText(str(exc))
            self.rename_button.setEnabled(False)
            return
        if not self.plans:
            self.summary.setText('这个文件夹里没有文件。')
            self.rename_button.setEnabled(False)
            return
        self._fill_table()
        ready = sum(item.status == 'ready' for item in self.plans)
        unchanged = sum(item.status == 'unchanged' for item in self.plans)
        conflict = sum(item.status == 'conflict' for item in self.plans)
        suffix = next((item.destination.suffix for item in self.plans if item.status == 'ready'), '')
        parts = [f'共 {len(self.plans)} 个文件', f'将把 {ready} 个改为 {suffix}' if suffix else f'将修改 {ready} 个']
        if unchanged:
            parts.append(f'{unchanged} 个已是该后缀')
        if conflict:
            parts.append(f'{conflict} 个有冲突')
        self.summary.setText('，'.join(parts) + '。')
        self.rename_button.setEnabled(ready > 0)

    def rename(self) -> None:
        self.refresh()
        ready = [item for item in self.plans if item.status == 'ready']
        if not ready:
            return
        skipped = len(self.plans) - len(ready)
        suffix = ready[0].destination.suffix
        text = f'将把 {len(ready)} 个文件的后缀改为 {suffix}。\n文件名的其余部分不变，并直接修改原文件。'
        if skipped:
            text += f'\n另外 {skipped} 个文件会跳过。'
        answer = QMessageBox.question(self, '确认改名', text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        try:
            done = apply_renames(self.plans)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, '改名失败', str(exc))
            self.refresh()
            return
        self.refresh()
        QMessageBox.information(self, '改名完成', f'已修改 {len(done)} 个文件。')

    def _fill_table(self) -> None:
        self.table.setRowCount(len(self.plans))
        for row, plan in enumerate(self.plans):
            values = (self._relative(plan.source), self._relative(plan.destination), plan.reason)
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, column, item)

    def _relative(self, path: Path) -> str:
        if self.directory is None:
            return path.name
        try:
            return path.relative_to(self.directory).as_posix()
        except ValueError:
            return path.name

    def _dropped_folder(self, mime) -> Path | None:
        urls = mime.urls() if mime.hasUrls() else []
        if len(urls) == 1 and urls[0].isLocalFile():
            path = Path(urls[0].toLocalFile())
            if path.is_dir():
                return path
        return None

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._dropped_folder(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if self._dropped_folder(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        folder = self._dropped_folder(event.mimeData())
        if folder is None:
            event.ignore()
            return
        self.set_directory(folder)
        config.settings().setValue('renamer/directory', str(folder))
        event.acceptProposedAction()
