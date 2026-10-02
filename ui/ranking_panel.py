# -*- coding: utf-8 -*-
"""
模型排名面板 (ranking_panel.py) - V3.0
展示 CurveFinder 自动寻优结果（排名 / 模型 / 族 / R² / 标准误 / AIC），
点击某一行可将对应模型与结果载入主视图。
"""

from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor


class RankingPanel(QTableWidget):
    """拟合排名表：行 = 模型，点击发射 model_selected 信号"""

    model_selected = pyqtSignal(object, object)  # (strategy, CurveFitResult 或 None)

    def __init__(self, parent=None):
        super().__init__(0, 6, parent)
        self.setHorizontalHeaderLabels(["排名", "模型", "模型族", "R²", "标准误", "AIC"])
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.cellClicked.connect(self._on_cell_clicked)
        self._entries = []

    def set_entries(self, entries):
        """注入 CurveFinder 排名条目列表"""
        self._entries = entries
        self.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            if entry.result is not None:
                self.setItem(row, 0, QTableWidgetItem(str(entry.rank)))
                self.setItem(row, 1, QTableWidgetItem(entry.model_name))
                self.setItem(row, 2, QTableWidgetItem(entry.family))
                self.setItem(row, 3, QTableWidgetItem(f"{entry.r_squared:.6f}"))
                self.setItem(row, 4, QTableWidgetItem(f"{entry.standard_error:.6g}"))
                self.setItem(row, 5, QTableWidgetItem(
                    "∞" if entry.aic == float("inf") else f"{entry.aic:.4g}"))
                for col in range(6):
                    self.item(row, col).setToolTip(entry.model_name)
            else:
                self.setItem(row, 0, QTableWidgetItem(str(entry.rank)))
                self.setItem(row, 1, QTableWidgetItem(entry.model_name))
                self.setItem(row, 2, QTableWidgetItem(entry.family))
                self.setItem(row, 3, QTableWidgetItem("—"))
                self.setItem(row, 4, QTableWidgetItem("—"))
                self.setItem(row, 5, QTableWidgetItem("—"))
                self.item(row, 1).setForeground(QColor(160, 160, 160))
                self.item(row, 1).setToolTip(entry.note or "拟合失败")
        self.resizeRowsToContents()

    def clear_entries(self):
        self._entries = []
        self.setRowCount(0)

    def best_entry(self):
        """返回排名第一的成功条目（无则 None）"""
        for entry in self._entries:
            if entry.result is not None:
                return entry
        return None

    def _on_cell_clicked(self, row, _col):
        if 0 <= row < len(self._entries):
            entry = self._entries[row]
            self.model_selected.emit(entry.strategy, entry.result)
