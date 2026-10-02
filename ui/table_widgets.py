# -*- coding: utf-8 -*-
"""
表格增强与交互处理组件模块 (table_widgets.py)
继承自 QTableWidget，实现主流数据软件标准复制粘贴支持 (Ctrl+C/Ctrl+V、直接与 Excel 交互)
及平行复孔右键分析、同样本编号求均值处理功能。
特别加强：锁死表格默认有效列数，从外部第三方电子表粘贴时遇到超长列直接舍弃溢出区域，严防表框混乱与冗余！
"""

import numpy as np
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QMenu, QMessageBox, QApplication, QHeaderView, QAbstractItemView
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QBrush, QKeySequence

from core.clipboard_utils import parse_clipboard_text, format_to_clipboard_text


class BaseCustomTableWidget(QTableWidget):
    """
    通用实验数据表格基础组件
    具备完整的系统剪贴板双向兼容处理逻辑，并严格锁定基本操作列宽。
    """
    def __init__(self, rows: int, cols: int, parent=None):
        super().__init__(rows, cols, parent)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

        # 开启右键菜单响应
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_custom_context_menu)

        self._color_reset_timers = []

    def keyPressEvent(self, event):
        """捕获常用组合按键，保障与第三方办公软件 (如 Excel, WPS) 之间的复制粘贴兼容性"""
        if event.matches(QKeySequence.Paste):
            self.paste_from_clipboard(show_info_if_empty=False)
        elif event.matches(QKeySequence.Copy):
            self.copy_to_clipboard()
        elif event.matches(QKeySequence.Delete):
            self.clear_selected_contents()
        else:
            super().keyPressEvent(event)

    def copy_to_clipboard(self):
        """将选中的矩形单元格区域格式化为带有定位占位符的文本并复制到系统剪切板"""
        selected_ranges = self.selectedRanges()
        if not selected_ranges:
            return

        min_row = min(r.topRow() for r in selected_ranges)
        max_row = max(r.bottomRow() for r in selected_ranges)
        min_col = min(r.leftColumn() for r in selected_ranges)
        max_col = max(r.rightColumn() for r in selected_ranges)

        matrix = []
        for r in range(min_row, max_row + 1):
            row_data = []
            for c in range(min_col, max_col + 1):
                item = self.item(r, c)
                if item and item.isSelected():
                    row_data.append(item.text())
                else:
                    row_data.append("")
            matrix.append(row_data)

        clip_str = format_to_clipboard_text(matrix)
        QApplication.clipboard().setText(clip_str)

    def paste_from_clipboard(self, show_info_if_empty: bool = False) -> bool:
        """
        从剪切板读取外部已复制的数据表，并将内容由当前选中格展开填入表格。
        严格锁死既定默认列数：一旦粘贴数据越过本表固定的最右方极限列（溢出列），该溢出部分直接忽略！
        返回 bool：展示本次粘贴是否获取并有效填入了数据。
        """
        clip_str = QApplication.clipboard().text()
        if not clip_str or not clip_str.strip():
            if show_info_if_empty:
                QMessageBox.information(
                    self, "提示",
                    "剪贴板中暂无可用的表格或行列文本。\n\n提示：请先在 Excel、WPS 或是记事本内选定需复制的数据行，然后使用 Ctrl+C 复制，再前来界面通过粘贴 (Ctrl+V) 快速填入。"
                )
            return False

        grid = parse_clipboard_text(clip_str)
        if not grid:
            return False

        curr_item = self.currentItem()
        start_row = curr_item.row() if curr_item else 0
        start_col = curr_item.column() if curr_item else 0

        # 行数若不足以承载下沉测定样序列，允许向下滑行增加行
        needed_rows = start_row + len(grid) + 3
        if self.rowCount() < needed_rows:
            self.setRowCount(needed_rows)

        # 核心防破坏规则：绝对不动用 self.setColumnCount(...) 扩展新列！完全死锁原本确立好的基准科研参数宽度
        max_cols = self.columnCount()

        # 展开循环填表，对于超过限定列边的数据一律抛掉！
        for r_idx, row_cells in enumerate(grid):
            for c_idx, val in enumerate(row_cells):
                target_r = start_row + r_idx
                target_c = start_col + c_idx
                if target_c >= max_cols:
                    # 当剪辑贴来更多不需要和不可承受之额外信息属性列，立即丢除直接滤过，绝对不再往右滋生烦心乱空列！
                    continue
                self._set_cell_text(target_r, target_c, val)

        return True

    def clear_selected_contents(self):
        """清空当前所选区域单元格的数据"""
        for item in self.selectedItems():
            item.setText("")

    def _set_cell_text(self, row: int, col: int, text: str, editable: bool = True):
        item = self.item(row, col)
        if not item:
            item = QTableWidgetItem(str(text))
            self.setItem(row, col, item)
        else:
            item.setText(str(text))

        if editable:
            item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        else:
            item.setFlags((item.flags() & ~Qt.ItemIsEditable) | Qt.ItemIsEnabled | Qt.ItemIsSelectable)

    def _on_custom_context_menu(self, pos):
        """构造常规的标准表单操作右键列表"""
        selected_rows = sorted(list(set(item.row() for item in self.selectedItems())))

        menu = QMenu(self)

        action_paste = menu.addAction("粘贴 (Ctrl+V)")
        action_copy = menu.addAction("复制选中区域 (Ctrl+C)")
        menu.addSeparator()

        action_merge = menu.addAction("合并选中的复孔求均值")
        action_cv = menu.addAction("计算选中孔位的变异系数 (CV%)")

        extra_actions = self._add_derived_menu_options(menu)

        menu.addSeparator()
        action_add = menu.addAction("在表格末端添加 5 行")
        action_del = menu.addAction("删除选中的行区")

        action = menu.exec_(self.viewport().mapToGlobal(pos))
        if not action:
            return

        if action == action_paste:
            self.paste_from_clipboard(show_info_if_empty=True)
        elif action == action_copy:
            self.copy_to_clipboard()
        elif action == action_merge:
            self.handle_merge_and_average(selected_rows)
        elif action == action_cv:
            self.handle_show_cv(selected_rows)
        elif action == action_add:
            self.setRowCount(self.rowCount() + 5)
        elif action == action_del:
            self.handle_delete_rows(selected_rows)
        else:
            self._handle_derived_menu_action(action, extra_actions)

    def _add_derived_menu_options(self, menu: QMenu) -> dict:
        return {}

    def _handle_derived_menu_action(self, action, extra: dict):
        pass

    def handle_delete_rows(self, selected_rows: list):
        for r in reversed(selected_rows):
            self.removeRow(r)

    def handle_show_cv(self, selected_rows: list):
        if len(selected_rows) < 2:
            QMessageBox.information(self, "提示", "请至少选择 2 个以上的并行复孔数据行，方可计算分析变异系数。")
            return

        od_idx = self._get_od_column_idx()
        od_vals = []
        for r in selected_rows:
            item = self.item(r, od_idx)
            if item and item.text().strip() != "":
                try:
                    od_vals.append(float(item.text().strip()))
                except ValueError:
                    continue

        if len(od_vals) < 2:
            QMessageBox.warning(self, "提示", "当前选中的范围内有效吸光度数值少于 2 个，无法统计其变异和标准差指标。")
            return

        mean_val = np.mean(od_vals)
        std_val = np.std(od_vals, ddof=1)
        cv_val = (std_val / mean_val) * 100.0 if abs(mean_val) > 1e-12 else 0.0

        info_text = (
            f"【平行复孔统计简报】\n\n"
            f"· 复孔考察总计：{len(od_vals)} 孔\n"
            f"· OD 平均值 (Mean)：{mean_val:.4f}\n"
            f"· 标准抽样误差 (Std)：{std_val:.4f}\n\n"
            f"· 变异系数 (CV%)：{cv_val:.2f}%"
        )

        if cv_val > 15.0:
            info_text += "\n\n⚠️ 提示：变异系数 (CV%) 已超过 15.0% 标准参照边界，表明该组复孔的读数差异偏大，建议排查实验实试过程中是否存有加样不均、未消气泡或其他测试干扰情况。"
            QMessageBox.warning(self, "变异系数过大警示 (CV% > 15%)", info_text)
        else:
            info_text += "\n\n✔ [一致性合格] 该选区的平行复孔变异系数处于 ≤15.0% 的安全参考要求下，表明测定平行一致。"
            QMessageBox.information(self, "平行复孔变异评估表", info_text)

    def _get_od_column_idx(self) -> int:
        return 1

    def handle_merge_and_average(self, selected_rows: list):
        pass

    def _highlight_merged_row(self, row: int):
        """合并操作执行结束后的视觉背景色彩高亮提醒"""
        brush_green = QBrush(QColor(220, 250, 220))
        for c in range(self.columnCount()):
            item = self.item(row, c)
            if not item:
                self._set_cell_text(row, c, "")
                item = self.item(row, c)
            item.setBackground(brush_green)

        timer = QTimer(self)
        timer.setSingleShot(True)
        def _revert_color():
            if row < self.rowCount():
                for col in range(self.columnCount()):
                    if self.item(row, col):
                        self.item(row, col).setBackground(QBrush(QColor(255, 255, 255)))
        timer.timeout.connect(_revert_color)
        timer.start(2000)
        self._color_reset_timers.append(timer)


