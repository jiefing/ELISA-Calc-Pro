# -*- coding: utf-8 -*-
"""拟合曲线图表属性设置。"""

from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QComboBox, QCheckBox,
    QDialogButtonBox, QVBoxLayout, QColorDialog
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt


class PlotPropertiesDialog(QDialog):
    def __init__(self, settings=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("图表属性设置")
        self.resize(430, 360)
        s = dict(settings or {})
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title = QLineEdit(str(s.get("title", "")))
        self.xlabel = QLineEdit(str(s.get("xlabel", "浓度 Concentration (X)")))
        self.ylabel = QLineEdit(str(s.get("ylabel", "吸光度 OD (Y)")))
        form.addRow("图表标题：", self.title)
        form.addRow("X 轴标题/单位：", self.xlabel)
        form.addRow("Y 轴标题/单位：", self.ylabel)

        self.xscale = QComboBox()
        self.xscale.addItems(["跟随模型", "线性", "对数"])
        self.xscale.setCurrentText(str(s.get("xscale", "跟随模型")))
        form.addRow("X 轴坐标：", self.xscale)
        self.yscale = QComboBox()
        self.yscale.addItems(["线性", "对数"])
        self.yscale.setCurrentText(str(s.get("yscale", "线性")))
        form.addRow("Y 轴坐标：", self.yscale)

        self.xmin = QLineEdit(str(s.get("xmin", "")))
        self.xmax = QLineEdit(str(s.get("xmax", "")))
        self.ymin = QLineEdit(str(s.get("ymin", "")))
        self.ymax = QLineEdit(str(s.get("ymax", "")))
        form.addRow("X 最小值（空=自动）：", self.xmin)
        form.addRow("X 最大值（空=自动）：", self.xmax)
        form.addRow("Y 最小值（空=自动）：", self.ymin)
        form.addRow("Y 最大值（空=自动）：", self.ymax)

        self.show_legend = QCheckBox("显示图例")
        self.show_legend.setChecked(bool(s.get("show_legend", True)))
        self.black_white = QCheckBox("黑白打印模式")
        self.black_white.setChecked(bool(s.get("black_white", False)))
        self.auto_scale = QCheckBox("自动缩放（覆盖手动范围）")
        self.auto_scale.setChecked(bool(s.get("auto_scale", True)))
        form.addRow("", self.show_legend)
        form.addRow("", self.black_white)
        form.addRow("", self.auto_scale)

        self.std_color = QLineEdit(str(s.get("std_color", "#C62828")))
        self.fit_color = QLineEdit(str(s.get("fit_color", "#212121")))
        self.sample_color = QLineEdit(str(s.get("sample_color", "#1565C0")))
        self.std_marker = QLineEdit(str(s.get("std_marker", "o")))
        self.sample_marker = QLineEdit(str(s.get("sample_marker", "s")))
        form.addRow("标准品颜色：", self.std_color)
        form.addRow("拟合曲线颜色：", self.fit_color)
        form.addRow("样本颜色：", self.sample_color)
        form.addRow("标准品点型：", self.std_marker)
        form.addRow("样本点型：", self.sample_marker)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _float_or_none(text):
        text = text.strip()
        if not text:
            return None
        return float(text)

    def values(self):
        return {
            "title": self.title.text().strip(),
            "xlabel": self.xlabel.text().strip(),
            "ylabel": self.ylabel.text().strip(),
            "xscale": self.xscale.currentText(),
            "yscale": self.yscale.currentText(),
            "xmin": self._float_or_none(self.xmin.text()),
            "xmax": self._float_or_none(self.xmax.text()),
            "ymin": self._float_or_none(self.ymin.text()),
            "ymax": self._float_or_none(self.ymax.text()),
            "show_legend": self.show_legend.isChecked(),
            "black_white": self.black_white.isChecked(),
            "auto_scale": self.auto_scale.isChecked(),
            "std_color": self.std_color.text().strip() or "#C62828",
            "fit_color": self.fit_color.text().strip() or "#212121",
            "sample_color": self.sample_color.text().strip() or "#1565C0",
            "std_marker": self.std_marker.text().strip() or "o",
            "sample_marker": self.sample_marker.text().strip() or "s",
        }
