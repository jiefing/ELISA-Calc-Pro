# -*- coding: utf-8 -*-
"""
Matplotlib 动态交互响应画布组件模块 (plot_canvas.py)
ELISA-Calc-Pro contributors
无缝嵌入 PyQt5 体系，提供曲线拟合及数据坐标点的图表展示。
"""

import matplotlib
matplotlib.use('Qt5Agg')
# 开启全局中文字体支持，避免显示乱码及方块问号
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
from PyQt5.QtWidgets import QSizePolicy

from core.data_models import CurveFitResult


class FitPlotCanvas(FigureCanvas):
    """
    图形拟合展示画布组件：
    自动适应展示窗格，保持适当留白与正确的抗压缩延展度。
    """
    def __init__(self, parent=None, width=7, height=5, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='#F8F9FA')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#FFFFFF')
        self.settings = {
            "title": "",
            "xlabel": "浓度 Concentration (X)",
            "ylabel": "吸光度 OD (Y)",
            "xscale": "跟随模型",
            "yscale": "线性",
            "xmin": None, "xmax": None, "ymin": None, "ymax": None,
            "show_legend": True, "black_white": False, "auto_scale": True,
            "std_color": "#C62828", "fit_color": "#212121", "sample_color": "#1565C0",
            "std_marker": "o", "sample_marker": "s",
        }

        super().__init__(self.fig)
        self.setParent(parent)

        # 设定全向扩展策略与足够的最小尺寸，防止图表在高分栏下被向左压缩
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumWidth(500)
        self.setMinimumHeight(360)

        # 显示初始占位符
        self._draw_initial_placeholder()

    def _draw_initial_placeholder(self):
        """初始无数据或复位情况下的标准简明提示图"""
        self.ax.clear()
        self.ax.set_title("拟合分析曲线图", fontsize=11, fontweight='bold', color='#495057', pad=10)
        self.ax.set_xlabel("浓度 Concentration (X)", fontsize=10, labelpad=6, color='#343A40')
        self.ax.set_ylabel("吸光度 OD (Y)", fontsize=10, labelpad=6, color='#343A40')
        self.ax.grid(True, linestyle='--', alpha=0.5, color='#CED4DA')

        # 严格按照规范显示简洁明朗的文本
        self.ax.text(
            0.5, 0.5,
            "【未绘制】",
            horizontalalignment='center', verticalalignment='center',
            transform=self.ax.transAxes,
            fontsize=12, color='#6C757D', fontfamily='Microsoft YaHei',
            bbox=dict(boxstyle='round,pad=0.8', facecolor='#F1F3F5', edgecolor='#DEE2E6', alpha=0.9)
        )
        self.fig.tight_layout(pad=1.5)
        self.draw()

    def update_plot(self, fit_result: CurveFitResult):
        """
        绘制标准曲线及样品散点：标准品观察值 (红色圆点)、拟合方程序线 (实黑细线)、待测样品值 (蓝色方块)
        """
        self.ax.clear()

        if not fit_result or not fit_result.success:
            self._draw_error_state(fit_result.error_message if fit_result else "无法完成迭代拟合计算")
            return

        # 1. 根据不同模型要求配置坐标轴显示度量 (如 4PL/Logit 要求对数 X 轴)
        s = self.settings
        if s.get("xscale") == "对数" or (s.get("xscale") == "跟随模型" and fit_result.is_log_x):
            self.ax.set_xscale('log')
        else:
            self.ax.set_xscale('linear')
        self.ax.set_yscale('log' if s.get("yscale") == "对数" else "linear")
        bw = bool(s.get("black_white"))
        std_color = "#222222" if bw else s.get("std_color", "#C62828")
        fit_color = "#000000" if bw else s.get("fit_color", "#212121")
        sample_color = "#555555" if bw else s.get("sample_color", "#1565C0")

        # 2. 绘制标准品输入读值散点
        if fit_result.std_points:
            x_stds = [p.x for p in fit_result.std_points]
            y_stds = [p.y for p in fit_result.std_points]
            self.ax.plot(x_stds, y_stds, linestyle='None', marker=s.get("std_marker", "o"),
                         color=std_color, markersize=7, label='标准品 (Standards)',
                         zorder=6, markeredgecolor=std_color, markeredgewidth=1.2)

        # 3. 绘制连续优化的拟合方程曲线
        if len(fit_result.curve_x) > 0 and len(fit_result.curve_y) > 0:
            c_x = fit_result.curve_x
            c_y = fit_result.curve_y
            if fit_result.is_log_x:
                mask = c_x > 0
                c_x, c_y = c_x[mask], c_y[mask]
            self.ax.plot(c_x, c_y, '-', color=fit_color, linewidth=1.8,
                         label='拟合曲线 (Fitted Curve)', zorder=4)

        # 4. 绘制所有有效推导待测未知样品的落点 —— 标记由星形改设为标准蓝方格(square)
        valid_s_x = []
        valid_s_y = []
        for sp in fit_result.sample_points:
            if isinstance(sp.calc_x, float):
                if not (fit_result.is_log_x and sp.calc_x <= 0):
                    valid_s_x.append(sp.calc_x)
                    valid_s_y.append(sp.y)

        if valid_s_x:
            self.ax.plot(valid_s_x, valid_s_y, linestyle='None', marker=s.get("sample_marker", "s"),
                         color=sample_color, markersize=6.5, label='待测样 (Samples)',
                         zorder=7, markeredgecolor=sample_color, markeredgewidth=1.0)

        # 5. 图标样式规范化润饰
        title = s.get("title") or f"标准曲线: {fit_result.model_name} (R² = {fit_result.r_squared:.5f})"
        self.ax.set_title(title, fontsize=11, fontweight='bold', color='#212529', pad=10)
        self.ax.set_xlabel(s.get("xlabel") or "浓度 Concentration (X)", fontsize=10, labelpad=6, color='#343A40')
        self.ax.set_ylabel(s.get("ylabel") or "吸光度 OD (Y)", fontsize=10, labelpad=6, color='#343A40')
        self.ax.grid(True, linestyle='--', alpha=0.6, color='#CED4DA', which='both' if fit_result.is_log_x else 'major')

        if s.get("show_legend", True):
            legend = self.ax.legend(loc='best', frameon=True, facecolor='#FFFFFF', edgecolor='#DEE2E6', fontsize=9.5)
            legend.get_frame().set_alpha(0.9)

        if not s.get("auto_scale", True):
            try:
                if s.get("xmin") is not None and s.get("xmax") is not None:
                    self.ax.set_xlim(float(s["xmin"]), float(s["xmax"]))
                if s.get("ymin") is not None and s.get("ymax") is not None:
                    self.ax.set_ylim(float(s["ymin"]), float(s["ymax"]))
            except (TypeError, ValueError):
                pass

        self.fig.tight_layout(pad=1.5)
        self.draw()

    def _draw_error_state(self, err_msg: str):
        """发生错误时的简练规范状态告知"""
        self.ax.clear()
        self.ax.set_title("提示: 回归拟合未执行", fontsize=11, color='#D32F2F', fontweight='bold', pad=10)
        self.ax.grid(True, linestyle=':', alpha=0.4)
        self.ax.text(
            0.5, 0.5,
            f"【计算异常】\n\n原因：\n{err_msg}\n\n建议：\n确认输入数值合规且标准品测读数量符合公式需求。",
            horizontalalignment='center', verticalalignment='center',
            transform=self.ax.transAxes,
            fontsize=10.5, color='#B71C1C',
            bbox=dict(boxstyle='round,pad=1.0', facecolor='#FFEBEE', edgecolor='#EF9A9A', alpha=0.95)
        )
        self.fig.tight_layout(pad=1.5)
        self.draw()
