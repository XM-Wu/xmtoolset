"""Native graphic workbench with persistent per-generator parameters."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPixmap, QBrush
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox,
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGraphicsScene, QGraphicsView, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from app import config
from app.widgets.color_picker import pick_color
from app.tools.base_tool import BaseTool
from .catalog import CATALOG, EDIT_KINDS, TILE_KINDS, defaults
from .render import rasterize, render, tile_size


class Preview(QGraphicsView):
    picked = Signal(float, float, bool)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setMinimumSize(240, 200)
        tile = QPixmap(24,24)
        tile.fill(QColor('#313244'))
        painter=QPainter(tile)
        painter.fillRect(0,0,12,12,QColor('#45475a'))
        painter.fillRect(12,12,12,12,QColor('#45475a'))
        painter.end()
        self.setBackgroundBrush(QBrush(tile))
        self.auto_fit=True
        self.edit=False
        self.brush=False
        self.renderer=None

    def show_document(self, document):
        self.scene().clear()
        self.renderer=QSvgRenderer(QByteArray(document.svg.encode()),self)
        item=QGraphicsSvgItem()
        item.setSharedRenderer(self.renderer)
        self.scene().addItem(item)
        self.scene().setSceneRect(QRectF(0,0,document.width,document.height))
        if self.auto_fit: self.fit()

    def fit(self):
        self.auto_fit=True
        self.fitInView(self.sceneRect(),Qt.KeepAspectRatio)

    def wheelEvent(self,event):
        self.auto_fit=False
        factor=1.2 if event.angleDelta().y()>0 else 1/1.2
        if .02 < self.transform().m11()*factor < 40:
            self.scale(factor,factor)
        event.accept()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.auto_fit: self.fit()

    def mousePressEvent(self,event):
        if self.edit and event.button()==Qt.LeftButton:
            point=self.mapToScene(event.position().toPoint())
            self.picked.emit(point.x(),point.y(),self.brush)
            event.accept()
        else: super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self.edit and self.brush and event.buttons() & Qt.LeftButton:
            point=self.mapToScene(event.position().toPoint())
            self.picked.emit(point.x(),point.y(),True)
            event.accept()
        else: super().mouseMoveEvent(event)


class GraphicsTool(BaseTool):
    tool_id='dot_pattern'
    tool_name='图形生成工具'
    tool_description='波点、线条、网格与几何素材生成，导出 PNG / SVG'

    def __init__(self,parent=None):
        super().__init__(parent)
        self.controls={}
        self.states={}
        self.kind=None
        self.document=None
        self.hidden=set()
        self.styles={}
        self.history=[]
        self.selected=None
        self._loading=True
        self.timer=QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.refresh)
        try:
            saved=json.loads(config.settings().value('graphics/states','{}',type=str))
            self.states=saved if isinstance(saved,dict) else {}
        except (ValueError,TypeError): pass
        root=QVBoxLayout(self)
        root.setContentsMargins(14,12,14,12)
        top=QHBoxLayout()
        title=QLabel('图形生成工具');title.setObjectName('pageTitle')
        top.addWidget(title)
        top.addStretch()
        self.mode=QComboBox()
        self.mode.setMinimumWidth(180)
        self.mode.addItem('波点生成','legacy')
        for key,(name,_) in CATALOG.items(): self.mode.addItem(name,key)
        top.addWidget(self.mode)
        root.addLayout(top)
        self.stack=QStackedWidget()
        self.legacy_host=QWidget()
        self.legacy_layout=QVBoxLayout(self.legacy_host)
        self.legacy_layout.setContentsMargins(0,0,0,0)
        self.stack.addWidget(self.legacy_host)
        self.legacy=None
        self.editor=QWidget()
        layout=QVBoxLayout(self.editor);layout.setContentsMargins(0,0,0,0)
        split=QSplitter()
        self.scroll=QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setMinimumWidth(265)
        self.scroll.setMaximumWidth(410)
        split.addWidget(self.scroll)
        right=QWidget();right_layout=QVBoxLayout(right)
        right_layout.setContentsMargins(8,0,0,0)
        toolbar=QHBoxLayout()
        fit=QPushButton('适应画布');fit.clicked.connect(lambda:self.preview.fit())
        toolbar.addWidget(fit)
        full=QPushButton('全屏');full.clicked.connect(self.toggle_fullscreen)
        toolbar.addWidget(full)
        self.edit_mode=QComboBox()
        self.edit_mode.addItems(['拖动画布','点选编辑','按住擦除','按住恢复'])
        self.edit_mode.currentIndexChanged.connect(self.set_edit_mode)
        toolbar.addWidget(self.edit_mode)
        undo=QPushButton('撤销');undo.clicked.connect(self.undo)
        toolbar.addWidget(undo)
        restore=QPushButton('恢复全部');restore.clicked.connect(self.restore_elements)
        toolbar.addWidget(restore)
        toolbar.addStretch()
        right_layout.addLayout(toolbar)
        self.preview=Preview();self.preview.picked.connect(self.pick)
        right_layout.addWidget(self.preview,1)
        self.selection_row=QWidget()
        selection=QHBoxLayout(self.selection_row);selection.setContentsMargins(0,0,0,0)
        self.selection_label=QLabel()
        selection.addWidget(self.selection_label)
        recolor=QPushButton('线条颜色');recolor.clicked.connect(self.recolor)
        selection.addWidget(recolor)
        self.selected_width=QDoubleSpinBox();self.selected_width.setRange(.1,80)
        self.selected_width.setPrefix('粗细 ')
        self.selected_width.valueChanged.connect(self.rewidth)
        selection.addWidget(self.selected_width)
        remove=QPushButton('删除此线');remove.clicked.connect(self.remove_selected)
        selection.addWidget(remove)
        advanced=QPushButton('填充 / 批量删除');advanced.clicked.connect(self.contour_options)
        selection.addWidget(advanced)
        right_layout.addWidget(self.selection_row)
        self.selection_row.hide()
        self.status=QLabel('滚轮缩放；拖动画布。透明区域以棋盘格显示。')
        self.status.setWordWrap(True);self.status.setObjectName('mutedLabel')
        right_layout.addWidget(self.status)
        split.addWidget(right);split.setStretchFactor(1,1)
        split.setSizes([310,620]);layout.addWidget(split,1)
        actions=QHBoxLayout()
        reset=QPushButton('恢复默认');reset.clicked.connect(self.reset)
        actions.addWidget(reset)
        self.tile_button=QPushButton('导出重复单元…');self.tile_button.clicked.connect(lambda:self.export('tile'))
        actions.addWidget(self.tile_button)
        actions.addStretch()
        copy=QPushButton('复制 SVG');copy.clicked.connect(self.copy_svg)
        actions.addWidget(copy)
        svg=QPushButton('导出 SVG…');svg.clicked.connect(lambda:self.export('svg'))
        actions.addWidget(svg)
        png=QPushButton('导出 PNG…');png.setObjectName('primaryButton');png.clicked.connect(lambda:self.export('png'))
        actions.addWidget(png)
        layout.addLayout(actions)
        self.stack.addWidget(self.editor)
        root.addWidget(self.stack,1)
        self.mode.currentIndexChanged.connect(self.switch)
        last=config.settings().value('graphics/mode','legacy',type=str)
        idx=self.mode.findData(last)
        self.mode.setCurrentIndex(max(0,idx))
        if self.kind is None: self.switch()

    def switch(self):
        if self.kind and not self._loading: self.save()
        self.timer.stop()
        self.kind=self.mode.currentData()
        config.settings().setValue('graphics/mode',self.kind)
        self.history=[];self.selected=None;self.selection_row.hide()
        if self.kind=='legacy':
            if self.legacy is None:
                from ..widget import LegacyDotPatternTool
                self.legacy=LegacyDotPatternTool()
                # Long legacy form remains usable in smaller windows.
                area=QScrollArea();area.setWidgetResizable(True);area.setWidget(self.legacy)
                self.legacy_layout.addWidget(area)
            self.stack.setCurrentIndex(0)
            self._loading=False
            return
        self.stack.setCurrentIndex(1)
        self.build_form()
        self.preview.auto_fit=True
        self.edit_mode.setEnabled(self.kind in EDIT_KINDS)
        self.edit_mode.setCurrentIndex(0)
        self.set_edit_mode(0)
        self.tile_button.setVisible(self.kind in TILE_KINDS)
        self.refresh()

    def build_form(self):
        self._loading=True
        old=self.scroll.takeWidget()
        if old: old.deleteLater()
        pane=QWidget();form=QFormLayout(pane)
        form.setContentsMargins(12,12,12,12);form.setSpacing(9)
        form.setRowWrapPolicy(QFormLayout.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.controls={}
        state=self.states.get(self.kind,{})
        if not isinstance(state,dict): state={}
        values=state.get('values',{})
        self.hidden=set(state.get('hidden',[]));self.styles=state.get('styles',{})
        self.width=QSpinBox();self.width.setRange(16,8192);self.width.setValue(state.get('width',512))
        self.height=QSpinBox();self.height.setRange(16,8192);self.height.setValue(state.get('height',512))
        size=QHBoxLayout();size.addWidget(self.width);size.addWidget(QLabel('×'));size.addWidget(self.height)
        form.addRow('画布尺寸',size)
        self.width.valueChanged.connect(self.changed);self.height.valueChanged.connect(self.changed)
        self.transparent=QCheckBox('透明背景');self.transparent.setChecked(state.get('transparent',True))
        self.transparent.toggled.connect(self.changed);form.addRow(self.transparent)
        self.bg=self.color_button(state.get('background','#ffffffff'))
        form.addRow('背景颜色',self.bg)
        heading=QLabel(CATALOG[self.kind][0]);heading.setObjectName('pageTitle');form.addRow(heading)
        for key,label,default,options,maximum in CATALOG[self.kind][1]:
            value=values.get(key,default)
            if isinstance(default,bool):
                control=QCheckBox();control.setChecked(bool(value));control.toggled.connect(self.changed)
            elif isinstance(options,list):
                control=QComboBox()
                for text,data in options: control.addItem(text,data)
                control.setCurrentIndex(max(0,control.findData(value)))
                control.currentIndexChanged.connect(self.changed)
            elif options=='color': control=self.color_button(value)
            elif options=='file':
                control=QLineEdit(str(value));control.setReadOnly(True);control.setPlaceholderText('未选择')
                row=QHBoxLayout();row.addWidget(control)
                button=QPushButton('选择');button.clicked.connect(lambda checked=False,c=control:self.choose_file(c))
                row.addWidget(button)
                clear=QPushButton('×');clear.setFixedWidth(28);clear.clicked.connect(control.clear);row.addWidget(clear)
                control.textChanged.connect(self.changed)
                self.controls[key]=control;form.addRow(label,row);continue
            elif options=='text':
                control=QLineEdit(str(value));control.setMaxLength(256);control.textChanged.connect(self.changed)
            else:
                control=QSpinBox() if isinstance(default,int) else QDoubleSpinBox()
                if isinstance(control,QDoubleSpinBox):
                    control.setDecimals(3 if key=='frequency' else 2)
                    control.setSingleStep(.002 if key=='frequency' else .1 if maximum<=5 else 1)
                control.setRange(options,maximum)
                try: control.setValue(value)
                except TypeError: control.setValue(default)
                control.valueChanged.connect(self.changed)
            self.controls[key]=control;form.addRow(label,control)
        note=QLabel('参数按图形类型分别保存。\n改变网格间距后，局部编辑仍按单元编号保留。')
        note.setWordWrap(True);note.setObjectName('mutedLabel');form.addRow(note)
        self.scroll.setWidget(pane)
        self._loading=False

    def color_button(self,value):
        button=QPushButton()
        self.set_color(button,value)
        button.clicked.connect(lambda:self.choose_color(button))
        return button

    def set_color(self,button,value):
        color=QColor(value)
        if not color.isValid(): color=QColor('#89b4fa')
        button.setProperty('color',color.name(QColor.HexArgb))
        button.setText(color.name(QColor.HexArgb).upper())
        text='#11111b' if color.lightness()>140 else '#ffffff'
        button.setStyleSheet(f'background-color:{color.name()};color:{text};padding:5px;')

    def choose_color(self,button):
        color=pick_color(QColor(button.property('color')),self,'选择颜色')
        if color.isValid(): self.set_color(button,color.name(QColor.HexArgb));self.changed()

    def choose_file(self,control):
        filename,_=QFileDialog.getOpenFileName(self,'选择本地图片','','图片 (*.png *.svg *.jpg *.jpeg *.webp)')
        if filename: control.setText(filename)

    def values(self):
        values={}
        for key,c in self.controls.items():
            if isinstance(c,QCheckBox): values[key]=c.isChecked()
            elif isinstance(c,QComboBox): values[key]=c.currentData()
            elif isinstance(c,QPushButton): values[key]=c.property('color')
            elif isinstance(c,QLineEdit): values[key]=c.text()
            else: values[key]=c.value()
        return values

    def save(self):
        if self.kind=='legacy' or self._loading: return
        self.states[self.kind]={'values':self.values(),'width':self.width.value(),'height':self.height.value(),
            'transparent':self.transparent.isChecked(),'background':self.bg.property('color'),
            'hidden':sorted(self.hidden),'styles':self.styles}
        config.settings().setValue('graphics/states',json.dumps(self.states,ensure_ascii=False))

    def changed(self,*args):
        if self._loading: return
        self.save();self.timer.start()

    def make_document(self,tile=False):
        p=self.values()
        if tile and self.kind=='matrix': p=p | {'finite':False}
        if tile and self.kind=='symbols': p=p | {'repeat':1,'layout':'single'}
        w,h=tile_size(self.kind,p) if tile else (self.width.value(),self.height.value())
        # Tile edges retain the exact period; the main canvas minimum is unrelated.
        doc=render(self.kind,p,max(16,int(w+0.999)),max(16,int(h+0.999)),None if self.transparent.isChecked() else self.bg.property('color'),self.hidden,self.styles)
        if tile:
            dw,dh=max(1,round(w)),max(1,round(h))
            doc.svg=doc.svg.replace(f'width="{doc.width}" height="{doc.height}" viewBox="0 0 {doc.width} {doc.height}"',f'width="{dw}" height="{dh}" viewBox="0 0 {w} {h}"',1)
            doc.width,doc.height=dw,dh
        return doc

    def refresh(self):
        if self.kind=='legacy': return
        try:
            self.document=self.make_document()
            previous=self.preview.renderer
            self.preview.show_document(self.document)
            if previous: previous.deleteLater()
            self.status.setText(f'{CATALOG[self.kind][0]} · {self.document.width} × {self.document.height} · 已隐藏 {len(self.hidden)} 个元素\n滚轮缩放；拖动画布。切换“点选编辑”可增删元素，等高线可单独调整颜色和粗细。')
        except (ValueError,OSError,MemoryError) as exc:
            self.document=None
            self.preview.scene().clear()
            self.status.setText('无法生成：'+str(exc))

    def set_edit_mode(self,index):
        self.preview.edit=index>0 and self.kind in EDIT_KINDS
        self.preview.brush=index in (2,3)
        self.preview.setDragMode(QGraphicsView.NoDrag if self.preview.edit else QGraphicsView.ScrollHandDrag)

    def remember(self):
        self.history.append((set(self.hidden),json.loads(json.dumps(self.styles))))
        self.history=self.history[-50:]

    def pick(self,x,y,brush):
        if not self.document: return
        key=self.document.hit(x,y,8/max(.01,self.preview.transform().m11()))
        if key is None: return
        if self.kind=='contour' and not brush:
            self.selected=key;self.selection_label.setText('等高线 #'+key)
            self.selected_width.blockSignals(True)
            self.selected_width.setValue(self.styles.get(key,{}).get('stroke',self.values()['stroke']))
            self.selected_width.blockSignals(False);self.selection_row.show();return
        restoring=brush and self.edit_mode.currentIndex()==3
        if brush and ((key not in self.hidden) if restoring else (key in self.hidden)): return
        self.remember()
        if key in self.hidden: self.hidden.remove(key)
        else: self.hidden.add(key)
        self.changed()

    def recolor(self):
        if self.selected is None: return
        color=pick_color(QColor(self.styles.get(self.selected,{}).get('color',self.values()['color'])),self,'线条颜色')
        if color.isValid():
            self.remember();self.styles.setdefault(self.selected,{})['color']=color.name(QColor.HexArgb);self.changed()

    def rewidth(self,value):
        if self.selected is not None:
            self.remember();self.styles.setdefault(self.selected,{})['stroke']=value;self.changed()

    def remove_selected(self):
        if self.selected is not None:
            self.remember();self.hidden.add(self.selected);self.changed()

    def toggle_fullscreen(self):
        window=self.window()
        if window.isFullScreen(): window.showNormal()
        else: window.showFullScreen()

    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Escape and self.window().isFullScreen():
            self.window().showNormal();event.accept()
        else: super().keyPressEvent(event)

    def contour_options(self):
        if self.selected is None: return
        dialog=QDialog(self);dialog.setWindowTitle('等高线 #'+self.selected)
        form=QFormLayout(dialog)
        current=self.values() | self.styles.get(self.selected,{})
        fill=QComboBox()
        for label,value in [('无','none'),('纯色','solid'),('波点','dots'),('斜线','hatch')]: fill.addItem(label,value)
        fill.setCurrentIndex(max(0,fill.findData(current['fill_type'])))
        form.addRow('至下一层带状区间',fill)
        ink=QPushButton();self.set_color(ink,current['fill_color'])
        def choose_fill_color():
            color=pick_color(QColor(ink.property('color')),dialog,'填充颜色')
            if color.isValid(): self.set_color(ink,color.name(QColor.HexArgb))
        ink.clicked.connect(choose_fill_color);form.addRow('填充颜色 / 透明度',ink)
        fields={}
        for key,label,low,high in [('fill_spacing','填充间距',4,100),('fill_size','点半径 / 线宽',.5,20),('fill_angle','斜线角度',-90,90),('dash','虚线长度（0 为实线）',0,100)]:
            box=QDoubleSpinBox();box.setRange(low,high);box.setValue(current[key]);fields[key]=box;form.addRow(label,box)
        batch=QComboBox();batch.addItems(['保留所有线','删除编号更小的线','删除编号更大的线'])
        form.addRow('批量操作',batch)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
        if dialog.exec()==QDialog.Accepted:
            self.remember()
            self.styles.setdefault(self.selected,{}).update({key:c.value() for key,c in fields.items()} | {'fill_type':fill.currentData(),'fill_color':ink.property('color')})
            if batch.currentIndex():
                for i in range(1,self.values()['count']+1):
                    if (i<int(self.selected) if batch.currentIndex()==1 else i>int(self.selected)): self.hidden.add(str(i))
            self.changed()

    def undo(self):
        if self.history:
            self.hidden,self.styles=self.history.pop();self.changed()

    def restore_elements(self):
        self.remember();self.hidden.clear();self.styles.clear();self.changed()

    def reset(self):
        self.states.pop(self.kind,None);self.history=[];self.selected=None;self.selection_row.hide()
        self.build_form();self.changed();self.preview.auto_fit=True

    def copy_svg(self):
        try:
            QApplication.clipboard().setText(self.make_document().svg)
            self.status.setText('SVG 代码已复制')
        except (ValueError,OSError,MemoryError) as exc: self.status.setText(str(exc))

    def export(self,format):
        try: document=self.make_document(tile=format=='tile')
        except (ValueError,OSError,MemoryError) as exc:
            QMessageBox.warning(self,'无法导出',str(exc));return
        extension='svg' if format=='svg' else 'png'
        folder=config.settings().value('graphics/export_dir','',type=str)
        filename,_=QFileDialog.getSaveFileName(self,'导出图形',str(Path(folder)/(self.kind+('-tile' if format=='tile' else '')+'.'+extension)),extension.upper()+f' (*.{extension})')
        if not filename: return
        path=Path(filename)
        if path.suffix.lower()!='.'+extension: path=path.with_suffix('.'+extension)
        try:
            if extension=='svg': path.write_text(document.svg,encoding='utf-8')
            elif not rasterize(document).save(str(path),'PNG'): raise OSError('无法写入 PNG 文件')
            config.settings().setValue('graphics/export_dir',str(path.parent))
            self.status.setText('已导出：'+str(path))
        except (OSError,ValueError,MemoryError) as exc: QMessageBox.warning(self,'导出失败',str(exc))
