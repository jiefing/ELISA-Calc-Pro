# -*- coding: utf-8 -*-
"""
主窗口模块 (main_window.py) - V3.0
多模型酶免分析系统 (ELISA-Calc-Pro) V3.0
ELISA-Calc-Pro contributors

V3.0 新增（对齐 CurveExpert 1.4 全功能）：
  - 40+ 内置回归/插值模型，分族选择，多项式阶数可调
  - 权重回归（1/y²、1/y、1/x²、1/x、1/标准差²）
  - CurveFinder 自动寻优 + 右侧模型排名面板（点击切换）
  - 分析工具：y=f(x) 求值 / x=f(y) 反推 / 微分 / 积分 / 弧长
  - 数据变换（排序/缩放/平移/去离群点）与数据统计
  - 用户自定义模型（表达式语言与 CurveExpert 一致）
"""

import os
import sys
import csv
import ctypes
from ctypes import Structure, c_long, POINTER, cast
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QLabel, QPushButton, QTextEdit, QGroupBox, QSpinBox,
    QMessageBox, QApplication, QSizePolicy, QFileDialog, QMenu, QAction
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon

from core.data_models import StandardPoint, SamplePoint
from ui.table_widgets import StandardTableWidget, SampleTableWidget
from ui.lazy_plot_canvas import LazyPlotCanvas
from ui.ranking_panel import RankingPanel
from ui.preprocess_dialog import PreprocessDialog
from ui.plot_properties_dialog import PlotPropertiesDialog


# Windows 结构体定义，用于拦截窗口尺寸变化事件
class RECT(Structure):
    _fields_ = [
        ("left", c_long), ("top", c_long),
        ("right", c_long), ("bottom", c_long),
    ]


class MSG(Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint),
        ("wParam", ctypes.c_void_p), ("lParam", ctypes.c_void_p),
        ("time", ctypes.c_uint), ("pt_x", c_long), ("pt_y", c_long),
    ]


