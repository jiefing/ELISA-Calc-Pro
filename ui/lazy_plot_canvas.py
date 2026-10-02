# -*- coding: utf-8 -*-
"""延迟创建 Matplotlib 画布，避免程序启动阶段加载 Matplotlib。"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt


class LazyPlotCanvas(QWidget):
    def __init__(self, parent=None, width=7, height=5):
        super().__init__(parent)
        self._width = width
        self._height = height
        self._canvas = None
        self.settings = {
            "title": "", "xlabel": "浓度 Concentration (X)",
            "ylabel": "吸光度 OD (Y)", "xscale": "跟随模型",
            "yscale": "线性", "xmin": None, "xmax": None,
            "ymin": None, "ymax": None, "show_legend": True,
            "black_white": False, "auto_scale": True,
            "std_color": "#C62828", "fit_color": "#212121",
            "sample_color": "#1565C0", "std_marker": "o",
            "sample_marker": "s",
        }
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._placeholder = QLabel("拟合图表将在首次计算时加载")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(
            "color:#6C757D;background:#FFFFFF;border:1px solid #DEE2E6;")
        self._layout.addWidget(self._placeholder)

    def _ensure_canvas(self):
        if self._canvas is None:
            from ui.plot_canvas import FitPlotCanvas
            self._canvas = FitPlotCanvas(self, width=self._width, height=self._height)
            self._canvas.settings = dict(self.settings)
            self._layout.removeWidget(self._placeholder)
            self._placeholder.deleteLater()
            self._layout.addWidget(self._canvas)
        return self._canvas

    @property
    def fig(self):
        return self._ensure_canvas().fig

    def update_plot(self, fit_result):
        canvas = self._ensure_canvas()
        canvas.settings = dict(self.settings)
        canvas.update_plot(fit_result)

    def _draw_initial_placeholder(self):
        if self._canvas is not None:
            self._canvas._draw_initial_placeholder()

    def _draw_error_state(self, message):
        self._ensure_canvas()._draw_error_state(message)
