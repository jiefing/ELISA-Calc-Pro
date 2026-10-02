# -*- coding: utf-8 -*-
"""
数据统计信息对话框 (stats_dialog.py) - V3.0
忠实移植 CurveExpert 1.4 的 Data Information 功能：
展示标准品表与样本表的点数、均值、最小值、最大值、标准差。
"""

import numpy as np
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QAbstractItemView,
)
from PyQt5.QtGui import QFont


def _col_stats(values):
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return None
    return {
        "n": arr.size,
        "mean": float(np.mean(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "std": float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0,
    }


class StatsDialog(QDialog):
    """展示当前表格数据的统计摘要"""

    def __init__(self, std_table, sample_table, parent=None):
        super().__init__(parent)
        self.setWindowTitle("数据统计信息")
        self.resize(560, 380)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("标准品数据（浓度 X / 吸光度 Y）："))
        std_x, std_y = [], []
        for r in range(std_table.rowCount()):
            ix, iy = std_table.item(r, 0), std_table.item(r, 1)
            if not ix or not iy:
                continue
            try:
                std_x.append(float(ix.text().strip()))
                std_y.append(float(iy.text().strip()))
            except ValueError:
                continue
        layout.addWidget(self._build_table([
            ("指标", "X (浓度)", "Y (吸光度)"),
            *self._stat_rows(std_x, std_y),
        ]))

        layout.addWidget(QLabel("样本数据（吸光度 OD）："))
        samp_y = []
        for r in range(sample_table.rowCount()):
            iy = sample_table.item(r, 1)
            if not iy:
                continue
            try:
                samp_y.append(float(iy.text().strip()))
            except ValueError:
                continue
        layout.addWidget(self._build_table([
            ("指标", "Y (吸光度)"),
            *self._stat_rows(samp_y, []),
        ]))

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    @staticmethod
    def _stat_rows(col_a, col_b):
        sa, sb = _col_stats(col_a), _col_stats(col_b)
        if sa is None and sb is None:
            return [("数据点", "—", "—")]
        rows = [
            ("数据点", str(sa["n"]) if sa else "—", str(sb["n"]) if sb else "—"),
            ("平均值", f"{sa['mean']:.6g}" if sa else "—", f"{sb['mean']:.6g}" if sb else "—"),
            ("最小值", f"{sa['min']:.6g}" if sa else "—", f"{sb['min']:.6g}" if sb else "—"),
            ("最大值", f"{sa['max']:.6g}" if sa else "—", f"{sb['max']:.6g}" if sb else "—"),
            ("标准差 (n-1)", f"{sa['std']:.6g}" if sa else "—", f"{sb['std']:.6g}" if sb else "—"),
        ]
        return rows

    @staticmethod
    def _build_table(rows):
        n_cols = len(rows[0])
        table = QTableWidget(len(rows), n_cols)
        table.setHorizontalHeaderLabels([str(c) for c in rows[0]])
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        for r, row in enumerate(rows[1:], start=1):
            for c, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                if r == 0:
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)
                table.setItem(r - 1, c, item)
        table.setMaximumHeight(180)
        return table