def _get_app_icon() -> QIcon:
    """加载应用图标，兼容源码运行和 PyInstaller 打包环境。"""
    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ico_path = os.path.join(base_dir, "assets", "logo.ico")
    if os.path.exists(ico_path):
        return QIcon(ico_path)
    return QIcon()


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("多模型酶免分析系统 (ELISA-Calc-Pro) V3.0")

        icon = _get_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        self._models = []
        self._math_api = None
        self._last_result = None
        self._last_strategy = None
        self._suppress_calc = False
        self._preprocess = {
            "blank_od": 0.0, "dilution_factor": 1.0,
            "batch_id": "", "plate_id": "",
        }

        self._apply_dpi_presets()
        self.setFont(QFont("Microsoft YaHei", self.preset_font_size))
        self._init_ui()
        self._bind_signals()
        self._show_initial_waiting_state()
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, self._load_heavy_components)

    def _apply_dpi_presets(self):
        """根据屏幕 DPI 设置窗口大小和字体。"""
        screen = QApplication.primaryScreen()
        dpi = screen.logicalDotsPerInch() if screen else 96.0

        if dpi <= 120.0:
            self.preset_win_width, self.preset_win_height = 1380, 860
            self.preset_font_size, self.preset_report_font = 9, 10
            self.preset_btn_height, self.preset_calc_btn_height = 30, 34
            self.preset_spacing = 10
        elif dpi <= 144.0:
            self.preset_win_width, self.preset_win_height = 1520, 950
            self.preset_font_size, self.preset_report_font = 10, 11
            self.preset_btn_height, self.preset_calc_btn_height = 33, 38
            self.preset_spacing = 12
        else:
            self.preset_win_width, self.preset_win_height = 1680, 1040
            self.preset_font_size, self.preset_report_font = 11, 12
            self.preset_btn_height, self.preset_calc_btn_height = 36, 42
            self.preset_spacing = 14

        self.target_aspect_ratio = float(self.preset_win_width) / float(self.preset_win_height)
        self.resize(self.preset_win_width, self.preset_win_height)
        self.setMinimumSize(int(self.preset_win_width * 0.65), int(self.preset_win_height * 0.65))

    def nativeEvent(self, eventType, message):
        """拦截 WM_SIZING 消息，锁定窗口宽高比。"""
        if eventType == "windows_generic_MSG":
            try:
                msg_ptr = int(message)
                msg = cast(msg_ptr, POINTER(MSG)).contents
                if msg.message == 0x0214:  # WM_SIZING
                    rect = cast(msg.lParam, POINTER(RECT)).contents
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                    target_ratio = getattr(self, "target_aspect_ratio", 1.6)
                    wParam = int(msg.wParam)

                    if wParam in (1, 2):  # 左/右边拖拽
                        rect.bottom = rect.top + int(w / target_ratio)
                    elif wParam in (3, 6):  # 上/下边拖拽
                        rect.right = rect.left + int(h * target_ratio)
                    else:  # 角落拖拽
                        new_h = int(w / target_ratio)
                        if wParam in (4, 5):
                            rect.top = rect.bottom - new_h
                        else:
                            rect.bottom = rect.top + new_h
                    return True, 0
            except Exception:
                pass
        return super().nativeEvent(eventType, message)

    def _apply_panel_width_limits(self, w: int):
        """限制左右面板宽度比例，防止图表区域被挤压。"""
        if hasattr(self, 'left_panel') and hasattr(self, 'right_panel'):
            self.left_panel.setMinimumWidth(int(w * 0.36))
            self.left_panel.setMaximumWidth(int(w * 0.42))
            self.right_panel.setMinimumWidth(int(w * 0.55))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_panel_width_limits(self.width())

    # ================= 界面构建 =================
    def _init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(self.preset_spacing + 2)

        # === 顶部：V3.0 分析工具箱 ===
        top_group = QGroupBox("V3.0 分析工具箱")
        top_layout = QHBoxLayout(top_group)
        top_layout.setSpacing(self.preset_spacing)

        top_layout.addWidget(QLabel("模型："))
        self.algo_combo = QComboBox()
        self.algo_combo.setFixedHeight(self.preset_btn_height - 2)
        self._fill_model_combo()
        top_layout.addWidget(self.algo_combo, stretch=3)

        top_layout.addWidget(QLabel("权重："))
        self.combo_weight = QComboBox()
        self.combo_weight.setFixedHeight(self.preset_btn_height - 2)
        self.combo_weight.addItems(["不加权", "1/y²", "1/y", "1/x²", "1/x", "1/标准差²"])
        top_layout.addWidget(self.combo_weight)

        top_layout.addWidget(QLabel("多项式阶数："))
        self.spin_poly = QSpinBox()
        self.spin_poly.setRange(2, 8)
        self.spin_poly.setValue(3)
        self.spin_poly.setFixedHeight(self.preset_btn_height - 2)
        top_layout.addWidget(self.spin_poly)

        self.btn_curve_finder = QPushButton("CurveFinder 自动寻优")
        self.btn_curve_finder.setFixedHeight(self.preset_btn_height)
        top_layout.addWidget(self.btn_curve_finder)
        self.btn_analyze = QPushButton("分析工具")
        self.btn_analyze.setFixedHeight(self.preset_btn_height)
        top_layout.addWidget(self.btn_analyze)
        self.btn_stats = QPushButton("数据统计")
        self.btn_stats.setFixedHeight(self.preset_btn_height)
        top_layout.addWidget(self.btn_stats)
        self.btn_transform = QPushButton("数据变换")
        self.btn_transform.setFixedHeight(self.preset_btn_height)
        top_layout.addWidget(self.btn_transform)
        self.btn_user_models = QPushButton("自定义模型")
        self.btn_user_models.setFixedHeight(self.preset_btn_height)
        top_layout.addWidget(self.btn_user_models)
        self.btn_preprocess = QPushButton("前处理设置")
        self.btn_preprocess.setFixedHeight(self.preset_btn_height)
        top_layout.addWidget(self.btn_preprocess)

        main_layout.addWidget(top_group)

        # === 中部：左右双栏 ===
        mid_layout = QHBoxLayout()
        mid_layout.setSpacing(self.preset_spacing + 4)

        # --- 左侧面板 ---
        self.left_panel = QWidget()
        self.left_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(self.preset_spacing)

        tables_container = QWidget()
        tables_layout = QVBoxLayout(tables_container)
        tables_layout.setContentsMargins(0, 0, 0, 0)
        tables_layout.setSpacing(self.preset_spacing)

        # 第一步：标准曲线计算
        std_group = QGroupBox("第一步：标准曲线计算")
        std_layout = QVBoxLayout(std_group)
        self.std_table = StandardTableWidget(std_group)
        std_layout.addWidget(self.std_table)

        std_row_btn1 = QHBoxLayout()
        self.btn_paste_std = QPushButton("从 Excel 粘贴标品数据")
        self.btn_paste_std.setFixedHeight(self.preset_btn_height)
        self.btn_clear_std = QPushButton("清空所有标准行")
        self.btn_clear_std.setFixedHeight(self.preset_btn_height)
        std_row_btn1.addWidget(self.btn_paste_std, stretch=3)
        std_row_btn1.addWidget(self.btn_clear_std, stretch=2)
        std_layout.addLayout(std_row_btn1)
        tables_layout.addWidget(std_group, stretch=4)

        # 第二步：样本测定与浓度求算
        sample_group = QGroupBox("第二步：样本测定与浓度求算")
        sample_layout = QVBoxLayout(sample_group)
        self.sample_table = SampleTableWidget(sample_group)
        sample_layout.addWidget(self.sample_table)

        samp_row_1 = QHBoxLayout()
        self.btn_paste_samp = QPushButton("从 Excel 粘贴样本数据")
        self.btn_paste_samp.setFixedHeight(self.preset_btn_height)
        self.btn_auto_merge = QPushButton("相同样本编号求均值")
        self.btn_auto_merge.setFixedHeight(self.preset_btn_height)
        samp_row_1.addWidget(self.btn_paste_samp, stretch=1)
        samp_row_1.addWidget(self.btn_auto_merge, stretch=1)

        samp_row_2 = QHBoxLayout()
        self.btn_copy_res = QPushButton("复制数据 (Ctrl+C)")
        self.btn_copy_res.setFixedHeight(self.preset_btn_height)
        self.btn_export_res = QPushButton("导出结果 (XLSX / CSV)")
        self.btn_export_res.setFixedHeight(self.preset_btn_height)
        self.btn_clear_samp = QPushButton("清空所有样本行")
        self.btn_clear_samp.setFixedHeight(self.preset_btn_height)
        samp_row_2.addWidget(self.btn_copy_res, stretch=2)
        samp_row_2.addWidget(self.btn_export_res, stretch=3)
        samp_row_2.addWidget(self.btn_clear_samp, stretch=2)

        sample_layout.addLayout(samp_row_1)
        sample_layout.addLayout(samp_row_2)
        tables_layout.addWidget(sample_group, stretch=6)

        # 计算按钮
        self.btn_calc = QPushButton("计算标曲与样本浓度")
        self.btn_calc.setFixedHeight(self.preset_calc_btn_height)
        self.btn_calc.setStyleSheet("background-color: #1976D2; color: white; font-weight: bold; border-radius: 4px;")
        tables_layout.addWidget(self.btn_calc)

        left_layout.addWidget(tables_container, stretch=1)
        left_layout.addWidget(QLabel(
            "<font color='#555'>提示：从 Excel 复制数据后在表格中按 <b>Ctrl+V</b> 粘贴；"
            "右键表格可合并复孔/计算 CV%；模型下拉框已按族分组。</font>"))

        mid_layout.addWidget(self.left_panel, stretch=4)

        # --- 右侧面板 ---
        self.right_panel = QWidget()
        self.right_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(self.preset_spacing)

        # 模型排名面板
        ranking_group = QGroupBox("模型排名 (CurveFinder 自动寻优)")
        ranking_layout = QVBoxLayout(ranking_group)
        self.ranking_panel = RankingPanel(ranking_group)
        ranking_layout.addWidget(self.ranking_panel)
        right_layout.addWidget(ranking_group, stretch=22)

        # 拟合分析曲线图
        plot_group = QGroupBox("第三步：拟合分析曲线图")
        plot_layout = QVBoxLayout(plot_group)
        self.canvas = LazyPlotCanvas(plot_group, width=7, height=5)
        plot_layout.addWidget(self.canvas)
        self.btn_plot_properties = QPushButton("图表属性")
        self.btn_plot_properties.setFixedHeight(self.preset_btn_height)
        plot_layout.addWidget(self.btn_plot_properties)
        right_layout.addWidget(plot_group, stretch=58)

        # 报告面板
        report_group = QGroupBox("第四步：相关性与拟合参数报告")
        report_layout = QVBoxLayout(report_group)
        report_btn_row = QHBoxLayout()
        report_btn_row.addStretch(1)
        report_btn_row.addWidget(QLabel("详细导出请使用窗口顶部【导出】菜单"))
        report_layout.addLayout(report_btn_row)
        self.txt_report = QTextEdit()
        self.txt_report.setReadOnly(True)
        self.txt_report.setFont(QFont("Consolas", self.preset_report_font))
        self.txt_report.setStyleSheet(
            "background-color: #F8F9FA; border: 1px solid #CED4DA; border-radius: 4px; padding: 6px; color: #212529;")
        report_layout.addWidget(self.txt_report)
        right_layout.addWidget(report_group, stretch=20)

        mid_layout.addWidget(self.right_panel, stretch=6)
        main_layout.addLayout(mid_layout, stretch=1)
        self._build_export_menu()
        self._apply_panel_width_limits(self.width())

    def _build_export_menu(self):
        export_menu = self.menuBar().addMenu("导出")
        act_data = QAction("样本结果（XLSX / CSV）", self)
        act_txt = QAction("拟合报告（TXT）", self)
        act_xlsx = QAction("完整实验报告（Excel）", self)
        act_plot = QAction("曲线图片（PNG / JPEG / SVG / PDF）", self)
        export_menu.addAction(act_data)
        export_menu.addSeparator()
        export_menu.addAction(act_txt)
        export_menu.addAction(act_xlsx)
        export_menu.addSeparator()
        export_menu.addAction(act_plot)
        act_data.triggered.connect(self._on_export_sample_results)
        act_txt.triggered.connect(self._on_export_report)
        act_xlsx.triggered.connect(self._on_export_excel_report)
        act_plot.triggered.connect(self._on_export_plot_image)

        settings_menu = self.menuBar().addMenu("设置")
        act_pre = QAction("实验前处理（空白/稀释/批次）", self)
        act_plot_prop = QAction("图表属性", self)
        settings_menu.addAction(act_pre)
        settings_menu.addAction(act_plot_prop)
        act_pre.triggered.connect(self._on_preprocess)
        act_plot_prop.triggered.connect(self._on_plot_properties)

    def _fill_model_combo(self, keep_name: str = ""):
        """按族填充模型下拉框（itemData 为策略实例）"""
        self.algo_combo.blockSignals(True)
        self.algo_combo.clear()
        for model in self._models:
            self.algo_combo.addItem(f"{model.family} | {model.name}", model)
            self.algo_combo.setItemData(self.algo_combo.count() - 1, model.description, Qt.ToolTipRole)
        if keep_name:
            for i in range(self.algo_combo.count()):
                if self.algo_combo.itemData(i).name == keep_name:
                    self.algo_combo.setCurrentIndex(i)
                    break
        elif self._models:
            self.algo_combo.setCurrentIndex(0)
        self.algo_combo.blockSignals(False)

    def _load_heavy_components(self):
        """窗口首次进入事件循环后再导入模型库和 SciPy 相关模块。"""
        if self._math_api is not None:
            return
        from math_engine import get_all_models, WEIGHT_MODES
        self._math_api = {
            "get_all_models": get_all_models,
            "WEIGHT_MODES": WEIGHT_MODES,
        }
        self._models = get_all_models()
        current = self.algo_combo.currentData()
        self._fill_model_combo(keep_name=getattr(current, "name", ""))
        if self._models:
            self.algo_combo.setCurrentIndex(0)

    def _bind_signals(self):
        self.btn_calc.clicked.connect(self.run_full_calculation)
        self.algo_combo.currentIndexChanged.connect(self.run_full_calculation)
        self.combo_weight.currentIndexChanged.connect(self.run_full_calculation)
        self.spin_poly.valueChanged.connect(self._on_poly_order_changed)
        self.btn_clear_std.clicked.connect(self._on_clear_standard)
        self.btn_copy_res.clicked.connect(self._on_copy_sample_results)
        self.btn_export_res.clicked.connect(self._on_export_sample_results)
        self.btn_clear_samp.clicked.connect(self._on_clear_samples)
        self.btn_paste_std.clicked.connect(self._on_paste_standard)
        self.btn_paste_samp.clicked.connect(self._on_paste_sample)
        self.btn_auto_merge.clicked.connect(self._on_auto_merge_samples)
        self.btn_plot_properties.clicked.connect(self._on_plot_properties)
        self.btn_preprocess.clicked.connect(self._on_preprocess)

        self.btn_curve_finder.clicked.connect(self._on_curve_finder)
        self.btn_analyze.clicked.connect(self._on_analyze)
        self.btn_stats.clicked.connect(self._on_stats)
        self.btn_transform.clicked.connect(self._on_transform)
        self.btn_user_models.clicked.connect(self._on_user_models)
        self.ranking_panel.model_selected.connect(self._load_ranked_result)

    def _on_poly_order_changed(self, _val):
        from math_engine.models_linear import PolynomialStrategy
        model = self.algo_combo.currentData()
        if isinstance(model, PolynomialStrategy):
            self.run_full_calculation()

    def _show_initial_waiting_state(self):
        """显示初始等待状态。"""
        self.canvas._draw_initial_placeholder()
        self.txt_report.setText(
            "【未计算】\n\n"
            "· 请在左侧输入标准品和样本数据，或使用【从 Excel 粘贴】按钮导入数据；\n"
            "· 顶部工具箱可选择模型族/权重/多项式阶数，点击【计算】开始；\n"
            "· 点击【CurveFinder 自动寻优】可一次遍历全部模型并按 R² 排名。"
        )

    # ================= 计算核心 =================
    def run_full_calculation(self):
        if self._suppress_calc:
            return
        if self._math_api is None:
            return
        model = self.algo_combo.currentData()
        if model is None:
            return
        weights = self._math_api["WEIGHT_MODES"][self.combo_weight.currentText()]
        from math_engine.models_linear import PolynomialStrategy
        if isinstance(model, PolynomialStrategy):
            model.order = self.spin_poly.value()

        std_tuples = self.std_table.get_valid_standard_data()
        sample_tuples = self.sample_table.get_sample_input_data()

        if len(std_tuples) < 2:
            if self.sender() == self.btn_calc:
                QMessageBox.information(self, "标准品不足",
                    "至少需要 2 组有效标准品数据才能进行拟合计算。\n\n请先填写标准品浓度和吸光度数据。")
            else:
                self._show_initial_waiting_state()
            return

        blank = float(self._preprocess.get("blank_od", 0.0))
        dilution = float(self._preprocess.get("dilution_factor", 1.0))
        std_points = [StandardPoint(x=x, y=y - blank, row_idx=idx) for (x, y, idx) in std_tuples]
        sample_points = [SamplePoint(sample_id=sid, y=y - blank, row_idx=idx) for (sid, y, idx) in sample_tuples]

        try:
            res = model.fit_and_predict(std_points, sample_points, weights=weights)
            if dilution != 1.0:
                for point in res.sample_points:
                    if isinstance(point.calc_x, float):
                        point.calc_x *= dilution
            res.preprocessing = dict(self._preprocess)
            self._display_result(res, model)
        except Exception as fe:
            from math_engine import FitEngineError
            if not isinstance(fe, FitEngineError):
                err_str = f"运算出错:\n{fe}"
                self.canvas._draw_error_state(err_str)
                self.txt_report.setText(err_str)
                if self.sender() == self.btn_calc:
                    QMessageBox.critical(self, "错误", err_str)
                return
            err_text = str(fe)
            self.canvas._draw_error_state(err_text)
            self.txt_report.setText(f"【拟合失败】\n\n当前模型 ({model.name}) 拟合未收敛:\n{err_text}")
            if self.sender() == self.btn_calc:
                QMessageBox.warning(self, "拟合失败", err_text)
    def _display_result(self, result, strategy=None):
        """将拟合结果渲染到样本表 / 曲线图 / 报告面板"""
        self.sample_table.update_calc_results(result.sample_points)
        self.canvas.update_plot(result)
        self.txt_report.setText(result.generate_report_text())
        self._last_result = result
        self._last_strategy = strategy if strategy is not None else self.algo_combo.currentData()

    def _load_ranked_result(self, strategy, result):
        """点击排名面板某一行：载入对应模型与结果"""
        if result is None:
            note = getattr(strategy, "description", "")
            QMessageBox.information(self, "拟合失败",
                f"模型 {strategy.name} 未能收敛。\n\n详情：{note}")
            return
        # 同步顶部下拉框（不触发重算）
        self._suppress_calc = True
        for i in range(self.algo_combo.count()):
            if self.algo_combo.itemData(i) is strategy or self.algo_combo.itemData(i).name == strategy.name:
                self.algo_combo.setCurrentIndex(i)
                break
        self._suppress_calc = False
        self._display_result(result, strategy)

    # ================= CurveFinder =================
    def _on_curve_finder(self):
        if self._math_api is None:
            return
        from ui.curve_finder_dialog import run_curve_finder_dialog
        blank = float(self._preprocess.get("blank_od", 0.0))
        std_tuples = [(x, y - blank, idx) for x, y, idx in self.std_table.get_valid_standard_data()]
        sample_tuples = [(sid, y - blank, idx) for sid, y, idx in self.sample_table.get_sample_input_data()]
        run_curve_finder_dialog(self, std_tuples, sample_tuples)

    def _on_curve_finder_results(self, entries):
        self.ranking_panel.set_entries(entries)
        best = self.ranking_panel.best_entry()
        if best is not None:
            self._load_ranked_result(best.strategy, best.result)
            QMessageBox.information(self, "CurveFinder 完成",
                f"自动寻优完成，共尝试 {len(entries)} 个模型。\n"
                f"最佳模型：{best.model_name}\nR² = {best.r_squared:.6f}，标准误 = {best.standard_error:.6g}\n\n"
                "右侧排名面板已列出全部结果，可点击任意行切换模型。")
        else:
            QMessageBox.warning(self, "CurveFinder 完成",
                f"共尝试 {len(entries)} 个模型，但全部拟合失败。\n"
                "请在排名面板查看各模型的失败原因，或检查数据质量。")

    # ================= 分析工具 / 统计 / 变换 / 自定义模型 =================
    def _on_analyze(self):
        if self._last_result is None or not self._last_result.success:
            QMessageBox.information(self, "尚无拟合结果", "请先完成一次计算，再使用分析工具。")
            return
        from ui.analyze_dialog import AnalyzeDialog
        dlg = AnalyzeDialog(self._last_result, self._last_strategy, self)
        dlg.exec_()

    def _on_stats(self):
        from ui.stats_dialog import StatsDialog
        dlg = StatsDialog(self.std_table, self.sample_table, self)
        dlg.exec_()

    def _on_transform(self):
        from ui.transform_dialog import TransformDialog
        dlg = TransformDialog(self.std_table, self.sample_table, self)
        dlg.exec_()

    def _on_user_models(self):
        from ui.user_model_dialog import UserModelDialog
        dlg = UserModelDialog(self)
        dlg.exec_()

    def _on_preprocess(self):
        dlg = PreprocessDialog(self._preprocess, self)
        if dlg.exec_():
            self._preprocess = dlg.values()
            if len(self.std_table.get_valid_standard_data()) >= 2:
                self.run_full_calculation()

    def _on_plot_properties(self):
        dlg = PlotPropertiesDialog(self.canvas.settings, self)
        if dlg.exec_():
            self.canvas.settings = dlg.values()
            if self._last_result is not None:
                self.canvas.update_plot(self._last_result)
            else:
                self.canvas._draw_initial_placeholder()

    def _refresh_user_models(self):
        """用户模型变更后刷新下拉框，保持当前选择"""
        keep = self.algo_combo.currentData().name if self.algo_combo.currentData() else ""
        self._fill_model_combo(keep_name=keep)

    # ================= 数据导入导出（沿用 V2.0） =================
    def _on_paste_standard(self):
        if self.std_table.paste_from_clipboard(show_info_if_empty=True):
            self.run_full_calculation()

    def _on_paste_sample(self):
        if self.sample_table.paste_from_clipboard(show_info_if_empty=True):
            self.run_full_calculation()

    def _on_auto_merge_samples(self):
        if self.sample_table.run_auto_merge_identical_ids(show_dialog=True):
            self.run_full_calculation()

    def _on_clear_standard(self):
        self.std_table.clearContents()
        self.std_table.setRowCount(12)
        self._show_initial_waiting_state()

    def _on_copy_sample_results(self):
        self.sample_table.selectAll()
        self.sample_table.copy_to_clipboard()
        self.sample_table.clearSelection()
        QMessageBox.information(self, "复制成功",
            "样本数据已复制到剪贴板。\n可在 Excel 中按 Ctrl+V 粘贴。")

    def _on_export_sample_results(self):
        """导出计算结果为 XLSX 或 CSV 文件。"""
        data_rows = []
        for r in range(self.sample_table.rowCount()):
            c_id = self.sample_table.item(r, 0)
            c_od = self.sample_table.item(r, 1)
            c_conc = self.sample_table.item(r, 2)

            sid_str = c_id.text().strip() if c_id else ""
            od_str = c_od.text().strip() if c_od else ""
            conc_str = c_conc.text().strip() if c_conc else ""

            if sid_str or od_str or conc_str:
                data_rows.append({
                    "样本编号": sid_str,
                    "吸光度 OD (Y)": od_str,
                    "计算浓度 (X)": conc_str
                })

        if not data_rows:
            QMessageBox.information(self, "无数据", "当前没有可导出的数据，请先输入样本数据并计算。")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出结果",
            "样本计算结果.xlsx",
            "Excel 文件 (*.xlsx);;CSV 文件 (*.csv);;所有文件 (*.*)"
        )
        if not file_path:
            return

        try:
            import pandas as pd
            df = pd.DataFrame(data_rows)
            if file_path.lower().endswith(".csv"):
                df.to_csv(file_path, index=False, encoding="utf-8-sig")
            else:
                if not file_path.lower().endswith(".xlsx"):
                    file_path += ".xlsx"
                df.to_excel(file_path, index=False, engine="openpyxl")
            QMessageBox.information(self, "导出成功", f"数据已导出到:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出时出错:\n{e}")

    def _on_export_plot_image(self):
        """导出曲线图片 (300 DPI)。"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出曲线图片",
            "标准曲线.png",
            "PNG 图片 (*.png);;JPEG 图片 (*.jpg *.jpeg);;SVG 矢量图 (*.svg);;PDF 文件 (*.pdf);;所有文件 (*.*)"
        )
        if not file_path:
            return

        try:
            self.canvas.fig.savefig(file_path, dpi=300, bbox_inches='tight', facecolor='#F8F9FA')
            QMessageBox.information(self, "导出成功", f"图片已导出到:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出图片时出错:\n{e}")

    def _on_export_report(self):
        """导出当前拟合报告（方程/参数/指标）为 TXT 文件"""
        if self._last_result is None:
            QMessageBox.information(self, "尚无拟合结果", "请先完成一次计算，再导出报告。")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出完整报告",
            f"拟合报告_{self._last_result.model_name.replace('/', '_')}.txt",
            "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self._last_result.generate_report_text())
                f.write(f"\n· 空白扣除 OD：{self._preprocess.get('blank_od', 0.0):.6g}\n")
                f.write(f"· 样本稀释倍数：{self._preprocess.get('dilution_factor', 1.0):.6g}\n")
                f.write(f"· 校准批次：{self._preprocess.get('batch_id', '')}\n")
                f.write(f"· 校准板号：{self._preprocess.get('plate_id', '')}\n")
                f.write("\n\n===== 样本反推明细 =====\n")
                for p in self._last_result.sample_points:
                    f.write(f"{p.sample_id or '(未编号)'}\t{p.y:.6g}\t{p.calc_x}\n")
            QMessageBox.information(self, "导出成功", f"报告已导出到:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出报告时出错:\n{e}")

    def _on_export_excel_report(self):
        """导出标准品、样本、拟合参数和文字摘要组成的完整 Excel 报告。"""
        if self._last_result is None or not self._last_result.success:
            QMessageBox.information(self, "尚无拟合结果", "请先完成一次计算，再导出完整 Excel 报告。")
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出完整 Excel 报告", "ELISA_完整实验报告.xlsx",
            "Excel 文件 (*.xlsx);;所有文件 (*.*)"
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".xlsx"):
            file_path += ".xlsx"
        try:
            blank = float(self._preprocess.get("blank_od", 0.0))
            dilution = float(self._preprocess.get("dilution_factor", 1.0))
            std_rows = [{"浓度 X": p.x, "原始 OD": p.y + blank, "扣空白后 OD": p.y}
                        for p in self._last_result.std_points]
            sample_rows = []
            for p in self._last_result.sample_points:
                pre_dilution = p.calc_x
                if isinstance(p.calc_x, float) and dilution:
                    pre_dilution = p.calc_x / dilution
                sample_rows.append({
                    "样本编号": p.sample_id,
                    "原始 OD": p.y + blank,
                    "扣空白后 OD": p.y,
                    "计算浓度（稀释前）": pre_dilution,
                    "稀释倍数": dilution,
                    "最终浓度": p.calc_x,
                })
            params = [
                {"项目": "模型名称", "值": self._last_result.model_name},
                {"项目": "模型族", "值": self._last_result.family},
                {"项目": "方程", "值": self._last_result.equation_str},
                {"项目": "R²", "值": self._last_result.r_squared},
                {"项目": "标准误 SE", "值": self._last_result.standard_error},
                {"项目": "AIC", "值": self._last_result.aic},
                {"项目": "空白扣除 OD", "值": blank},
                {"项目": "样本稀释倍数", "值": dilution},
                {"项目": "校准批次", "值": self._preprocess.get("batch_id", "")},
                {"项目": "校准板号", "值": self._preprocess.get("plate_id", "")},
            ]
            import pandas as pd
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                pd.DataFrame(std_rows).to_excel(writer, sheet_name="标准品与校准", index=False)
                pd.DataFrame(sample_rows).to_excel(writer, sheet_name="样本结果", index=False)
                pd.DataFrame(params).to_excel(writer, sheet_name="拟合参数", index=False)
                pd.DataFrame([{"报告": self._last_result.generate_report_text()}]).to_excel(
                    writer, sheet_name="文字报告", index=False)
            QMessageBox.information(self, "导出成功", f"完整 Excel 报告已导出到：\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出完整 Excel 报告时出错：\n{e}")

    def _on_clear_samples(self):
        self.sample_table.clearContents()
        self.sample_table.setRowCount(22)
        if len(self.std_table.get_valid_standard_data()) >= 2:
            self.run_full_calculation()
        else:
            self._show_initial_waiting_state()
