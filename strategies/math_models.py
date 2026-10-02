# -*- coding: utf-8 -*-
"""
算法策略实现层 (Strategy)
包含具体策略：4PL拟合、基础扣减、CCK-8细胞活力
"""

import logging
import numpy as np
from scipy.optimize import curve_fit
from collections import defaultdict

from models.data_structures import Plate, WellType, Well
from .base_strategy import BaseAssayStrategy, StrategyError

logger = logging.getLogger("MathModels")


# ─────────────────────────────────────────────────────────────────────
# 1. 基础扣减模式策略
# ─────────────────────────────────────────────────────────────────────

class BlankSubtractionStrategy(BaseAssayStrategy):
    """
    基础扣减策略 (OD 值背景校正)
    计算公式：Sample_corrected = Sample - Mean(Blank)
    任何计算均基于 Well.corrected_value 实施
    """
    @property
    def name(self) -> str:
        return "基础扣减模式 (OD 值校正)"

    @property
    def description(self) -> str:
        return ("计算并扣除所有 Blank(空白) 孔的均值，对待测孔的原始值进行校正。\n"
                "无额外参数，直接计算即可。")

    def calculate(self, plate: Plate, params: dict = None) -> Plate:
        logger.info("启动基础扣减策略计算...")

        # 1. 收集 Blank 孔
        blank_wells = plate.get_wells_by_type(WellType.BLANK)
        # 获取其 corrected_value (主-参比波长净值)
        blank_vals = [w.corrected_value for w in blank_wells if w.raw_value is not None]

        blank_mean = np.mean(blank_vals) if blank_vals else 0.0
        plate.statistics["blank_mean"] = blank_mean
        logger.info(f"Blank 平均 OD 值: {blank_mean:.4f}")

        # 2. 扣除 Blank 均值
        for well in plate.all_wells():
            if well.well_type == WellType.UNUSED:
                well.calc_result = None
                continue

            if well.raw_value is not None:
                well.calc_result = well.corrected_value - blank_mean
            else:
                well.calc_result = None

        logger.info("基础扣减计算完毕！")
        return self.post_process_samples(plate)


# ─────────────────────────────────────────────────────────────────────
# 2. 4PL ELISA 曲线拟合策略
# ─────────────────────────────────────────────────────────────────────

def four_pl_func(x, A, B, C, D):
    """
    四参数逻辑回归 (4PL) 方程：
    y = D + (A - D) / (1 + (x / C) ** B)
    """
    return D + (A - D) / (1.0 + (x / C) ** B)

