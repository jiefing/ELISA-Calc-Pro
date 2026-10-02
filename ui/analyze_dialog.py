# -*- coding: utf-8 -*-
"""
曲线分析工具对话框 (analyze_dialog.py) - V3.0
忠实移植 CurveExpert 1.4 的 Analyze Fit 功能：
  y = f(x) 求值 / x = f(y) 反推 / 一阶微分 / 定积分 / 弧长
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QFormLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox,
)


def _parse_number(text: str) -> float:
    try:
        return float(text.strip())
    except ValueError:
        raise ValueError(f"无法解析数字：'{text}'")


class AnalyzeDialog(QDialog):
    """基于当前拟合结果的数值分析工具"""

    def __init__(self, result, strategy, parent=None):
        super().__init__(parent)
        self.result = result
        self.strategy = strategy
        self.setWindowTitle(f"分析工具 - {result.model_name}")
        self.resize(430, 320)

        layout = QVBoxLayout(self)
        info = QLabel(
            f"当前模型：{result.model_name}\n"
            f"方程：{result.equation_str}\n"
            f"标准品浓度范围：[{result.x_range[0]:.6g}, {result.x_range[1]:.6g}]"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        tabs = QTabWidget()
        tabs.addTab(self._build_eval_tab(), "求值 y=f(x)")
        tabs.addTab(self._build_solve_tab(), "反推 x=f(y)")
        tabs.addTab(self._build_deriv_tab(), "微分 f'(x)")
        tabs.addTab(self._build_integral_tab(), "积分 ∫f(x)dx")
        tabs.addTab(self._build_arclen_tab(), "弧长")
        layout.addWidget(tabs, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    # ---------------- 通用输入行 ----------------
    @staticmethod
    def _input_row(label, btn_text, callback):
        w = QWidget()
        form = QFormLayout(w)
        edit = QLineEdit()
        out = QLabel("—")
        out.setWordWrap(True)
        out.setStyleSheet("color: #0B5ED7; font-weight: bold;")
        btn = QPushButton(btn_text)
        btn.clicked.connect(lambda: callback(edit, out))
        edit.returnPressed.connect(btn.click)
        form.addRow(label, edit)
        form.addRow(btn)
        form.addRow("结果：", out)
        return w

    def _build_eval_tab(self):
        def calc(edit, out):
            try:
                x = _parse_number(edit.text())
                y = float(self.result.predict_fn([x])[0])
                out.setText(f"y = f({x:g}) = {y:.8g}")
            except Exception as e:
                out.setText(f"ERR：{e}")
        return self._input_row("输入 x 值：", "计算 y 值", calc)

    def _build_solve_tab(self):
        def calc(edit, out):
            try:
                y = _parse_number(edit.text())
                lo, hi = self.result.x_range
                span = hi - lo if hi > lo else 1.0
                x = self.strategy.solve_x(y, self.result.parameters,
                                          lo - span * 0.2, hi + span * 0.2,
                                          preferred_x=(lo + hi) / 2.0)
                if x is None:
                    out.setText("在标准品范围内无解（可能超出模型值域）")
                else:
                    out.setText(f"x = f⁻¹({y:g}) = {x:.8g}")
            except Exception as e:
                out.setText(f"ERR：{e}")
        return self._input_row("输入 y 值：", "计算 x 值", calc)

    def _build_deriv_tab(self):
        def calc(edit, out):
            try:
                x = _parse_number(edit.text())
                d = self.strategy.derivative(x, self.result.parameters)
                out.setText(f"f'({x:g}) = {d:.8g}")
            except Exception as e:
                out.setText(f"ERR：{e}")
        return self._input_row("输入 x 值：", "计算一阶导数", calc)

    def _build_integral_tab(self):
        def calc(edit, out):
            try:
                text = edit.text().replace(",", " ").split()
                if len(text) != 2:
                    out.setText("请输入两个数：下限 上限（空格或逗号分隔）")
                    return
                a, b = _parse_number(text[0]), _parse_number(text[1])
                val = self.strategy.integrate(a, b, self.result.parameters)
                out.setText(f"∫[{a:g}, {b:g}] f(x)dx = {val:.8g}")
            except Exception as e:
                out.setText(f"ERR：{e}")
        return self._input_row("输入积分区间 (a b)：", "计算定积分", calc)

    def _build_arclen_tab(self):
        def calc(edit, out):
            try:
                text = edit.text().replace(",", " ").split()
                if len(text) != 2:
                    out.setText("请输入两个数：起点 终点（空格或逗号分隔）")
                    return
                a, b = _parse_number(text[0]), _parse_number(text[1])
                val = self.strategy.arclength(a, b, self.result.parameters)
                out.setText(f"弧长 [{a:g}, {b:g}] = {val:.8g}")
            except Exception as e:
                out.setText(f"ERR：{e}")
        return self._input_row("输入弧长区间 (a b)：", "计算弧长", calc)
