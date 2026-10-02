# -*- coding: utf-8 -*-
"""
继承自 QTableWidget 的 96/384 孔板交互组件 - PlateWidget
提供拖拽多选与右键标记，并融合 HSL 热图及 selection 剥离选中高亮。
"""

import os
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QMenu, QAbstractItemView, QHeaderView, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QBrush

from models.data_structures import Plate, WellType, Well

class PlateWidget(QTableWidget):
    """
    孔板交互网格组件。
    """
    well_type_changed = pyqtSignal()  # 通知 Controller 更新浓度输入表等

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plate: Plate = None
        self._setup_ui()

    def _setup_ui(self):
        """初始化 UI 样式和交互设置"""
        # 默认 96 孔板配置
        self.setRowCount(8)
        self.setColumnCount(12)

        self.setVerticalHeaderLabels(list("ABCDEFGH"))
        self.setHorizontalHeaderLabels([str(i) for i in range(1, 13)])

        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # 右键菜单
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # 加载样式表
        self._apply_style()

        # 4.1 选中事件剥离机制：绑定选择改变信号
        self.itemSelectionChanged.connect(self._on_selection_changed)

        header_font = QFont("Microsoft YaHei", 9, QFont.Bold)
        self.horizontalHeader().setFont(header_font)
        self.verticalHeader().setFont(header_font)

        # 宽度拉伸填满，行高固定为38px以保证数值与计算结果贴紧，且不产生左下角全白
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.verticalHeader().setDefaultSectionSize(38)

        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

    def _apply_style(self):
        qss_path = os.path.join(os.path.dirname(__file__), "style_xp.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        else:
            self.setStyleSheet("""
                QTableWidget { background-color: #ffffff; gridline-color: #d0d0d0; }
                QTableWidget::item:selected { background-color: #000080; color: #ffffff; }
            """)

    def _on_selection_changed(self):
        """
        4.1 选中事件剥离机制：
        单元格选中时：前景色白色 #FFFFFF，清空背景 Brush，允许 QSS 深蓝高亮显露。
        单元格取消选中时：恢复前景色黑色 #000000，并重新计算赋予 HSL 热图背景。
        """
        if self.plate is None:
            return
        self.blockSignals(True)
        try:
            for r in range(self.rowCount()):
                for c in range(self.columnCount()):
                    item = self.item(r, c)
                    if item is None:
                        continue
                    row_label = self.plate.row_labels[r]
                    well = self.plate.get_well(row_label, c + 1)
                    if well is None:
                        continue

                    if item.isSelected():
                        item.setBackground(QBrush()) # 清空背景 Brush，释放给系统 QSS 深蓝选中色
                        item.setForeground(QBrush(QColor("#FFFFFF")))
                    else:
                        bg_color = self._get_heatmap_color(well)
                        item.setBackground(QBrush(bg_color))
                        item.setForeground(QBrush(QColor("#000000")))
        finally:
            self.blockSignals(False)

    def load_plate(self, plate: Plate):
        """将 Plate 对象数据渲染到表格中"""
        self.plate = plate
        self.setRowCount(self.plate.rows)
        self.setColumnCount(self.plate.cols)
        self.setVerticalHeaderLabels(self.plate.row_labels)
        self.setHorizontalHeaderLabels([str(i) for i in range(1, self.plate.cols + 1)])

        # 宽度拉伸填满，行高固定为38px
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.verticalHeader().setDefaultSectionSize(38)

        self._refresh_all_cells()

    def _get_heatmap_color(self, well: Well) -> QColor:
        """根据孔位类型和OD净值计算HSL柔和热图色 (亮度180-240)"""
        if self.plate is None or well is None:
            return QColor("#ffffff")

        if well.well_type == WellType.UNUSED:
            return QColor("#ffffff")

        if well.raw_value is None:
            # 仅有类型无数据，显示极淡基色以作区分
            default_colors = {
                WellType.BLANK:    QColor("#f2f2f2"),
                WellType.STANDARD: QColor("#fff2f2"),
                WellType.SAMPLE:   QColor("#f0f4ff"),
                WellType.CONTROL:  QColor("#f0fff0"),
                WellType.CUSTOM:   QColor("#fffaf0"),
            }
            return default_colors.get(well.well_type, QColor("#ffffff"))

        # 收集板上所有有值孔（除 Unused 以外）的最大和最小值
        all_vals = [w.corrected_value for w in self.plate.all_wells()
                    if w.raw_value is not None and w.well_type != WellType.UNUSED]

        min_val = min(all_vals) if all_vals else 0.0
        max_val = max(all_vals) if all_vals else 1.0
        val_range = max_val - min_val
        if val_range < 1e-5:
            val_range = 1.0

        ratio = (well.corrected_value - min_val) / val_range
        ratio = max(0.0, min(1.0, ratio)) # 限制在 0-1

        # 根据不同的类型计算对应的柔和热图
        if well.well_type == WellType.STANDARD:
            s_val = 150
            l_val = int(240 - ratio * 45) # 240(极浅红) -> 195(中浅红色)
            return QColor.fromHsl(0, s_val, l_val)
        elif well.well_type == WellType.SAMPLE:
            s_val = 160
            l_val = int(240 - ratio * 40) # 240(极浅蓝) -> 200(中浅蓝色)
            return QColor.fromHsl(210, s_val, l_val)
        elif well.well_type == WellType.CONTROL:
            s_val = 150
            l_val = int(240 - ratio * 40) # 240(极浅绿) -> 200(中浅绿色)
            return QColor.fromHsl(120, s_val, l_val)
        elif well.well_type == WellType.CUSTOM:
            s_val = 150
            l_val = int(240 - ratio * 40) # 240(极浅橙) -> 200(中浅橙色)
            return QColor.fromHsl(35, s_val, l_val)
        elif well.well_type == WellType.BLANK:
            l_val = int(240 - ratio * 35) # 240(极浅灰) -> 205(中灰色)
            return QColor.fromHsl(0, 0, l_val)

        return QColor("#ffffff")

    def _get_well_prefix(self, well: Well) -> str:
        """中文前缀，实现直观的可视化识别，并支持 Sample 复孔组 ID 表示"""
        if well.well_type == WellType.BLANK:
            return "空: "
        elif well.well_type == WellType.STANDARD:
            return "标: "
        elif well.well_type == WellType.SAMPLE:
            g_id = well.group_id or "S"
            return f"样({g_id}): "
        elif well.well_type == WellType.CONTROL:
            return "对: "
        elif well.well_type == WellType.CUSTOM:
            return "自: "
        return ""

    def _refresh_all_cells(self):
        """全量刷新所有单元格的显示"""
        if self.plate is None:
            return

        cell_font = QFont("Consolas", 8)

        for r_idx, row_label in enumerate(self.plate.row_labels):
            for c_idx in range(1, self.plate.cols + 1):
                well = self.plate.get_well(row_label, c_idx)
                if well is None:
                    continue

                prefix = self._get_well_prefix(well)
                if well.raw_value is not None:
                    text = f"{prefix}{well.raw_value:.3f}"
                else:
                    text = prefix.rstrip(": ")

                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                item.setFont(cell_font)

                # 4.1 选中事件剥离动态判定
                if item.isSelected():
                    item.setBackground(QBrush())
                    item.setForeground(QBrush(QColor("#FFFFFF")))
                else:
                    bg_color = self._get_heatmap_color(well)
                    item.setBackground(QBrush(bg_color))
                    item.setForeground(QBrush(QColor("#000000")))

                self.setItem(r_idx, c_idx - 1, item)

    def refresh_cell(self, row_label: str, col: int):
        """刷新单个孔位的显示"""
        if self.plate is None:
            return
        r_idx = self.plate.row_labels.index(row_label)
        c_idx = col - 1
        well = self.plate.get_well(row_label, col)
        if well is None:
            return

        prefix = self._get_well_prefix(well)
        if well.raw_value is not None:
            text = f"{prefix}{well.raw_value:.3f}"
        else:
            text = prefix.rstrip(": ")

        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setFont(QFont("Consolas", 8))

        if item.isSelected():
            item.setBackground(QBrush())
            item.setForeground(QBrush(QColor("#FFFFFF")))
        else:
            bg_color = self._get_heatmap_color(well)
            item.setBackground(QBrush(bg_color))
            item.setForeground(QBrush(QColor("#000000")))

        self.setItem(r_idx, c_idx, item)

    def update_results(self):
        """计算完成后更新显示（在OD值下方显示计算结果，强制纯黑前景色）"""
        if self.plate is None:
            return
        cell_font = QFont("Consolas", 7)

        for r_idx, row_label in enumerate(self.plate.row_labels):
            for c_idx in range(1, self.plate.cols + 1):
                well = self.plate.get_well(row_label, c_idx)
                if well is None:
                    continue

                prefix = self._get_well_prefix(well)
                lines = []
                if well.raw_value is not None:
                    lines.append(f"{prefix}{well.raw_value:.3f}")
                else:
                    if prefix:
                        lines.append(prefix.rstrip(": "))

                # 写入计算结果，支持 float 与 str (如 >Max, <Min 等极限拦截)
                if well.calc_result is not None:
                    if isinstance(well.calc_result, float):
                        lines.append(f"->{well.calc_result:.3f}")
                    else:
                        lines.append(f"->{well.calc_result}")

                text = "\n".join(lines)
                item = self.item(r_idx, c_idx - 1)
                if item is None:
                    item = QTableWidgetItem()
                    self.setItem(r_idx, c_idx - 1, item)

                item.setText(text)
                item.setTextAlignment(Qt.AlignCenter)
                item.setFont(cell_font)

                # 4.1 选中事件剥离动态判定
                if item.isSelected():
                    item.setBackground(QBrush())
                    item.setForeground(QBrush(QColor("#FFFFFF")))
                else:
                    bg_color = self._get_heatmap_color(well)
                    item.setBackground(QBrush(bg_color))
                    item.setForeground(QBrush(QColor("#000000")))

    def _show_context_menu(self, pos):
        """弹出右键菜单，允许标记孔位类型"""
        if not self.selectedItems():
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #e1e1e1; border: 1px solid #808080; }
            QMenu::item { padding: 4px 20px; color: #000000; }
            QMenu::item:selected { background-color: #000080; color: #ffffff; }
        """)

        menu.addAction("标记为 Blank", lambda: self._set_selected_wells_type(WellType.BLANK))
        menu.addAction("标记为 Standard", lambda: self._set_selected_wells_type(WellType.STANDARD))
        menu.addAction("标记为 Sample", lambda: self._set_selected_wells_type(WellType.SAMPLE))
        menu.addAction("标记为 Control", lambda: self._set_selected_wells_type(WellType.CONTROL))
        menu.addAction("标记为 Custom", lambda: self._set_selected_wells_type(WellType.CUSTOM))
        menu.addSeparator()
        menu.addAction("设为 未使用 (Unused)", lambda: self._set_selected_wells_type(WellType.UNUSED))

        menu.exec_(self.mapToGlobal(pos))

    def _generate_next_group_id(self) -> str:
        """生成下一个可用的样品组 ID，确保递增不冲突"""
        if self.plate is None:
            return "S1"
        existing_ids = set()
        for well in self.plate.all_wells():
            if well.well_type == WellType.SAMPLE and well.group_id:
                existing_ids.add(well.group_id)

        nums = []
        for g_id in existing_ids:
            if g_id.startswith("S"):
                try:
                    nums.append(int(g_id[1:]))
                except ValueError:
                    pass
        next_num = max(nums) + 1 if nums else 1
        return f"S{next_num}"

    def _set_selected_wells_type(self, well_type: WellType):
        """将当前选中孔设为指定类型，并处理复孔样品自动分组"""
        if self.plate is None:
            return

        # 2. 交互逻辑升级：如果设为 Sample，自动为本次选中所有孔分配同一个 group_id
        group_id = ""
        if well_type == WellType.SAMPLE:
            group_id = self._generate_next_group_id()

        for item in self.selectedItems():
            r = item.row()
            c = item.column()
            row_label = self.plate.row_labels[r]
            well = self.plate.get_well(row_label, c + 1)
            if well:
                well.well_type = well_type
                if well_type == WellType.SAMPLE:
                    well.group_id = group_id
                else:
                    well.group_id = ""  # 其它非 Sample 类型自动清空 ID

        self._refresh_all_cells()
        self.well_type_changed.emit()
