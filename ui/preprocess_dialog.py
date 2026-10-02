# -*- coding: utf-8 -*-
"""ELISA 数据前处理设置：空白扣除、稀释倍数和板/批次元数据。"""

from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QDoubleSpinBox, QLineEdit, QDialogButtonBox,
    QLabel, QVBoxLayout
)


class PreprocessDialog(QDialog):
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("实验前处理设置")
        self.resize(430, 250)
        cfg = dict(config or {})

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.blank_od = QDoubleSpinBox()
        self.blank_od.setRange(-1_000_000, 1_000_000)
        self.blank_od.setDecimals(6)
        self.blank_od.setSingleStep(0.001)
        self.blank_od.setValue(float(cfg.get("blank_od", 0.0)))
        self.blank_od.setToolTip("所有标准品和样本 OD 在拟合/反推前均减去此值。")
        form.addRow("空白孔 OD：", self.blank_od)

        self.dilution = QDoubleSpinBox()
        self.dilution.setRange(0.000001, 1_000_000)
        self.dilution.setDecimals(6)
        self.dilution.setSingleStep(1.0)
        self.dilution.setValue(float(cfg.get("dilution_factor", 1.0)))
        self.dilution.setToolTip("样本反推浓度乘以此倍数，标准曲线本身不乘倍数。")
        form.addRow("样本稀释倍数：", self.dilution)

        self.batch = QLineEdit(str(cfg.get("batch_id", "")))
        self.batch.setPlaceholderText("例如：Kit-2026-08 / 批号")
        form.addRow("校准批次：", self.batch)

        self.plate = QLineEdit(str(cfg.get("plate_id", "")))
        self.plate.setPlaceholderText("例如：Plate-01")
        form.addRow("校准板号：", self.plate)

        layout.addLayout(form)
        layout.addWidget(QLabel("说明：当前标准品表即为当前板/批次的独立校准；更换板号或批次后重新录入标准品并计算即可。"))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return {
            "blank_od": float(self.blank_od.value()),
            "dilution_factor": float(self.dilution.value()),
            "batch_id": self.batch.text().strip(),
            "plate_id": self.plate.text().strip(),
        }
