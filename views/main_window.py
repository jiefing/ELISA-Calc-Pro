# -*- coding: utf-8 -*-
"""
主窗口 UI 框架 - MainWindow
集成了顶层控制、孔板表格交互、各类实验动态参数板与结果展示看板。
标题栏：“ELISA-Calc-Pro --- ELISA-Calc-Pro”
"""

import os
from typing import List, Dict, Optional

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QLabel, QSplitter, QFrame,
    QMessageBox, QStatusBar, QGroupBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QCheckBox, QAbstractItemView,
    QHeaderView, QStackedWidget, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QDoubleValidator

from models.data_structures import Plate, WellType, Well
from views.plate_widget import PlateWidget
from controllers.app_controller import AppController


# ─────────────────────────────────────────────────────────────────────
# 1. 策略专属参数子面板 (搬移合并，确保 views 目录绝对精炼)
# ─────────────────────────────────────────────────────────────────────

class BlankSubtractionParamWidget(QWidget):
    """基础扣减模式：无需额外参数"""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        info = QLabel(
            "基础扣减模式\n\n"
            "• 自动计算所有 Blank（空白）孔的均值\n"
            "• 将所有待测孔的 OD 值减去空白均值\n"
            "• 结果为背景校正后的净 OD 值\n\n"
            "无需额外参数，直接点击'开始计算'即可。"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #000000; font-size: 9pt; line-height: 1.4;")
        layout.addWidget(info)
        layout.addStretch()

    def get_params(self) -> dict:
        return {}


class FourPLParamWidget(QWidget):
    """
    4PL ELISA 参数面板：标准品浓度输入表
    4.2 标曲浓度“秒赋”复孔功能核心实现
    """
    DEFAULT_STD_CONCS = [0.0, 3.9, 7.8, 15.6, 31.25, 62.5, 125.0, 250.0]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.std_wells: List[Well] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)

        info = QLabel(
            "四参数逻辑回归（4PL）ELISA\n"
            "请在下表中指定各 Standard（标曲）孔对应的已知浓度值："
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #000000; font-size: 9pt;")
        layout.addWidget(info)

        # 标准品浓度设置分组框
        group = QGroupBox("标准品浓度设置")
        g_layout = QVBoxLayout(group)

        self.std_table = QTableWidget(8, 2)
        self.std_table.setHorizontalHeaderLabels(["孔位编号", "浓度值"])
        self.std_table.setVerticalHeaderLabels([f"Std {i+1}" for i in range(8)])
        self.std_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.std_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.std_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.std_table.setEditTriggers(
            QAbstractItemView.DoubleClicked |
            QAbstractItemView.SelectedClicked
        )

        for i, conc in enumerate(self.DEFAULT_STD_CONCS):
            id_item = QTableWidgetItem(f"Std {i+1}")
            id_item.setFlags(Qt.ItemIsEnabled)
            id_item.setTextAlignment(Qt.AlignCenter)
            self.std_table.setItem(i, 0, id_item)

            conc_item = QTableWidgetItem(str(conc))
            conc_item.setTextAlignment(Qt.AlignCenter)
            self.std_table.setItem(i, 1, conc_item)

        # 4.2 绑定 cellChanged 信号以执行标曲浓度“秒赋”
        self.std_table.cellChanged.connect(self._on_cell_changed)
        g_layout.addWidget(self.std_table)

        # 浓度单位
        unit_layout = QHBoxLayout()
        unit_label = QLabel("浓度单位：")
        self.unit_edit = QLineEdit("ng/mL")
        self.unit_edit.setFixedWidth(100)
        unit_layout.addWidget(unit_label)
        unit_layout.addWidget(self.unit_edit)
        unit_layout.addStretch()
        g_layout.addLayout(unit_layout)

        # 扣减空白
        self.subtract_blank_cb = QCheckBox("计算前先扣减 Blank 空白值")
        self.subtract_blank_cb.setChecked(True)
        g_layout.addWidget(self.subtract_blank_cb)

        layout.addWidget(group)

    def _on_cell_changed(self, row: int, column: int):
        """
        4.2 标曲浓度“秒赋”复孔功能：
        多选状态下编辑某行自动遍历同步覆盖，并实时更新 Model 中对应的 Well.std_conc。
        """
        if column != 1:
            return
        item = self.std_table.item(row, column)
        if not item:
            return
        text = item.text().strip()

        # 屏蔽信号防递归死循环
        self.std_table.blockSignals(True)
        try:
            # 扫描所有选中单元格所在的行
            selected_rows = set(idx.row() for idx in self.std_table.selectedIndexes())

            # 更新当前修改行 model 中的 well 属性
            if row < len(self.std_wells):
                try:
                    self.std_wells[row].std_conc = float(text) if text else None
                except ValueError:
                    self.std_wells[row].std_conc = None

            # 同步多选其他选中的行
            if row in selected_rows:
                for r in selected_rows:
                    if r != row:
                        t_item = self.std_table.item(r, column)
                        if t_item:
                            t_item.setText(text)
                        # 更新 model
                        if r < len(self.std_wells):
                            try:
                                self.std_wells[r].std_conc = float(text) if text else None
                            except ValueError:
                                self.std_wells[r].std_conc = None
        except Exception as e:
            pass
        finally:
            self.std_table.blockSignals(False)

    def update_std_list(self, std_wells: List[Well]):
        """根据当前板上标注的 Standard 孔位动态更新列表并绑定 well 数据"""
        self.std_wells = std_wells

        self.std_table.blockSignals(True)
        try:
            count = len(std_wells)
            self.std_table.setRowCount(count)
            self.std_table.setVerticalHeaderLabels([f"Std {i+1}" for i in range(count)])

            for i, well in enumerate(std_wells):
                lbl_item = QTableWidgetItem(well.label)
                lbl_item.setFlags(Qt.ItemIsEnabled)
                lbl_item.setTextAlignment(Qt.AlignCenter)
                self.std_table.setItem(i, 0, lbl_item)

                conc_str = f"{well.std_conc}" if well.std_conc is not None else ""
                conc_item = QTableWidgetItem(conc_str)
                conc_item.setTextAlignment(Qt.AlignCenter)
                self.std_table.setItem(i, 1, conc_item)
        finally:
            self.std_table.blockSignals(False)

    def get_params(self) -> dict:
        concentrations = []
        for i in range(self.std_table.rowCount()):
            item = self.std_table.item(i, 1)
            if item:
                try:
                    concentrations.append(float(item.text()))
                except ValueError:
                    concentrations.append(0.0)
            else:
                concentrations.append(0.0)
        return {
            "std_concentrations": concentrations,
            "subtract_blank": self.subtract_blank_cb.isChecked(),
            "unit": self.unit_edit.text().strip() or "ng/mL",
        }


class CellViabilityParamWidget(QWidget):
    """CCK-8/MTT 细胞活力参数提示"""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        info = QLabel(
            "细胞活力计算（CCK-8 / MTT）\n\n"
            "计算公式：\n"
            "  相对活力(%) = (Sample - Blank均值) / "
            "(Control - Blank均值) × 100\n\n"
            "请确保已在左侧孔板上标记以下孔位类型：\n"
            "  Blank   — 空白对照（试剂背景）\n"
            "  Control — 正常对照（细胞阴性，作为 100% 相对值）\n"
            "  Sample  — 样品实验组\n\n"
            "注：如果未设定 Control，系统将自动降级计算为绝对背景扣减净值。"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #000000; font-size: 9pt; line-height: 1.4;")
        layout.addWidget(info)
        layout.addStretch()

    def get_params(self) -> dict:
        return {}


class StrategyParamPanel(QStackedWidget):
    """
    策略参数堆栈面板
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._param_widgets = []
        self._build_pages()

    def _build_pages(self):
        widget_classes = [
            BlankSubtractionParamWidget,
            FourPLParamWidget,
            CellViabilityParamWidget,
        ]
        for cls in widget_classes:
            w = cls()
            self.addWidget(w)
            self._param_widgets.append(w)

    def switch_to(self, index: int):
        if 0 <= index < len(self._param_widgets):
            self.setCurrentIndex(index)

    def get_current_params(self) -> dict:
        idx = self.currentIndex()
        if 0 <= idx < len(self._param_widgets):
            return self._param_widgets[idx].get_params()
        return {}

    def get_four_pl_widget(self) -> FourPLParamWidget:
        return self._param_widgets[1]


# ─────────────────────────────────────────────────────────────────────
# 2. 统计/计算结果展示看板 (搬移合并)
# ─────────────────────────────────────────────────────────────────────

class ResultPanel(QGroupBox):
    """
    实验结果汇总看板。
    展示 4PL 拟合参数（A, B, C, D）、R² 以及 CV% 质控警告和 CCK-8 降级警告等。
    """
    def __init__(self, parent=None):
        super().__init__("计算结果汇总", parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 状态指示
        self.status_lbl = QLabel("尚未运行任何计算")
        self.status_lbl.setStyleSheet("color: #000080; font-weight: bold; font-size: 10pt;")
        layout.addWidget(self.status_lbl)

        # 参数明细展示框
        self.detail_txt = QLabel("请配置参数并点击“开始计算”以展示详情。")
        self.detail_txt.setWordWrap(True)
        self.detail_txt.setStyleSheet("line-height: 1.4; color: #000000;")
        layout.addWidget(self.detail_txt)

        self.export_btn = QPushButton("导出计算报表 (Excel)")
        self.export_btn.setEnabled(False)
        layout.addWidget(self.export_btn)

        layout.addStretch()

    def show_results(self, plate: Plate, strategy_index: int):
        """拉取 Model 统计数据并在看板上做 XP 立体渲染展示"""
        self.status_lbl.setText("计算执行成功！")
        self.export_btn.setEnabled(True)

        lines = []
        if strategy_index == 0:  # 基础扣减
            blank_mean = plate.statistics.get("blank_mean", 0.0)
            lines.append(f"• 试剂空白 (Blank) 平均 OD: {blank_mean:.4f}")
            lines.append("• 所有待测孔已完成背景值物理扣减。")

        elif strategy_index == 1:  # 4PL ELISA
            popt = plate.statistics.get("popt")
            r_sq = plate.statistics.get("r_squared", 0.0)
            blank_mean = plate.statistics.get("blank_mean", 0.0)

            lines.append(f"• 试剂空白 (Blank) 平均 OD: {blank_mean:.4f}")
            if popt and len(popt) == 4:
                A, B, C, D = popt
                lines.append("• 4PL 曲线拟合参数：")
                lines.append(f"  - 下限渐近值 (A): {A:.4f}")
                lines.append(f"  - 曲线斜率值 (B): {B:.4f}")
                lines.append(f"  - 效应浓度值 (C): {C:.4f}")
                lines.append(f"  - 上限渐近值 (D): {D:.4f}")
                lines.append(f"• 拟合决定系数 (R²): {r_sq:.5f}")
            else:
                lines.append("• 4PL 曲线拟合失败，未能计算参数")

            # 4.2 质控警告信息渲染
            cv_warns = plate.statistics.get("cv_warnings", [])
            if cv_warns:
                lines.append("\n[警告质控警告提示]：")
                for w in cv_warns:
                    lines.append(f"  ⚠️ {w}")
                self.status_lbl.setText("计算完成 (存在质控警告！)")

        elif strategy_index == 2:  # CCK-8 活力
            blank_mean = plate.statistics.get("blank_mean", 0.0)
            control_mean = plate.statistics.get("control_mean", None)
            lines.append(f"• 试剂空白 (Blank) 平均 OD: {blank_mean:.4f}")

            if control_mean is not None:
                lines.append(f"• 正常对照 (Control) 平均 OD: {control_mean:.4f}")
                lines.append("• 细胞活力百分比计算成功。")
            else:
                lines.append("• 警告：未设定 Control 对照孔！")
                lines.append("  已自动降级为绝对背景扣减净 OD 值展示。")

            # 3.2 细胞活力降级机制警告渲染
            warns = plate.statistics.get("warnings", [])
            if warns:
                lines.append("\n[系统降级提示]：")
                for w in warns:
                    lines.append(f"  ⚠️ {w}")
                self.status_lbl.setText("计算完成 (已降级模式运行！)")

        self.detail_txt.setText("\n".join(lines))

    def reset_status(self):
        self.status_lbl.setText("尚未运行任何计算")
        self.detail_txt.setText("请配置参数并点击“开始计算”以展示详情。")
        self.export_btn.setEnabled(False)


# ─────────────────────────────────────────────────────────────────────
# 3. 主窗口 MainWindow 类
# ─────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    """应用主窗口"""

    def __init__(self, controller: AppController):
        super().__init__()
        self.controller = controller
        self.controller.set_main_window(self)
        self.plate: Plate = None
        self._init_ui()
        self._load_global_style()

    def _init_ui(self):
        # 窗口基本属性 (符合任务书标题硬性要求)
        self.setWindowTitle("ELISA-Calc-Pro --- ELISA-Calc-Pro")
        self.resize(1200, 900)
        self.setMinimumSize(1000, 750)

        # 主中心控件
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # 1. 顶层控制区
        top_bar = QHBoxLayout()
        top_bar.setSpacing(15)

        self.import_btn = QPushButton("导入数据文件")
        self.import_btn.clicked.connect(self._import_file)
        top_bar.addWidget(self.import_btn)

        mode_label = QLabel("实验计算模式：")
        mode_label.setStyleSheet("font-size: 10pt; font-weight: bold; color: #000080; background-color: transparent;")
        top_bar.addWidget(mode_label)

        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(self.controller.get_strategy_names())
        self.strategy_combo.currentIndexChanged.connect(self._on_strategy_changed)
        self.strategy_combo.setMinimumWidth(250)
        top_bar.addWidget(self.strategy_combo)

        self.calc_btn = QPushButton("开始计算")
        self.calc_btn.clicked.connect(self._run_calculation)
        self.calc_btn.setStyleSheet("font-weight: bold;")
        top_bar.addWidget(self.calc_btn)

        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # 2. 中间分割布局 (左侧孔板，右侧参数/结果)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #d0d0d0; }")

        # 左侧孔板框 (改用 QSplitter(Qt.Vertical) 以便用户自由上下拉伸图表与孔板表格)
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 5, 0)
        left_layout.setSpacing(0)

        left_splitter = QSplitter(Qt.Vertical)
        left_splitter.setStyleSheet("QSplitter::handle { background-color: #d0d0d0; }")

        # 3.2 嵌入专业级 4PL 拟合曲线图组件到左侧顶部
        from views.curve_plot_widget import CurvePlotWidget
        self.curve_plot_widget = CurvePlotWidget()
        left_splitter.addWidget(self.curve_plot_widget)

        # 下半部分放提示和孔板表格
        bottom_container = QWidget()
        bottom_container_layout = QVBoxLayout(bottom_container)
        bottom_container_layout.setContentsMargins(0, 5, 0, 0)
        bottom_container_layout.setSpacing(5)

        self.info_lbl = QLabel("使用提示：鼠标左键框选表格，右键指定孔位类别 (Standard/Sample/Blank/Control/Unused)。")
        self.info_lbl.setStyleSheet("color: #555555; font-size: 8pt; background-color: transparent;")
        bottom_container_layout.addWidget(self.info_lbl)

        # 引入重写后的 PlateWidget，完全解离选中背景色
        self.plate_widget = PlateWidget()
        self.plate_widget.well_type_changed.connect(self._on_well_type_changed)
        bottom_container_layout.addWidget(self.plate_widget)

        left_splitter.addWidget(bottom_container)

        # 初始分配比例：标曲图占 42%，孔板表格占 58%
        left_splitter.setSizes([330, 450])
        left_layout.addWidget(left_splitter)

        splitter.addWidget(left_frame)

        # 右侧参数与结果区 (改用 QSplitter(Qt.Vertical) 彻底消除 std_table 高度 Expanding 对 result_panel 导出按钮的截断挤压)
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(5, 0, 5, 10)  # 底边留出 10px 呼吸间距，防止按钮贴底
        right_layout.setSpacing(0)

        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.setStyleSheet("QSplitter::handle { background-color: #d0d0d0; }")

        # 参数面板
        self.param_panel = StrategyParamPanel()
        right_splitter.addWidget(self.param_panel)

        # 结果汇总看板
        self.result_panel = ResultPanel()
        self.result_panel.export_btn.clicked.connect(self._export_report)
        right_splitter.addWidget(self.result_panel)

        # 初始分配比例：参数设置占 50%，结果看板占 50%
        right_splitter.setSizes([360, 360])
        right_layout.addWidget(right_splitter)

        splitter.addWidget(right_frame)

        # 初始分配比例：左侧 65%，右侧 35%
        splitter.setSizes([750, 400])
        main_layout.addWidget(splitter)

        # 3. 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("系统就绪，请先导入数据文件进行框选。")

    def _load_global_style(self):
        """读取 style_xp.qss 的样式表"""
        qss_path = os.path.join(os.path.dirname(__file__), "style_xp.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def load_plate_data(self, plate: Plate):
        """挂载孔板并初始化界面视图"""
        self.plate = plate
        self.plate_widget.load_plate(plate)
        self.result_panel.reset_status()
        self.curve_plot_widget.clear_plot()
        self._on_well_type_changed()
        self.status_bar.showMessage(f"成功导入数据源：{os.path.basename(plate.source_file)}")

    def _import_file(self):
        """导入事件"""
        self.controller.import_file()

    def _on_strategy_changed(self, index: int):
        """下拉计算类型改变"""
        self.param_panel.switch_to(index)
        self.curve_plot_widget.clear_plot()
        self.status_bar.showMessage(f"实验模式切换为: {self.controller.get_strategy_names()[index]}")

    def _on_well_type_changed(self):
        """孔板标记类别改变时，实时通知 4PL 参数列表更新绑定的标曲 Standard 孔"""
        if self.plate is None:
            return
        std_wells = self.plate.get_wells_by_type(WellType.STANDARD)
        self.param_panel.get_four_pl_widget().update_std_list(std_wells)

    def _run_calculation(self):
        """运行计算"""
        if self.plate is None:
            QMessageBox.warning(self, "警告", "请先导入酶标仪数据文件。")
            return

        strategy_idx = self.strategy_combo.currentIndex()
        params = self.param_panel.get_current_params()

        try:
            self.controller.run_calculation(strategy_idx, params)
            # 刷新结果表格和结果显示看板
            self.plate_widget.update_results()
            self.result_panel.show_results(self.plate, strategy_idx)

            # 3.3 标曲可视化联动绘图
            if strategy_idx == 1:
                popt = self.plate.statistics.get("popt")
                r_squared = self.plate.statistics.get("r_squared", 0.0)
                std_pts = self.plate.statistics.get("std_points", [])
                sample_pts = self.plate.statistics.get("sample_points", [])

                std_x = [pt[0] for pt in std_pts]
                std_y = [pt[1] for pt in std_pts]
                sample_x = [pt[0] for pt in sample_pts]
                sample_y = [pt[1] for pt in sample_pts]

                self.curve_plot_widget.plot_curve(popt, std_x, std_y, sample_x, sample_y, r_squared)
            else:
                self.curve_plot_widget.clear_plot()

            self.status_bar.showMessage("实验结果计算完毕，可一键导出 Excel 报表。")
        except Exception as e:
            QMessageBox.critical(self, "计算错误", f"算法拟合运行失败：\n{e}")
            self.status_bar.showMessage("计算中断。")

    def _export_report(self):
        """导出"""
        if self.plate is None:
            return
        self.controller.export_report()

    def grab_screenshot(self, filepath: str) -> bool:
        """
        截取当前主窗口的屏幕截图并保存为图片文件。
        """
        try:
            from PyQt5.QtWidgets import QApplication
            QApplication.processEvents()
            pixmap = self.grab()
            return pixmap.save(filepath, "PNG")
        except Exception as e:
            print(f"[截图失败] {e}")
            return False
