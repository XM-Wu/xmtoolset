"""PNG splitter: drag vertical guides, then export original-resolution crops."""
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, QPointF, QRectF, Signal, QUrl
from PySide6.QtGui import QColor, QBrush, QDesktopServices, QImage, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QFileDialog, QGraphicsItem, QGraphicsLineItem, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QSpinBox,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from app import config
from app.tools.base_tool import BaseTool
from . import equal_cuts, export_slices, intervals, load_png


class CutLine(QGraphicsLineItem):
    def __init__(self, view, x):
        super().__init__(0, 0, 0, view.image_height)
        self.view = view
        pen = QPen(QColor('#f9e2af'), 2)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setCursor(Qt.SplitHCursor)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
        self.setPos(x, 0)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(2)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            others = [line.pos().x() for line in self.view.lines if line is not self]
            previous = max([0] + [x for x in others if x < self.pos().x()])
            following = min([self.view.image_width] + [x for x in others if x > self.pos().x()])
            return QPointF(max(previous + 1, min(following - 1, round(value.x()))), 0)
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.view.cutsChanged.emit()


class SplitView(QGraphicsView):
    cutsChanged = Signal()
    addAt = Signal(int)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setMinimumSize(320, 240)
        tile = QPixmap(24, 24)
        tile.fill(QColor('#313244'))
        painter = QPainter(tile)
        painter.fillRect(0, 0, 12, 12, QColor('#45475a'))
        painter.fillRect(12, 12, 12, 12, QColor('#45475a'))
        painter.end()
        self.setBackgroundBrush(QBrush(tile))
        self.image_width = self.image_height = 0
        self.lines = []
        self.auto_fit = True
        self.drag_line = None
        self.setAcceptDrops(False)
        self.viewport().setAcceptDrops(False)

    def set_image(self, image):
        self.drag_line = None
        self.lines = []
        self.scene().clear()
        self.image_width, self.image_height = image.size
        preview = image.convert('RGBA')
        preview.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
        raw = preview.tobytes()
        qimage = QImage(raw, preview.width, preview.height, preview.width * 4, QImage.Format_RGBA8888).copy()
        item = self.scene().addPixmap(QPixmap.fromImage(qimage))
        item.setTransform(QTransform.fromScale(image.width / preview.width, image.height / preview.height))
        self.setSceneRect(QRectF(0, 0, image.width, image.height))
        self.fit()

    def set_cuts(self, cuts):
        for line in self.lines:
            self.scene().removeItem(line)
        self.lines = []
        for x in sorted(cuts):
            line = CutLine(self, x)
            self.lines.append(line)
            self.scene().addItem(line)

    def cuts(self):
        return sorted(round(line.pos().x()) for line in self.lines)

    def fit(self):
        self.auto_fit = True
        if self.image_width:
            self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.auto_fit: self.fit()

    def wheelEvent(self, event):
        if not self.image_width: return
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        if .001 < self.transform().m11() * factor < 32:
            self.auto_fit = False
            self.scale(factor, factor)
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if self.image_width and event.button() == Qt.LeftButton:
            self.addAt.emit(round(self.mapToScene(event.position().toPoint()).x()))
            event.accept()
        else: super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.lines:
            line = min(self.lines, key=lambda item: abs(self.mapFromScene(item.pos()).x()-event.position().x()))
            point = self.mapToScene(event.position().toPoint())
            if abs(self.mapFromScene(line.pos()).x()-event.position().x()) <= 8 and 0 <= point.y() <= self.image_height:
                for item in self.lines: item.setSelected(item is line)
                self.drag_line = line
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_line is not None:
            point = self.mapToScene(event.position().toPoint())
            self.drag_line.setPos(point.x(), 0)
            event.accept()
        else: super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drag_line is not None:
            self.drag_line = None
            self.cutsChanged.emit()
            event.accept()
        else: super().mouseReleaseEvent(event)