class StandardTableWidget(BaseCustomTableWidget):
    """
    标准品测定参数表格: 永远严格固定死锁为 2 列: [ 浓度 (X), 吸光度 OD (Y) ]
    """
    def __init__(self, parent=None):
        super().__init__(12, 2, parent)
        self.setHorizontalHeaderLabels(["浓度 (X)", "吸光度 OD (Y)"])

    def _get_od_column_idx(self) -> int:
        return 1

    def handle_merge_and_average(self, selected_rows: list):
        if len(selected_rows) < 2:
            QMessageBox.information(self, "提示", "请选择两个或多个同浓度的标准品记录行，再操作求取均值合并。")
            return

        conc_values = set()
        od_floats = []

        for r in selected_rows:
            item_c = self.item(r, 0)
            c_val = item_c.text().strip() if item_c else ""
            if c_val != "":
                conc_values.add(c_val)

            item_o = self.item(r, 1)
            o_val = item_o.text().strip() if item_o else ""
            if o_val != "":
                try:
                    od_floats.append(float(o_val))
                except ValueError:
                    continue

        if len(conc_values) > 1:
            QMessageBox.warning(self, "操作禁止", f"您当前选择合并不具有统一浓度的未知项集：{list(conc_values)}。请确保选中合并区域属于相同标准密度的复孔读值。")
            return

        if not od_floats:
            QMessageBox.warning(self, "缺少吸光度", "当前选中范围内没有任何可被识别求算的的数值序列。")
            return

        mean_od = np.mean(od_floats)
        first_row = selected_rows[0]
        self._set_cell_text(first_row, 1, f"{mean_od:.4f}")

        for r in reversed(selected_rows[1:]):
            self.removeRow(r)

        self._highlight_merged_row(first_row)

    def get_valid_standard_data(self):
        stds = []
        for r in range(self.rowCount()):
            item_x = self.item(r, 0)
            item_y = self.item(r, 1)
            if not item_x or not item_y:
                continue
            str_x = item_x.text().strip()
            str_y = item_y.text().strip()
            if str_x == "" or str_y == "":
                continue
            try:
                x_val = float(str_x)
                y_val = float(str_y)
                stds.append((x_val, y_val, r))
            except ValueError:
                continue
        return stds

    def load_demo_data(self):
        """导入标准的理化实验散列表"""
        demo = [
            ("1.0", "0.062"),
            ("5.0", "0.245"),
            ("10.0", "0.435"),
            ("25.0", "0.932"),
            ("50.0", "1.560"),
            ("100.0", "2.185"),
            ("250.0", "2.685"),
            ("500.0", "2.890"),
        ]
        self.setRowCount(len(demo) + 4)
        for r, (x, y) in enumerate(demo):
            self._set_cell_text(r, 0, x)
            self._set_cell_text(r, 1, y)