class FourPLStrategy(BaseAssayStrategy):
    """
    四参数逻辑回归 (4PL) 曲线拟合策略
    利用标准曲线已知的浓度值与 OD 读数拟合曲线，反推待测样品的实际浓度。
    任何计算均基于 Well.corrected_value 实施
    """
    @property
    def name(self) -> str:
        return "四参数逻辑回归 (4PL) ELISA"

    @property
    def description(self) -> str:
        return ("根据标曲(Standard)孔的已知浓度和OD读数，利用Levenberg-Marquardt算法拟合4PL曲线，\n"
                "并自动计算待测样品的反推浓度。若样品读数超出渐近线极值，自动安全拦截标注为 >Max 或 <Min。")

    def calculate(self, plate: Plate, params: dict = None) -> Plate:
        logger.info("启动 4PL ELISA 曲线拟合策略...")

        # 清理统计结果
        plate.statistics.clear()

        # 1. 提取标曲浓度设置
        if not params or "std_concentrations" not in params:
            raise StrategyError("未配置标准品浓度参数")
        std_concs = params["std_concentrations"]
        subtract_blank = params.get("subtract_blank", True)

        # 2. 提取 Blank 值以作校准
        blank_wells = plate.get_wells_by_type(WellType.BLANK)
        blank_vals = [w.corrected_value for w in blank_wells if w.raw_value is not None]
        blank_mean = np.mean(blank_vals) if blank_vals else 0.0
        plate.statistics["blank_mean"] = blank_mean

        # 3. 收集 Standard 孔位数据进行曲线拟合
        std_wells = plate.get_wells_by_type(WellType.STANDARD)
        x_data = [] # 浓度
        y_data = [] # 校正/原始 OD 值

        # 同步浓度值并收集散点
        for i, well in enumerate(std_wells):
            if i < len(std_concs):
                well.std_conc = std_concs[i]
            if well.std_conc is not None and well.raw_value is not None:
                # 浓度自变量为标曲设定值，因变量做 corrected_value 背景校正
                x_data.append(well.std_conc)
                y_val = well.corrected_value
                if subtract_blank:
                    y_val -= blank_mean
                y_data.append(y_val)

        if len(x_data) < 4:
            raise StrategyError(f"4PL 拟合需要至少 4 个标曲数据点，当前仅有 {len(x_data)} 个有效标曲点！")

        x_arr = np.array(x_data, dtype=float)
        y_arr = np.array(y_data, dtype=float)

        # 4. 执行 LM (Levenberg-Marquardt) 曲线拟合
        # 4PL 初值猜测：
        # A: 最小 OD，D: 最大 OD，C: EC50 (浓度中位数)，B: 斜率 (设为 1.0)
        min_y = np.min(y_arr)
        max_y = np.max(y_arr)
        mid_x = np.median(x_arr) if len(x_arr) > 0 else 1.0
        initial_guess = [min_y, 1.0, mid_x, max_y]

        # 为了避免 x <= 0 时 4PL 幂运算出现复数，我们对自变量 x 作微小浮动校正或限制
        # 对于浓度为 0 的空白孔，为了代入回归，将其浓度修改为极小值（如 1e-6）以防开方无解
        x_arr_fit = np.where(x_arr <= 0, 1e-6, x_arr)

        try:
            popt, pcov = curve_fit(
                four_pl_func, x_arr_fit, y_arr,
                p0=initial_guess,
                method='lm',
                maxfev=10000
            )
            A, B, C, D = popt
            logger.info(f"4PL 拟合成功：A={A:.4f}, B={B:.4f}, C={C:.4f}, D={D:.4f}")
        except Exception as e:
            raise StrategyError(f"Levenberg-Marquardt 4PL 拟合迭代失败：\n{e}")

        # 计算决定系数 R²
        residuals = y_arr - four_pl_func(x_arr_fit, A, B, C, D)
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((y_arr - np.mean(y_arr))**2)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-9 else 0.0

        plate.statistics["popt"] = [float(A), float(B), float(C), float(D)]
        plate.statistics["r_squared"] = float(r_squared)

        # 5. STANDARD 孔的 CV% 质控计算
        std_groups = defaultdict(list)
        for i, well in enumerate(std_wells):
            if well.std_conc is not None and well.raw_value is not None:
                # 记录拟合前数据
                y_val = well.corrected_value
                if subtract_blank:
                    y_val -= blank_mean
                std_groups[well.std_conc].append(y_val)

        cv_warnings = []
        for conc, vals in std_groups.items():
            if len(vals) > 1:
                mean_val = np.mean(vals)
                std_val = np.std(vals, ddof=1)
                if mean_val > 1e-5:
                    cv_pct = (std_val / mean_val) * 100.0
                    if cv_pct > 15.0:
                        cv_warnings.append(f"标曲浓度 {conc} 的重复孔 CV% ({cv_pct:.1f}%) 超过 15% 限制！")

        if cv_warnings:
            plate.statistics["cv_warnings"] = cv_warnings
            logger.warning(f"检测到 CV% 质控警告：{cv_warnings}")

        # 6. 利用拟合方程反推样品浓度并作极值拦截
        # 渐近线上下限判断
        min_asymptote = min(A, D)
        max_asymptote = max(A, D)

        for well in plate.all_wells():
            if well.well_type == WellType.UNUSED:
                well.calc_result = None
                continue

            if well.raw_value is not None:
                # 获取净 OD
                y_target = well.corrected_value
                if subtract_blank:
                    y_target -= blank_mean

                # 标准品孔直接把输入的已知浓度作为计算结果展示，其余的进行反推
                if well.well_type == WellType.STANDARD:
                    well.calc_result = well.std_conc
                    continue

                # 极限拦截防崩溃运算
                if y_target > max_asymptote:
                    well.calc_result = ">Max"
                elif y_target < min_asymptote:
                    well.calc_result = "<Min"
                else:
                    try:
                        # 4PL 反推方程求解 x:
                        ratio = (A - D) / (y_target - D) - 1.0
                        if ratio < 0:
                            well.calc_result = ">Max" if B > 0 else "<Min"
                        else:
                            conc_calc = C * (ratio ** (1.0 / B))
                            well.calc_result = float(conc_calc)
                    except:
                        well.calc_result = "Err"
            else:
                well.calc_result = None

        # 7. 导出 std_points 和 sample_points 供前端绘图使用
        std_points = []
        for well in std_wells:
            if well.std_conc is not None and well.raw_value is not None:
                y_val = well.corrected_value
                if subtract_blank:
                    y_val -= blank_mean
                std_points.append((float(well.std_conc), float(y_val)))

        sample_points = []
        for well in plate.all_wells():
            if well.well_type == WellType.SAMPLE and well.raw_value is not None:
                if isinstance(well.calc_result, float):
                    y_val = well.corrected_value
                    if subtract_blank:
                        y_val -= blank_mean
                    sample_points.append((float(well.calc_result), float(y_val)))

        plate.statistics["std_points"] = std_points
        plate.statistics["sample_points"] = sample_points

        logger.info("4PL 标曲拟合与浓度反推计算执行成功！")
        return self.post_process_samples(plate)