class ViewSplitterTool(BaseTool):
    tool_id = 'view_splitter'
    tool_name = '三视图切分器'
    tool_description = '拖入 PNG，垂直切割为多张图片并批量导出'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.source = None
        self.output = None
        self.history = []
        self.last_cuts = []
        self.setAcceptDrops(True)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        title = QLabel(self.tool_name);title.setObjectName('pageTitle');root.addWidget(title)
        hint = QLabel('拖入一张 PNG，默认三等分。拖动竖线调整边界，双击图片添加切割线；滚轮缩放，空白处拖动平移。')
        hint.setWordWrap(True);hint.setObjectName('mutedLabel');root.addWidget(hint)
        toolbar = QHBoxLayout()
        open_button = QPushButton('打开 PNG…');open_button.clicked.connect(self.choose);toolbar.addWidget(open_button)
        self.count = QSpinBox();self.count.setRange(2, 100);self.count.setValue(3)
        self.count.setPrefix('等分 ');self.count.setSuffix(' 张');toolbar.addWidget(self.count)
        self.equal_button = QPushButton('应用等分');self.equal_button.clicked.connect(self.equalize);toolbar.addWidget(self.equal_button)
        self.add_button = QPushButton('添加切割线');self.add_button.clicked.connect(self.add_largest);toolbar.addWidget(self.add_button)
        self.delete_button = QPushButton('删除选中线');self.delete_button.clicked.connect(self.delete_selected);toolbar.addWidget(self.delete_button)
        undo = QPushButton('撤销');undo.clicked.connect(self.undo);toolbar.addWidget(undo)
        fit = QPushButton('适应图片');fit.clicked.connect(lambda: self.view.fit());toolbar.addWidget(fit)
        toolbar.addStretch();root.addLayout(toolbar)
        split = QSplitter()
        self.view = SplitView();split.addWidget(self.view)
        self.view.cutsChanged.connect(self.moved)
        self.view.addAt.connect(self.add_cut)
        panel = QWidget();side = QVBoxLayout(panel);side.setContentsMargins(8,0,0,0)
        side.addWidget(QLabel('切割线位置（原图像素）'))
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['切割线', 'X 坐标'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setMinimumWidth(210)
        self.table.itemSelectionChanged.connect(self.select_line)
        side.addWidget(self.table)
        self.parts = QLabel('导出时保留原图分辨率和透明通道。')
        self.parts.setWordWrap(True);side.addWidget(self.parts)
        split.addWidget(panel);split.setStretchFactor(0,1);split.setSizes([680,240]);root.addWidget(split,1)
        self.status = QLabel('将 PNG 拖入此窗口，或点击“打开 PNG”。')
        self.status.setObjectName('mutedLabel');self.status.setWordWrap(True);root.addWidget(self.status)
        actions = QHBoxLayout()
        self.folder_button = QPushButton('打开导出文件夹');self.folder_button.setEnabled(False)
        self.folder_button.clicked.connect(self.open_folder);actions.addWidget(self.folder_button)
        actions.addStretch()
        self.export_button = QPushButton('导出全部 PNG…');self.export_button.setObjectName('primaryButton')
        self.export_button.clicked.connect(self.export);actions.addWidget(self.export_button);root.addLayout(actions)
        self.update_enabled()

    def update_enabled(self):
        for widget in (self.equal_button, self.add_button, self.delete_button, self.export_button):
            widget.setEnabled(self.image is not None)

    def choose(self):
        filename, _ = QFileDialog.getOpenFileName(self, '打开 PNG', config.settings().value('splitter/input_dir','',type=str), 'PNG 图片 (*.png)')
        if filename: self.load(filename)

    def load(self, filename):
        try:
            image = load_png(filename)
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            QMessageBox.warning(self, '无法打开图片', str(exc));return False
        self.image, self.source = image, Path(filename)
        self.history = []
        self.last_cuts = equal_cuts(image.width, 3)
        self.view.set_image(image);self.view.set_cuts(self.last_cuts)
        self.count.setValue(3)
        self.output = None;self.folder_button.setEnabled(False)
        self.refresh_table();self.update_enabled()
        config.settings().setValue('splitter/input_dir',str(self.source.parent))
        self.status.setText(f'{self.source.name} · {image.width} × {image.height} px')
        return True

    def apply_cuts(self, cuts):
        if self.image is None: return
        cuts = sorted(set(cuts))
        if cuts == self.last_cuts: return
        self.history.append(list(self.last_cuts));self.history=self.history[-100:]
        self.last_cuts = cuts
        self.view.set_cuts(cuts);self.refresh_table()

    def moved(self):
        cuts = self.view.cuts()
        if cuts != self.last_cuts:
            self.history.append(list(self.last_cuts));self.history=self.history[-100:]
            self.last_cuts = cuts;self.refresh_table()

    def equalize(self):
        if self.image is not None: self.apply_cuts(equal_cuts(self.image.width,self.count.value()))

    def add_cut(self, x):
        if self.image is not None and 0 < x < self.image.width and len(self.last_cuts)<99:
            self.apply_cuts([*self.last_cuts,x])

    def add_largest(self):
        if self.image is None: return
        left,right=max(intervals(self.image.width,self.last_cuts),key=lambda pair:pair[1]-pair[0])
        if right-left>1: self.add_cut((left+right)//2)

    def delete_selected(self):
        if self.image is None: return
        selected = {round(line.pos().x()) for line in self.view.lines if line.isSelected()}
        if not selected:
            rows={index.row() for index in self.table.selectedIndexes()}
            selected={self.last_cuts[i] for i in rows}
        self.apply_cuts([x for x in self.last_cuts if x not in selected])

    def select_line(self):
        rows={index.row() for index in self.table.selectedIndexes()}
        for i,line in enumerate(self.view.lines): line.setSelected(i in rows)

    def set_cut(self,index,value):
        cuts=list(self.last_cuts);cuts[index]=value
        self.apply_cuts(cuts)

    def refresh_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.last_cuts))
        for i,x in enumerate(self.last_cuts):
            item=QTableWidgetItem(str(i+1));item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i,0,item)
            box=QSpinBox()
            box.setRange((self.last_cuts[i-1]+1) if i else 1,(self.last_cuts[i+1]-1) if i+1<len(self.last_cuts) else self.image.width-1)
            box.setValue(x);box.setKeyboardTracking(False)
            box.editingFinished.connect(lambda index=i,control=box:self.set_cut(index,control.value()))
            self.table.setCellWidget(i,1,box)
        self.table.blockSignals(False)
        ranges=intervals(self.image.width,self.last_cuts)
        self.parts.setText(f'共 {len(ranges)} 张 · 从左至右导出\n'+ '\n'.join(f'{i:02d}：{b-a} × {self.image.height} px' for i,(a,b) in enumerate(ranges[:12],1)) + ('\n…' if len(ranges)>12 else ''))

    def undo(self):
        if self.history:
            self.last_cuts=self.history.pop();self.view.set_cuts(self.last_cuts);self.refresh_table()

    def export(self):
        if self.image is None: return
        # Commit a pending coordinate edit before choosing an output location.
        focus=self.focusWidget()
        if focus: focus.clearFocus()
        folder=QFileDialog.getExistingDirectory(self,'选择导出位置',config.settings().value('splitter/output_dir',str(self.source.parent),type=str))
        if not folder: return
        try:
            files=export_slices(self.image,self.last_cuts,folder,self.source.stem)
        except (OSError,ValueError) as exc:
            QMessageBox.warning(self,'导出失败',str(exc));return
        self.output=files[0].parent
        config.settings().setValue('splitter/output_dir',folder)
        self.folder_button.setEnabled(True)
        self.status.setText(f'已导出 {len(files)} 张 PNG：{self.output}')

    def open_folder(self):
        if self.output: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output)))

    @staticmethod
    def dropped_png(mime):
        urls=mime.urls() if mime.hasUrls() else []
        if len(urls)==1 and urls[0].isLocalFile() and Path(urls[0].toLocalFile()).suffix.lower()=='.png':
            return urls[0].toLocalFile()
        return None

    def dragEnterEvent(self,event):
        if self.dropped_png(event.mimeData()): event.acceptProposedAction()
        else: event.ignore()

    def dropEvent(self,event):
        filename=self.dropped_png(event.mimeData())
        if filename and self.load(filename): event.acceptProposedAction()
        else: event.ignore()
