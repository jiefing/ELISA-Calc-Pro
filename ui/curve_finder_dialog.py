# -*- coding: utf-8 -*-
"""
CurveFinder 自动寻优对话框 (curve_finder_dialog.py) - V3.0
勾选要搜索的模型族、指定多项式最大阶数与权重模式，
执行全模型拟合并在完成后将排名结果交给主窗口。
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox, QComboBox,
    QPushButton, QLabel, QSpinBox, QProgressDialog, QMessageBox, QApplication,
)
from PyQt5.QtCore import Qt

from math_engine import get_all_models, get_families, run_curve_finder, WEIGHT_MODES


class CurveFinderDialog(QDialog):
    """CurveFinder 参数选择对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CurveFinder 自动寻优")
        self.resize(430, 460)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("选择需要搜索的模型族（拟合失败的模型会自动跳过）："))
        self._family_boxes = {}
        fam_group = QGroupBox("模型族")
        fam_layout = QVBoxLayout(fam_group)
        self._check_all = QCheckBox("全选 / 全不选")
        self._check_all.setChecked(True)
        fam_layout.addWidget(self._check_all)
        for fam in get_families():
            box = QCheckBox(fam)
            box.setChecked(True)
            self._family_boxes[fam] = box
            fam_layout.addWidget(box)
        layout.addWidget(fam_group)

        opt_layout = QHBoxLayout()
        opt_layout.addWidget(QLabel("多项式最高阶数："))
        self.spin_poly = QSpinBox()
        self.spin_poly.setRange(2, 8)
        self.spin_poly.setValue(4)
        opt_layout.addWidget(self.spin_poly)
        opt_layout.addSpacing(16)
        opt_layout.addWidget(QLabel("权重模式："))
        self.combo_weight = QComboBox()
        self.combo_weight.addItems(list(WEIGHT_MODES.keys()))
        self.combo_weight.setCurrentIndex(0)
        opt_layout.addWidget(self.combo_weight, stretch=1)
        layout.addLayout(opt_layout)

        btn_row = QHBoxLayout()
        self.btn_run = QPushButton("开始搜索")
        self.btn_cancel = QPushButton("取消")
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_run)
        btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)

        self._check_all.toggled.connect(self._on_toggle_all)
        self.btn_run.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def _on_toggle_all(self, checked):
        for box in self._family_boxes.values():
            box.setChecked(checked)

    def selected_families(self):
        return [fam for fam, box in self._family_boxes.items() if box.isChecked()]

    def max_poly_order(self):
        return self.spin_poly.value()

    def weight_mode(self):
        return WEIGHT_MODES[self.combo_weight.currentText()]


def run_curve_finder_dialog(parent, std_tuples, sample_tuples) -> bool:
    """
    弹出 CurveFinder 对话框并执行全模型搜索。
    成功时父窗口通过 _on_curve_finder_results 接收排名条目。
    返回是否执行了搜索。
    """
    from core.data_models import StandardPoint, SamplePoint

    if len(std_tuples) < 3:
        QMessageBox.information(parent, "标准品不足",
            "CurveFinder 至少需要 3 组有效的标准品数据。")
        return False

    dlg = CurveFinderDialog(parent)
    if dlg.exec_() != QDialog.Accepted:
        return False

    families = dlg.selected_families()
    if not families:
        QMessageBox.information(parent, "未选择模型族", "请至少勾选一个模型族。")
        return False

    std_points = [StandardPoint(x=x, y=y, row_idx=idx) for (x, y, idx) in std_tuples]
    sample_points = [SamplePoint(sample_id=sid, y=y, row_idx=idx) for (sid, y, idx) in sample_tuples]

    progress = QProgressDialog("正在遍历全部模型拟合…", "中止", 0, 100, parent)
    progress.setWindowTitle("CurveFinder 自动寻优")
    progress.setWindowModality(Qt.WindowModal)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)

    state = {"abort": False}

    def progress_cb(current, total, name):
        progress.setMaximum(total)
        progress.setValue(current)
        progress.setLabelText(f"正在拟合 [{current}/{total}]：{name}")
        QApplication.processEvents()

    def abort_flag():
        return state["abort"]

    progress.canceled.connect(lambda: state.update(abort=True))

    entries = run_curve_finder(
        std_points, sample_points,
        get_all_models(),
        families=families,
        max_poly_order=dlg.max_poly_order(),
        weights=dlg.weight_mode(),
        progress_cb=progress_cb,
        abort_flag=abort_flag,
    )
    progress.close()

    parent._on_curve_finder_results(entries)
    return True
