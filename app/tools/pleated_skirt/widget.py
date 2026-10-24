"""Independent native pleated skirt texture editor."""
import json
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QGraphicsItem, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget)
from app import config
from app.tools.base_tool import BaseTool
from app.widgets.color_picker import pick_color
from . import Band, PlaidParams, render_svg, from_dict, to_dict, REFERENCE_PRESET, REFERENCE_PRESET_NAME
from .presets import PRESETS, PRESET_BY_KEY


class CachedWeaveItem(QGraphicsItem):
    """One native-resolution tile, shared by every on-screen repetition."""
    def __init__(self, pixmap, width, height):
        super().__init__()
        self.pixmap = pixmap
        self.bounds = QRectF(0, 0, width, height)

    def boundingRect(self):
        return self.bounds

    def paint(self, painter, option, widget=None):
        # Keep the discrete weave cells sharp when magnified; filter minification.
        painter.setRenderHint(QPainter.SmoothPixmapTransform, abs(painter.transform().m11()) < 1)
        painter.drawTiledPixmap(self.bounds, self.pixmap)


class PleatPreview(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setMinimumSize(240,240)
        tile=QPixmap(24,24);tile.fill(QColor('#313244'))
        painter=QPainter(tile)
        painter.fillRect(0,0,12,12,QColor('#45475a'));painter.fillRect(12,12,12,12,QColor('#45475a'));painter.end()
        self.setBackgroundBrush(QBrush(tile))
        self.renderer=None
        self._cached_svg=None
        self._tile=None
        self._item=None
        self.auto_fit=True

    def show_svg(self, svg, width, height):
        # The input describes one seamless unit, not the repeated output canvas.
        # Changing repetition counts reuses the same cache, just like zoom/pan.
        if svg != self._cached_svg:
            renderer=QSvgRenderer(QByteArray(svg.encode()),self)
            if not renderer.isValid():
                renderer.deleteLater()
                raise ValueError('SVG 渲染失败')
            image=QImage(renderer.defaultSize(),QImage.Format_ARGB32_Premultiplied)
            if image.isNull():
                renderer.deleteLater()
                raise ValueError('预览过大，内存不足')
            image.fill(0)
            painter=QPainter(image)
            try:renderer.render(painter)
            finally:painter.end()
            pixmap=QPixmap.fromImage(image)
            if pixmap.isNull():
                renderer.deleteLater()
                raise ValueError('无法创建预览缓存')
            if self.renderer:self.renderer.deleteLater()
            self.renderer=renderer
            self._tile=pixmap
            self._cached_svg=svg
        self.scene().clear()
        self._item=CachedWeaveItem(self._tile,width,height)
        self.scene().addItem(self._item)
        self.setSceneRect(QRectF(0,0,width,height))
        if self.auto_fit: self.fit()

    def fit(self):
        self.auto_fit=True
        self.fitInView(self.sceneRect(),Qt.KeepAspectRatio)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.auto_fit: self.fit()

    def wheelEvent(self,event):
        delta=event.angleDelta().y() or event.pixelDelta().y()
        if not delta:
            event.ignore();return
        factor=1.2 ** max(-3,min(3,delta/120))
        if .01 < self.transform().m11()*factor < 40:
            self.auto_fit=False;self.scale(factor,factor)
        event.accept()


class BandEditor(QWidget):
    def __init__(self, changed, parent=None):
        super().__init__(parent)
        self.changed=changed
        layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        self.table=QTableWidget(0,2)
        self.table.setHorizontalHeaderLabels(['颜色（点击选择）','线数'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setMinimumHeight(210)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setStyleSheet('QTableWidget::item { padding: 0px; }')
        layout.addWidget(self.table)
        buttons=QHBoxLayout();layout.addLayout(buttons)
        for label,callback in [('添加',self.add),('删除',self.remove),('上移',lambda:self.move(-1)),('下移',lambda:self.move(1))]:
            button=QPushButton(label);button.clicked.connect(callback);buttons.addWidget(button)

    def bands(self):
        return tuple(Band(self.table.cellWidget(i,0).property('color'),self.table.cellWidget(i,1).value()) for i in range(self.table.rowCount()))

    def set_bands(self,bands):
        self.table.setRowCount(0)
        for band in bands:
            row=self.table.rowCount();self.table.insertRow(row)
            color=QPushButton();self.paint_color(color,band.color)
            color.clicked.connect(lambda checked=False,c=color:self.pick(c))
            count=QSpinBox();count.setRange(1,512);count.setValue(band.threads);count.setKeyboardTracking(False)
            count.valueChanged.connect(self.changed)
            self.table.setCellWidget(row,0,color);self.table.setCellWidget(row,1,count)
        if bands:self.table.selectRow(0)

    @staticmethod
    def paint_color(button,color):
        button.setProperty('color',color);button.setText(color.upper())
        text='#11111b' if QColor(color).lightness()>140 else '#ffffff'
        button.setStyleSheet(f'background:{color};color:{text};padding:4px;')

    def pick(self,button):
        color=pick_color(QColor(button.property('color')),self,allow_alpha=False)
        if color.isValid():self.paint_color(button,color.name(QColor.HexRgb));self.changed()

    def add(self):
        bands=list(self.bands())
        if len(bands)>=64:return
        row=self.table.currentRow()+1 if self.table.currentRow()>=0 else len(bands)
        bands.insert(row,Band('#f4edce',8));self.set_bands(bands);self.table.selectRow(row);self.changed()

    def remove(self):
        row=self.table.currentRow();bands=list(self.bands())
        if row<0 or len(bands)<=1:return
        bands.pop(row);self.set_bands(bands);self.table.selectRow(min(row,len(bands)-1));self.changed()

    def move(self,delta):
        row=self.table.currentRow();target=row+delta;bands=list(self.bands())
        if row<0 or not 0<=target<len(bands):return
        bands[row],bands[target]=bands[target],bands[row]
        self.set_bands(bands);self.table.selectRow(target);self.changed()


class PleatedSkirtTool(BaseTool):
    tool_id='pleated_skirt'
    tool_name='裙子格纹生成器'
    tool_description='生成斜纹交织结构，按经纬色带规则生成格纹基础色贴图'

    def __init__(self,parent=None):
        super().__init__(parent)
        self.loading=True
        self.controls={}
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(120);self.timer.timeout.connect(self.refresh)
        root=QVBoxLayout(self)
        title=QLabel(self.tool_name);title.setObjectName('pageTitle');root.addWidget(title)
        hint=QLabel('① 生成黑白斜纹交织结构 → ② 按纵向经线、横向纬线的色带规则着色。交点显示上层线的颜色，输出平面基础色贴图。')
        hint.setObjectName('mutedLabel');hint.setWordWrap(True);root.addWidget(hint)
        split=QSplitter();root.addWidget(split,1)
        side=QWidget();side.setMinimumWidth(350);side.setMaximumWidth(460)
        left=QVBoxLayout(side);left.setContentsMargins(0,0,8,0)
        preset_row=QHBoxLayout()
        self.preset_combo=QComboBox()
        self.preset_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.preset_combo.setMinimumContentsLength(12)
        for preset in PRESETS:
            self.preset_combo.addItem(preset.name,preset.key)
            self.preset_combo.setItemData(self.preset_combo.count()-1,preset.description,Qt.ToolTipRole)
        preset_row.addWidget(self.preset_combo,1)
        apply_preset=QPushButton('应用预设');apply_preset.clicked.connect(self.apply_preset)
        preset_row.addWidget(apply_preset);left.addLayout(preset_row)
        self.preset_note=QLabel();self.preset_note.setWordWrap(True);self.preset_note.setObjectName('mutedLabel')
        left.addWidget(self.preset_note)
        self.preset_combo.currentIndexChanged.connect(self.describe_preset)
        self.describe_preset()
        form=QFormLayout();left.addLayout(form)
        for key,label,low,high in [('thread_size','每根线宽度（px）',1,16),('over','经线在上：连续线数',1,8),('under','纬线在上：连续线数',1,8),('repeats_x','横向重复单元数',1,8),('repeats_y','纵向重复单元数',1,8)]:
            control=QSpinBox();control.setRange(low,high);control.setKeyboardTracking(False)
            control.valueChanged.connect(self.changed);self.controls[key]=control;form.addRow(label,control)
        reverse=QCheckBox('反向斜纹');reverse.toggled.connect(self.changed);self.controls['reverse']=reverse;form.addRow(reverse)
        self.linked=QCheckBox('横向与纵向使用相同色带规则');self.linked.toggled.connect(self.link_changed);left.addWidget(self.linked)
        self.tabs=QTabWidget();left.addWidget(self.tabs,1)
        self.warp=BandEditor(self.changed);self.weft=BandEditor(self.changed)
        self.tabs.addTab(self.warp,'纵向经线（从左到右）');self.tabs.addTab(self.weft,'横向纬线（从上到下）')
        note=QLabel('按列表顺序循环；线数决定色带宽度。交织默认 2 上 / 2 下。为保证无缝，单元尺寸取色带周期与交织周期的最小公倍数。')
        note.setWordWrap(True);note.setObjectName('mutedLabel');left.addWidget(note)
        split.addWidget(side)
        right=QWidget();layout=QVBoxLayout(right);layout.setContentsMargins(4,0,0,0)
        toolbar=QHBoxLayout();layout.addLayout(toolbar)
        self.stage=QComboBox();self.stage.addItem('① 黑白斜纹结构','structure');self.stage.addItem('② 按规则着色','color');self.stage.setCurrentIndex(1)
        self.stage.currentIndexChanged.connect(self.changed);toolbar.addWidget(self.stage)
        fit=QPushButton('适应画布');fit.clicked.connect(lambda:self.preview.fit());toolbar.addWidget(fit);toolbar.addStretch()
        self.preview=PleatPreview();layout.addWidget(self.preview,1)
        self.status=QLabel();self.status.setWordWrap(True);self.status.setObjectName('mutedLabel');layout.addWidget(self.status)
        split.addWidget(right);split.setStretchFactor(1,1);split.setSizes([390,710])
        actions=QHBoxLayout();root.addLayout(actions)
        for label,callback in [('恢复参考预设',self.reset),('导入规则…',self.import_rules),('保存规则…',self.export_rules)]:
            button=QPushButton(label);button.clicked.connect(callback);actions.addWidget(button)
            if label=='恢复参考预设':
                button.setToolTip('载入之前展示的格纹：配色、色带顺序及线数、2 上 / 2 下交织、2 px 线宽、经纬同步。')
        actions.addStretch()
        self.tile_button=QPushButton('导出无缝单元 PNG…');self.tile_button.clicked.connect(lambda:self.export('png',True));actions.addWidget(self.tile_button)
        for extension in ('svg','png'):
            button=QPushButton('导出当前阶段 '+extension.upper()+'…')
            if extension=='png':button.setObjectName('primaryButton')
            button.clicked.connect(lambda checked=False,e=extension:self.export(e));actions.addWidget(button)
        p=PlaidParams();linked=True
        try:
            data=json.loads(config.settings().value('plaid/rules','{}',type=str))
            if data:p=from_dict(data);linked=bool(data.get('linked',p.warp==p.weft))
        except (ValueError,KeyError,TypeError,AttributeError):pass
        self.load_params(p,linked)

    def params(self):
        values={key:(control.isChecked() if isinstance(control,QCheckBox) else control.value()) for key,control in self.controls.items()}
        return PlaidParams(warp=self.warp.bands(),weft=self.warp.bands() if self.linked.isChecked() else self.weft.bands(),**values)

    def load_params(self,p,linked):
        self.loading=True
        for key,control in self.controls.items():
            if isinstance(control,QCheckBox):control.setChecked(getattr(p,key))
            else:control.setValue(getattr(p,key))
        self.warp.set_bands(p.warp);self.weft.set_bands(p.weft);self.linked.setChecked(linked)
        self.tabs.setTabEnabled(1,not linked)
        self.loading=False;self.preview.auto_fit=True;self.refresh()

    def link_changed(self,checked):
        if self.loading:return
        self.weft.set_bands(self.warp.bands())
        self.tabs.setTabEnabled(1,not checked)
        if checked:self.tabs.setCurrentIndex(0)
        self.changed()

    def changed(self,*args):
        if not self.loading:self.timer.start()

    def refresh(self):
        try:
            p=self.params();tw,th=p.dimensions()
            if tw*p.repeats_x>8192 or th*p.repeats_y>8192:
                raise ValueError('重复后的输出超出 8192 px，请减少线数、线宽或重复次数')
            svg=render_svg(p,self.stage.currentData(),tile=True)
            self.preview.show_svg(svg,tw*p.repeats_x,th*p.repeats_y)
            config.settings().setValue('plaid/rules',json.dumps(to_dict(p)|{'linked':self.linked.isChecked()}))
            self.status.setText(f'无缝单元 {tw} × {th} px · 输出 {tw*p.repeats_x} × {th*p.repeats_y} px\n黑色位置取经线颜色，白色位置取纬线颜色；滚轮缩放查看交织细节。')
        except (ValueError,TypeError) as exc:
            self.preview.scene().clear();self.status.setText('无法生成：'+str(exc))

    def reset(self):
        self.preset_combo.setCurrentIndex(self.preset_combo.findData('reference'))
        self.apply_preset()

    def describe_preset(self,*args):
        self.preset_note.setText(PRESET_BY_KEY[self.preset_combo.currentData()].description)

    def apply_preset(self):
        preset=PRESET_BY_KEY[self.preset_combo.currentData()]
        self.timer.stop()
        self.stage.setCurrentIndex(1)
        self.load_params(preset.params,preset.params.warp==preset.params.weft)
        self.status.setText(self.status.text()+'\n已载入预设：'+preset.name)

    def save_image(self,path,extension,tile=False):
        p=self.params();svg=render_svg(p,self.stage.currentData(),tile)
        if extension=='svg':Path(path).write_text(svg,encoding='utf-8');return
        tw,th=p.dimensions();w,h=(tw,th) if tile else (tw*p.repeats_x,th*p.repeats_y)
        image=QImage(w,h,QImage.Format_ARGB32_Premultiplied)
        if image.isNull():raise ValueError('图片过大，内存不足')
        image.fill(0);painter=QPainter(image)
        renderer=QSvgRenderer(QByteArray(svg.encode()));renderer.render(painter);painter.end()
        if not image.save(str(path),'PNG'):raise OSError('无法写入图片')

    def export(self,extension,tile=False):
        folder=config.settings().value('plaid/export_dir','',type=str)
        name=('weave' if self.stage.currentData()=='structure' else 'plaid')+('_tile' if tile else '')+'.'+extension
        path,_=QFileDialog.getSaveFileName(self,'导出当前阶段',str(Path(folder)/name),extension.upper()+f' (*.{extension})')
        if not path:return
        dest=Path(path)
        if dest.suffix.lower()!='.'+extension:dest=dest.with_suffix('.'+extension)
        try:self.save_image(dest,extension,tile)
        except (ValueError,OSError,MemoryError) as exc:QMessageBox.warning(self,'导出失败',str(exc));return
        config.settings().setValue('plaid/export_dir',str(dest.parent));self.status.setText('已导出：'+str(dest))

    def export_rules(self):
        path,_=QFileDialog.getSaveFileName(self,'保存格纹规则','plaid-rules.json','JSON (*.json)')
        if not path:return
        try:
            p=self.params();render_svg(p)
            Path(path).with_suffix('.json').write_text(json.dumps(to_dict(p)|{'linked':self.linked.isChecked()},ensure_ascii=False,indent=2),encoding='utf-8')
        except (OSError,ValueError) as exc:QMessageBox.warning(self,'保存失败',str(exc))

    def import_rules(self):
        path,_=QFileDialog.getOpenFileName(self,'导入格纹规则','','JSON (*.json)')
        if not path:return
        try:
            if Path(path).stat().st_size>131072:raise ValueError('规则文件超过 128 KB')
            data=json.loads(Path(path).read_text(encoding='utf-8-sig'));p=from_dict(data)
            self.load_params(p,bool(data.get('linked',p.warp==p.weft)))
        except (OSError,ValueError,KeyError,TypeError,AttributeError) as exc:QMessageBox.warning(self,'导入失败',str(exc))
