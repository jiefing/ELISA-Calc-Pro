# -*- coding: utf-8 -*-
"""
手动框选确认预览对话框 - PreviewDialog
读取 Excel/CSV/TXT 原貌数据并展示，供实验人员进行有效区域拖拽选择。
"""

import re
import os
import numpy as np
from typing import List, Tuple

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QMessageBox,
    QAbstractItemView, QHeaderView, QFrame
)
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QFont, QColor, QBrush

from models.data_structures import Plate, WellType
from controllers.io_manager import IOManager, IOManagerError

class PreviewDialog(QDialog):
    """
    统一手动框选数据确认预览框 (QDialog)。
    """
    def __init__(self, filepath: str, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.split_data: List[List[str]] = []
        self.selected_matrix: List[List[float]] = None
        self.ref_matrix: List[List[float]] = None
        self.plate_size = 96  # 默认

        self.setWindowTitle("数据导入预览 --- ELISA-Calc-Pro")
        self.setMinimumSize(800, 500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        # 1. 优先加载读取数据原貌 (List[List[str]])
        self._load_raw_data()

        # 2. 初始化 UI 组件
        self._init_ui()

        # 3. 基于 RegEx 执行自动定位推荐高亮
        self._auto_detect_matrix()

        # 加载样式表
        self._apply_style()

    def _load_raw_data(self):
        """借助 IOManager 静态类读取文件二维列表"""
        try:
            self.split_data = IOManager.read_to_grid(self.filepath)
        except IOManagerError as e:
            QMessageBox.critical(self, "读取错误", f"无法解析读取数据：\n{e}")
            self.reject()

    def _apply_style(self):
        # 优先读取全局 style_xp.qss 的样式
        qss_path = os.path.join(os.path.dirname(__file__), "style_xp.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        else:
            # 备用样式
            self.setStyleSheet("""
                QDialog { background-color: #ffffff; }
                QPushButton { background-color: #e1e1e1; border: 1px outset #808080; padding: 4px 8px; }
                QTableWidget { border: 2px inset #808080; }
            """)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 1. 顶层控制面板
        top_panel = QFrame()
        top_layout = QHBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        info_label = QLabel(
            "使用方法：用鼠标左键拖拽框选数据矩阵区域（如 8×12 的数值范围），"
            "然后点击设定为对应数据。"
        )
        info_label.setWordWrap(True)
        top_layout.addWidget(info_label, 1)

        self.set_main_btn = QPushButton("设为主波长数据")
        self.set_main_btn.clicked.connect(self._set_main_data)
        top_layout.addWidget(self.set_main_btn)

        self.set_ref_btn = QPushButton("设为参比波长数据")
        self.set_ref_btn.clicked.connect(self._set_ref_data)
        top_layout.addWidget(self.set_ref_btn)

        self.confirm_btn = QPushButton("确认导入")
        self.confirm_btn.setEnabled(False)
        self.confirm_btn.clicked.connect(self._confirm_import)
        self.confirm_btn.setStyleSheet("font-weight: bold;")
        top_layout.addWidget(self.confirm_btn)

        layout.addWidget(top_panel)

        # 数据状态反馈区
        self.status_label = QLabel("未选中任何有效数据区域")
        self.status_label.setStyleSheet("color: #000080; font-weight: bold;")
        layout.addWidget(self.status_label)

        # 2. 下半部分数据预览区
        max_cols = max(len(row) for row in self.split_data) if self.split_data else 0

        self.table_widget = QTableWidget()
        self.table_widget.setRowCount(len(self.split_data))
        self.table_widget.setColumnCount(max_cols)

        # 展现物理原始行、列号
        self.table_widget.setVerticalHeaderLabels([str(i+1) for i in range(len(self.split_data))])
        self.table_widget.setHorizontalHeaderLabels([str(i+1) for i in range(max_cols)])

        self.table_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table_widget.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # 填充二维预览格点
        cell_font = QFont("Consolas", 9)
        for r_idx, row in enumerate(self.split_data):
            for c_idx, val in enumerate(row):
                item = QTableWidgetItem(val)
                item.setFont(cell_font)
                self.table_widget.setItem(r_idx, c_idx, item)

        # 自适应列宽
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.table_widget)

    def _auto_detect_matrix(self):
        """
        基于正则表达式的半自动识别定位推荐算法。
        寻找连续的 8 行且包含 12 个以上浮点数的区域 (96孔板)。
        """
        float_pattern = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')

        def is_numeric(s):
            if s is None:
                return False
            return bool(float_pattern.match(str(s).strip()))

        row_numeric_counts = []
        for row in self.split_data:
            numeric_count = sum(1 for cell in row if is_numeric(cell))
            row_numeric_counts.append(numeric_count)

        # 96孔板自动定位
        for i in range(len(row_numeric_counts) - 7):
            if all(count >= 12 for count in row_numeric_counts[i:i+8]):
                start_cols = []
                for r_idx in range(i, i+8):
                    numeric_indices = [c for c, val in enumerate(self.split_data[r_idx]) if is_numeric(val)]
                    if len(numeric_indices) >= 12:
                        start_cols.append(numeric_indices[0])
                if start_cols:
                    start_col = min(start_cols)
                    self._highlight_range(i, start_col, 8, 12)
                    self.plate_size = 96
                    self.status_label.setText("自动检测到疑似 96 孔板(8x12)数据矩阵，已为您自动高亮框选。")
                    return

        # 384孔板自动定位
        for i in range(len(row_numeric_counts) - 15):
            if all(count >= 24 for count in row_numeric_counts[i:i+16]):
                start_cols = []
                for r_idx in range(i, i+16):
                    numeric_indices = [c for c, val in enumerate(self.split_data[r_idx]) if is_numeric(val)]
                    if len(numeric_indices) >= 24:
                        start_cols.append(numeric_indices[0])
                if start_cols:
                    start_col = min(start_cols)
                    self._highlight_range(i, start_col, 16, 24)
                    self.plate_size = 384
                    self.status_label.setText("自动检测到疑似 384 孔板(16x24)数据矩阵，已为您自动高亮框选。")
                    return

    def _highlight_range(self, start_row: int, start_col: int, rows: int, cols: int):
        self.table_widget.clearSelection()
        for r in range(start_row, start_row + rows):
            for c in range(start_col, start_col + cols):
                if r < self.table_widget.rowCount() and c < self.table_widget.columnCount():
                    item = self.table_widget.item(r, c)
                    if item:
                        item.setSelected(True)

    def _extract_selected_matrix(self) -> Tuple[List[List[float]], int, int]:
        """
        提取当前框选区域，应用 IOManager.clean_cell 二次防崩过滤
        """
        selected_ranges = self.table_widget.selectedRanges()
        if not selected_ranges:
            return None, 0, 0

        # 取第一个框选区域的边界
        selected_range = selected_ranges[0]
        top_row = selected_range.topRow()
        bottom_row = selected_range.bottomRow()
        left_col = selected_range.leftColumn()
        right_col = selected_range.rightColumn()

        rows = bottom_row - top_row + 1
        cols = right_col - left_col + 1

        matrix: List[List[float]] = []
        for r in range(top_row, bottom_row + 1):
            row_data = []
            for c in range(left_col, right_col + 1):
                item = self.table_widget.item(r, c)
                val_str = item.text().strip() if item else ""
                # 二次清洗过滤，移除非数字杂质
                cleaned_val = IOManager.clean_cell(val_str)
                row_data.append(cleaned_val)
            matrix.append(row_data)

        return matrix, rows, cols

    def _set_main_data(self):
        """设定为主波长数据"""
        matrix, rows, cols = self._extract_selected_matrix()
        if not matrix:
            QMessageBox.warning(self, "警告", "请先在预览网格中拖拽选中数据区域。")
            return

        # 检查是否是标准规格尺寸
        if (rows != 8 or cols != 12) and (rows != 16 or cols != 24):
            reply = QMessageBox.question(
                self, "尺寸确认",
                f"选中的数据区域大小为 {rows}行 x {cols}列，不符合标准的 8x12 (96孔) 或 16x24 (384孔) 规格。\n\n"
                "是否强制设为主波长数据（部分未装满的孔板）？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        self.selected_matrix = matrix
        self.plate_size = 384 if (rows == 16 or cols == 24) else 96

        self.status_label.setText(
            f"已成功框选主波长数据：共 {rows} 行 x {cols} 列 (确定为 {self.plate_size} 孔板规格)"
        )
        self.confirm_btn.setEnabled(True)

    def _set_ref_data(self):
        """设定为参比波长数据"""
        matrix, rows, cols = self._extract_selected_matrix()
        if not matrix:
            QMessageBox.warning(self, "警告", "请先在预览网格中拖拽选中数据区域。")
            return

        if (rows != 8 or cols != 12) and (rows != 16 or cols != 24):
            reply = QMessageBox.question(
                self, "尺寸确认",
                f"选中的参比波长数据区域大小为 {rows}行 x {cols}列。\n是否确认强制设定？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        self.ref_matrix = matrix
        QMessageBox.information(
            self, "设置成功", f"参比波长数据框选成功 ({rows}x{cols})，用于执行主-参比差分扣除。"
        )

    def _confirm_import(self):
        if not self.selected_matrix:
            QMessageBox.critical(self, "错误", "请先确认主波长数据。")
            return
        self.accept()

    def get_imported_plate(self) -> Plate:
        """根据框选映射生成 Plate 模型数据"""
        plate = Plate(self.plate_size)
        plate.source_file = self.filepath

        # 按空间次序映射到 Plate 微孔中
        for r_idx, row_label in enumerate(plate.row_labels):
            if r_idx >= len(self.selected_matrix):
                break
            row_data = self.selected_matrix[r_idx]
            ref_row_data = self.ref_matrix[r_idx] if (self.ref_matrix and r_idx < len(self.ref_matrix)) else None

            for c_idx in range(1, plate.cols + 1):
                if (c_idx - 1) >= len(row_data):
                    break
                val = row_data[c_idx - 1]
                ref_val = ref_row_data[c_idx - 1] if (ref_row_data and (c_idx - 1) < len(ref_row_data)) else None

                # 写入 Well
                well = plate.get_well(row_label, c_idx)
                if well:
                    well.raw_value = val
                    well.ref_value = ref_val
                    # 设定类型为 SAMPLE，防止为空
                    well.well_type = WellType.SAMPLE

        return plate
