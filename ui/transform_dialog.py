# -*- coding: utf-8 -*-
"""
数据变换对话框 (transform_dialog.py) - V3.0
忠实移植 CurveExpert 1.4 的 Data | Manipulate 功能：
排序、缩放、平移、去离群点，作用于标准品表或样本表。
"""

import numpy as np
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QLineEdit,
    QPushButton, QLabel, QMessageBox, QApplication,
)


class TransformDialog(QDialog):
    """数据操纵对话框"""

    OPERATIONS = [
        "按 X / 样本编号排序",
        "X 值缩放（乘以因子）",
        "Y 值缩放（乘以因子）",
        "X 值平移（加上偏移）",
        "Y 值平移（加上偏移）",
        "去除离群点（Y 的 z 分数阈值）",
    ]

    def __init__(self, std_table, sample_table, parent=None):
        super().__init__(parent)
        self.std_table = std_table
        self.sample_table = sample_table
        self.setWindowTitle("数据变换 (Manipulate)")
        self.resize(430, 240)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.combo_target = QComboBox()
        self.combo_target.addItems(["标准品表", "样本表"])
        form.addRow("作用对象：", self.combo_target)

        self.combo_op = QComboBox()
        self.combo_op.addItems(self.OPERATIONS)
        form.addRow("操作：", self.combo_op)

        self.edit_value = QLineEdit()
        self.edit_value.setPlaceholderText("缩放因子 / 平移偏移 / z 分数阈值（如 3.0）")
        form.addRow("参数：", self.edit_value)
        layout.addLayout(form)

        hint = QLabel("提示：排序可令样条插值等模型正确工作；去离群点按 Y 值的 z 分数剔除异常行。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666;")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btn_apply = QPushButton("应用")
        btn_cancel = QPushButton("取消")
        btn_row.addWidget(self.btn_apply)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        self.btn_apply.clicked.connect(self._apply)
        btn_cancel.clicked.connect(self.reject)
        self.combo_op.currentIndexChanged.connect(self._on_op_changed)
        self._on_op_changed(0)

    def _on_op_changed(self, _idx):
        need_value = self.combo_op.currentIndex() not in (0,)
        self.edit_value.setEnabled(need_value)

    def _get_table(self):
        return self.sample_table if self.combo_target.currentIndex() == 1 else self.std_table

    def _apply(self):
        table = self._get_table()
        op_idx = self.combo_op.currentIndex()
        is_sample = table is self.sample_table

        rows_data = []
        for r in range(table.rowCount()):
            if is_sample:
                c0 = table.item(r, 0)
                c1 = table.item(r, 1)
                rows_data.append([
                    c0.text() if c0 else "",
                    c1.text() if c1 else "",
                ])
            else:
                c0 = table.item(r, 0)
                c1 = table.item(r, 1)
                rows_data.append([
                    c0.text() if c0 else "",
                    c1.text() if c1 else "",
                ])

        def num(cell):
            try:
                return float(cell.strip())
            except ValueError:
                return None

        if op_idx == 0:  # 排序
            valid = [(r, num(row[0]), num(row[1])) for r, row in enumerate(rows_data)]
            valid = [(r, x, y) for r, x, y in valid if x is not None]
            if not valid:
                QMessageBox.information(self, "无数据", "没有可排序的数值行。")
                return
            valid.sort(key=lambda t: t[1])
            new_order = [t[0] for t in valid] + [r for r, row in enumerate(rows_data) if num(row[0]) is None]
            rows_data = [rows_data[i] for i in new_order]
            for r, row in enumerate(rows_data):
                for c in range(2):
                    table._set_cell_text(r, c, row[c], editable=True)
        elif op_idx in (1, 2, 3, 4):  # 缩放/平移
            text = self.edit_value.text().strip()
            try:
                factor = float(text)
            except ValueError:
                QMessageBox.warning(self, "参数无效", "请输入有效数字。")
                return
            col = 0 if op_idx in (1, 3) else 1
            is_scale = op_idx in (1, 2)
            changed = 0
            for r, row in enumerate(rows_data):
                v = num(row[col])
                if v is None:
                    continue
                new_v = v * factor if is_scale else v + factor
                table._set_cell_text(r, col, f"{new_v:.6g}", editable=True)
                changed += 1
            if changed == 0:
                QMessageBox.information(self, "无数据", "所选列没有数值。")
                return
        else:  # 去离群点
            text = self.edit_value.text().strip()
            try:
                threshold = float(text) if text else 3.0
            except ValueError:
                QMessageBox.warning(self, "参数无效", "请输入有效数字。")
                return
            ys = [(r, num(row[1])) for r, row in enumerate(rows_data)]
            ys = [(r, y) for r, y in ys if y is not None]
            if len(ys) < 4:
                QMessageBox.information(self, "数据不足", "至少需要 4 个数值行才能评估离群点。")
                return
            arr = np.array([y for _, y in ys])
            mean, std = float(np.mean(arr)), float(np.std(arr, ddof=1))
            if std < 1e-12:
                QMessageBox.information(self, "无离群点", "数据几乎没有波动，无离群点可去除。")
                return
            removed = []
            for r, y in ys:
                if abs(y - mean) / std > threshold:
                    removed.append(r)
            if not removed:
                QMessageBox.information(self, "无离群点", f"没有 |z| > {threshold:g} 的数据行。")
                return
            for r in reversed(sorted(removed)):
                table.removeRow(r)
            QMessageBox.information(self, "完成", f"已移除 {len(removed)} 个离群数据行。")

        QApplication.processEvents()
        if callable(getattr(self.parent(), "run_full_calculation", None)):
            self.parent().run_full_calculation()
        self.accept()