class SampleTableWidget(BaseCustomTableWidget):
    """
    样口测值录用台: 永远严格死锁不变为 3 列: [ 样本编号, 吸光度 OD (Y), 计算浓度 (X) ]
    """
    def __init__(self, parent=None):
        super().__init__(22, 3, parent)
        self.setHorizontalHeaderLabels(["样本编号", "吸光度 OD (Y)", "计算浓度 (X)"])

    def _get_od_column_idx(self) -> int:
        return 1

    def _add_derived_menu_options(self, menu: QMenu) -> dict:
        menu.addSeparator()
        action_auto = menu.addAction("相同样本编号求均值")
        return {"auto_merge": action_auto}

    def _handle_derived_menu_action(self, action, extra: dict):
        if action == extra.get("auto_merge"):
            self.run_auto_merge_identical_ids(show_dialog=True)

    def run_auto_merge_identical_ids(self, show_dialog: bool = True) -> bool:
        """
        顺扫样本全列，自动把享有同样样本称号、不空置名称的多对试验读数均值回归保留一列。
        对超出合拍规限变异度进行变异分析服务。
        """
        merged_groups = []
        group_map = {}
        total_raw_valid = 0

        for r in range(self.rowCount()):
            item_y = self.item(r, 1)
            if not item_y or item_y.text().strip() == "":
                continue
            try:
                val_y = float(item_y.text().strip())
            except ValueError:
                continue

            total_raw_valid += 1
            item_id = self.item(r, 0)
            s_id = item_id.text().strip() if item_id else ""

            # 完全不提供称别的留空位属于个人独立试验孔位，不可错归同一系列求并
            if s_id != "" and s_id in group_map:
                idx = group_map[s_id]
                merged_groups[idx][1].append(val_y)
                merged_groups[idx][2].append(r)
            else:
                if s_id != "":
                    group_map[s_id] = len(merged_groups)
                merged_groups.append([s_id, [val_y], [r]])

        duplicates_found = any(len(ods) > 1 for _, ods, _ in merged_groups)
        if not duplicates_found:
            if show_dialog:
                QMessageBox.information(self, "扫描提示", "完成对当前全部测量读数孔区的扫描检索，确认所有被指定的编号皆各不相同为单一独立测点，当前表中无复孔行合并需求。")
            return False

        merged_count = 0
        high_cv_warnings = []
        new_rows_data = []

        for s_id, ods, r_indices in merged_groups:
            mean_od = np.mean(ods)
            was_merged = len(ods) > 1
            if was_merged:
                merged_count += (len(ods) - 1)
                std_val = np.std(ods, ddof=1)
                cv_val = (std_val / mean_od) * 100.0 if abs(mean_od) > 1e-12 else 0.0
                if cv_val > 15.0:
                    high_cv_warnings.append((s_id, cv_val, mean_od, len(ods)))
            new_rows_data.append((s_id, f"{mean_od:.4f}", was_merged))

        self.clearContents()
        needed_size = max(len(new_rows_data) + 6, 20)
        self.setRowCount(needed_size)

        for r_idx, (sid, od_str, was_merged) in enumerate(new_rows_data):
            self._set_cell_text(r_idx, 0, sid)
            self._set_cell_text(r_idx, 1, od_str)
            self._set_cell_text(r_idx, 2, "", editable=False)
            if was_merged:
                self._highlight_merged_row(r_idx)

        if show_dialog:
            msg = (
                "【同样品编号去复均和结果报道】\n\n"
                f"· 初始化统计记录： 共计 {total_raw_valid} 列实验项读数\n"
                f"· 已合并重复试验位： 共 {merged_count} 条同样本冗余项\n"
                f"· 当前保留独立记录： 保留 {len(new_rows_data)} 组样本项\n"
            )
            if high_cv_warnings:
                msg += "\n⚠️ 特殊说明：检测到以下重样序列之间的实量变异系数过大 (CV% > 15.0%)：\n"
                for warn_id, cv, w_mean, w_cnt in high_cv_warnings:
                    msg += f" - [编号: {warn_id}] ({w_cnt} 孔均值 {w_mean:.4f}): CV% = {cv:.2f}%\n"
                msg += "\n提示：如对偏大偏差结果存有困惑，可在原始读数里检查并剔除实验异常极值再重绘。"
                QMessageBox.warning(self, "不同样本同序号合归明细函提示", msg)
            else:
                msg += "\n· 质量判定： 所有发生并取平均值的相同同一样品测试内部差强平整，全项 CV% 变异处于标准设定以内（均 ≤15.0%）。"
                QMessageBox.information(self, "同编号一样品求取收约总和结论", msg)

        return True

    def handle_merge_and_average(self, selected_rows: list):
        if len(selected_rows) < 2:
            QMessageBox.information(self, "提示", "请按需拉选最少 2 组以上的样本待检行列方能够操作复孔求和化整。")
            return

        od_floats = []
        for r in selected_rows:
            item_o = self.item(r, 1)
            o_val = item_o.text().strip() if item_o else ""
            if o_val != "":
                try:
                    od_floats.append(float(o_val))
                except ValueError:
                    continue

        if not od_floats:
            QMessageBox.warning(self, "提示", "您选区的对应单元格中没有可被解析的基础 OD 数据集。")
            return

        mean_od = np.mean(od_floats)
        first_row = selected_rows[0]
        self._set_cell_text(first_row, 1, f"{mean_od:.4f}")
        self._set_cell_text(first_row, 2, "", editable=False)

        for r in reversed(selected_rows[1:]):
            self.removeRow(r)

        self._highlight_merged_row(first_row)

    def get_sample_input_data(self):
        s_list = []
        for r in range(self.rowCount()):
            item_id = self.item(r, 0)
            item_y = self.item(r, 1)
            s_id = item_id.text().strip() if item_id else f"Sample_{r+1}"
            if not item_y or item_y.text().strip() == "":
                continue
            try:
                val_y = float(item_y.text().strip())
                s_list.append((s_id, val_y, r))
            except ValueError:
                continue
        return s_list

    def update_calc_results(self, sample_points: list):
        for sp in sample_points:
            r = sp.row_idx
            if r >= 0 and r < self.rowCount():
                if isinstance(sp.calc_x, float):
                    txt_x = f"{sp.calc_x:.4f}"
                    self._set_cell_text(r, 2, txt_x, editable=False)
                else:
                    txt_x = str(sp.calc_x)
                    self._set_cell_text(r, 2, txt_x, editable=False)
                    item_x = self.item(r, 2)
                    if item_x:
                        item_x.setForeground(QBrush(QColor(211, 47, 47)))
                        item_x.setBackground(QBrush(QColor(255, 240, 240)))

    def load_demo_samples(self):
        """导入样例检测散点带(特别提供重复样标便于使用相同编号均一计算演示)"""
        demo_samps = [
            ("Spl-Ctrl-01", "0.355"),
            ("Spl-Ctrl-02", "0.850"),
            ("Test-Dup-A", "1.425"),
            ("Test-Dup-A", "1.465"),
            ("Test-Dup-B", "2.015"),
            ("Test-Dup-B", "2.035"),
            ("Spl-High-Max", "3.050"),
            ("Spl-Low-Min", "0.012"),
        ]
        if self.rowCount() < len(demo_samps) + 6:
            self.setRowCount(len(demo_samps) + 6)
        for r, (sid, oy) in enumerate(demo_samps):
            self._set_cell_text(r, 0, sid)
            self._set_cell_text(r, 1, oy)
            self._set_cell_text(r, 2, "", editable=False)