# ─────────────────────────────────────────────────────────────────────
# 3. CCK-8 / MTT 细胞活力策略
# ─────────────────────────────────────────────────────────────────────

class CellViabilityStrategy(BaseAssayStrategy):
    """
    细胞活力策略 (CCK-8 / MTT)
    公式：Viability = (Sample - Blank_avg) / (Control - Blank_avg) * 100
    若无 Control 孔，则自动降级为绝对净值模式 (Sample - Blank_avg) 并提出警告
    任何计算均基于 Well.corrected_value 实施
    """
    @property
    def name(self) -> str:
        return "细胞活力计算 (CCK-8 / MTT)"

    @property
    def description(self) -> str:
        return ("计算给药组样品的相对细胞存活率(%)。\n"
                "若无对照孔(Control)，系统自动启动降级机制计算背景校正绝对净OD值，并向用户警告提示。")

    def calculate(self, plate: Plate, params: dict = None) -> Plate:
        logger.info("启动 CCK-8 细胞活力计算...")

        plate.statistics.clear()

        # 1. 获取空白孔及对照孔
        blank_wells = plate.get_wells_by_type(WellType.BLANK)
        control_wells = plate.get_wells_by_type(WellType.CONTROL)

        blank_vals = [w.corrected_value for w in blank_wells if w.raw_value is not None]
        control_vals = [w.corrected_value for w in control_wells if w.raw_value is not None]

        blank_mean = np.mean(blank_vals) if blank_vals else 0.0
        plate.statistics["blank_mean"] = blank_mean
        logger.info(f"Blank 平均 OD 值: {blank_mean:.4f}")

        # 2. 对照孔降级判断
        if not control_vals:
            # 💡 降级处理：无 Control 时转为绝对净值模式，写回警告
            plate.statistics["warnings"] = ["未检测到任何对照孔(Control)，细胞活力已自动降级为绝对净值模式计算。"]
            logger.warning("未设定 Control 对照孔，进入背景校正绝对净值模式。")

            for well in plate.all_wells():
                if well.well_type == WellType.UNUSED:
                    well.calc_result = None
                    continue
                if well.raw_value is not None:
                    # 净值 = corrected_value - blank_mean
                    well.calc_result = well.corrected_value - blank_mean
                else:
                    well.calc_result = None
        else:
            control_mean = np.mean(control_vals)
            plate.statistics["control_mean"] = control_mean
            denominator = control_mean - blank_mean
            logger.info(f"Control 平均 OD 值: {control_mean:.4f}, 校正分母值: {denominator:.4f}")

            # 防分母为零崩溃
            if abs(denominator) < 1e-9:
                denominator = 1e-9

            for well in plate.all_wells():
                if well.well_type == WellType.UNUSED:
                    well.calc_result = None
                    continue

                # 只有 Sample 和 Control 以及 Blank 参与相对计算渲染
                if well.raw_value is not None:
                    numerator = well.corrected_value - blank_mean
                    viability = (numerator / denominator) * 100.0
                    well.calc_result = float(viability)
                else:
                    well.calc_result = None

        logger.info("CCK-8 计算执行完毕！")
        return self.post_process_samples(plate)
