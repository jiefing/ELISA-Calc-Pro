# -*- coding: utf-8 -*-
"""
标准曲线绘图组件 - CurvePlotWidget
继承自 QWidget，内嵌 Matplotlib Canvas，支持对数 X 轴 4PL 拟合曲线与散点图渲染。
XP 经典浅灰背景融合风格。
"""

import numpy as np
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import Qt

import matplotlib
matplotlib.use("Qt5Agg")
# 配置中文字体，防止 matplotlib 乱码和负号方块
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class CurvePlotWidget(QWidget):
    """
    4PL 标准曲线与测试样品分布可视化组件。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        # 1. 创建 Matplotlib 图像实体
        # tight_layout=True 自动收缩边距防止文字重叠
        self.figure = Figure(figsize=(5, 3.5), dpi=100, facecolor="#F0F0F0")
        self.figure.subplots_adjust(bottom=0.18, left=0.15, right=0.95, top=0.9)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        # 2. 获取子图坐标轴
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor("#F0F0F0")

        # 经典网格
        self.ax.grid(True, which="both", ls="--", color="#CCCCCC")
        self._draw_empty_placeholder()

    def _draw_empty_placeholder(self):
        """画出未运行计算时的占位符"""
        self.ax.clear()
        self.ax.set_facecolor("#F0F0F0")
        self.ax.text(0.5, 0.5, "尚未运行 4PL 标曲计算\n暂无标曲图谱",
                     ha="center", va="center", fontsize=10, color="#777777",
                     transform=self.ax.transAxes)
        self.ax.set_xlabel("浓度 (Concentration)", fontsize=9)
        self.ax.set_ylabel("净 OD 值 (Net OD)", fontsize=9)
        self.canvas.draw()

    def clear_plot(self):
        self._draw_empty_placeholder()

    def plot_curve(self, popt, std_x: list, std_y: list, sample_x: list, sample_y: list, r_squared: float):
        """
        绘制 4PL 拟合曲线、标准品点及测试样品点。

        Args:
            popt: [A, B, C, D] 4PL 拟合系数
            std_x: 标准品浓度列表
            std_y: 标准品净 OD 列表
            sample_x: 测试样品反推浓度列表
            sample_y: 测试样品净 OD 列表
            r_squared: 拟合决定系数 R²
        """
        self.ax.clear()
        self.ax.set_facecolor("#F0F0F0")

        # 1. 对零浓度点进行极小值平移以适配对数坐标系 (Log10 Scale)
        # 查找标准品中的最小非零浓度以作为 0 点的底数，若无非零值则默认设为 1e-4
        # 1. 对零浓度点进行极小值平移以适配对数坐标系 (Log10 Scale)
        # 查找标准品中的最小非零浓度以作为 0 点的底数，若无非零值则默认设为 1.0
        non_zero_concs = [x for x in std_x if x > 0]
        min_pos = min(non_zero_concs) * 0.2 if non_zero_concs else 1.0
        if min_pos < 1e-4:
            min_pos = 1e-4

        std_x_plot = [x if x > 0 else min_pos for x in std_x]
        sample_x_plot = [x if x > 0 else min_pos for x in sample_x]

        # 2. 绘制 4PL 黑色拟合平滑 S 曲线
        if popt and len(popt) == 4:
            A, B, C, D = popt

            # 在 log 空间生成 100 个平滑插值自变量点
            min_x_fit = min(std_x_plot)
            max_x_fit = max(std_x_plot)
            if min_x_fit == max_x_fit:
                min_x_fit = min_pos
                max_x_fit = 1000.0

            x_fit = np.logspace(np.log10(min_x_fit), np.log10(max_x_fit), 100)
            # 4PL 函数方程
            y_fit = D + (A - D) / (1.0 + (x_fit / C) ** B)

            self.ax.plot(x_fit, y_fit, "k-", linewidth=1.5, label="4PL Fit Curve")

        # 3. 绘制标准品点 (红色圆圈 'ro')
        if std_x_plot:
            self.ax.plot(std_x_plot, std_y, "ro", markersize=6, label="Standards")

        # 4. 绘制待测样品点 (蓝色星星 'b*')
        if sample_x_plot:
            self.ax.plot(sample_x_plot, sample_y, "b*", markersize=5, label="Samples")

        # 5. 对数坐标系设置与标记
        self.ax.set_xscale("log")
        self.ax.set_xlabel("浓度 (Concentration)", fontsize=9, fontweight="bold")
        self.ax.set_ylabel("净 OD 值 (Net OD)", fontsize=9, fontweight="bold")

        # 锁定 X 轴显示范围：以标准品稀释区间为主导，避免低浓度杂点拉长横轴
        if std_x_plot:
            self.ax.set_xlim(min(std_x_plot) * 0.5, max(std_x_plot) * 1.5)

        # 经典网格与边框样式
        self.ax.grid(True, which="both", ls="--", color="#CCCCCC", alpha=0.7)

        # 6. 图例与决定系数 R²
        self.ax.legend(loc="best", fontsize=8, framealpha=0.8, facecolor="#F0F0F0")

        # 角落展示决定系数
        self.ax.text(0.05, 0.05, f"$R^2$ = {r_squared:.5f}",
                     transform=self.ax.transAxes, fontsize=10, fontweight="bold",
                     bbox=dict(boxstyle="round,pad=0.3", facecolor="#E1E1E1", alpha=0.8, edgecolor="#808080"))

        # 重绘画布
        self.canvas.draw()
