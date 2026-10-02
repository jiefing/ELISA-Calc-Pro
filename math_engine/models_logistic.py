# -*- coding: utf-8 -*-
"""
逻辑曲线多参数回归模块 (models_logistic.py)
提供标准的 4PL 四参数自回归非线性极值逼近和 Logit-Log 特种对数转化竞争去干扰计算引擎
"""

import numpy as np
from scipy.optimize import curve_fit
from typing import List
from core.data_models import StandardPoint, SamplePoint, CurveFitResult
from .strategy_base import BaseFitStrategy, FitEngineError


def _four_pl_equation(x, a, b, c, d):
    """
    四参数逻辑多重曲线映射函数 (4PL)
    y = d + (a - d) / (1.0 + (x / c)^b)
    """
    # np.power 在应对负半边的底遇有非整浮点将触发实数域无法开根的 RuntimeError 抛异常
    return d + (a - d) / (1.0 + np.power(np.abs(x) / np.abs(c), b))


class FourPLStrategy(BaseFitStrategy):
    """
    经典四参数逻辑回归模型 (4-Parameter Logistic)
    针对非线态 S 曲线或者生物抗体生殖激素检测最富权威解释度的专业范式。
    """
    @property
    def name(self) -> str:
        return "四参数逻辑回归 (4PL)"

    @property
    def description(self) -> str:
        return "S 型标准全效拟合。参数解释: a (最小值近极点), d (最大值终局端), c (半数效应 EC50), b (斜率拐率势)。要求浓度绝对需 > 0。"

    def fit_and_predict(self, std_points: List[StandardPoint], sample_points: List[SamplePoint],
                        weights=None, **kwargs) -> CurveFitResult:
        self.validate_std_points_length(std_points, min_len=4)

        # 【重点安全风控】：零值/负值强效重锁拦截机制！
        for sp in std_points:
            if sp.x <= 0:
                raise FitEngineError("对数/4PL模型要求浓度必须大于0")

        x_arr = np.array([p.x for p in std_points], dtype=float)
        y_arr = np.array([p.y for p in std_points], dtype=float)

        # 构建优等智能化回归启点 (Initial guess estimation for Levenberg-Marquardt optimizer)
        min_y, max_y = np.min(y_arr), np.max(y_arr)
        mid_x = np.median(x_arr)
        # 根据实验数据的趋向初勘趋势势态（如果末底 OD 低则是正比例竞争或吸附正比）
        slope_guess = 1.0 if y_arr[-1] < y_arr[0] else -1.0
        p0 = [min_y, slope_guess, mid_x, max_y]

        try:
            popt, _ = curve_fit(
                _four_pl_equation, x_arr, y_arr,
                p0=p0,
                method='lm',
                maxfev=15000
            )
            a, b, c, d = popt
        except RuntimeError:
            raise FitEngineError("无法收敛，请检查数据趋势。这有可能来自于实验散点发散失衡或者严重欠离轴无生理学单调对应规律！")
        except Exception as e:
            raise FitEngineError(f"4PL Levenberg-Marquardt 拟合异常终了：\n{e}")

        # 计算优度 R²
        y_pred = _four_pl_equation(x_arr, a, b, c, d)
        ss_res = np.sum((y_arr - y_pred) ** 2)
        ss_tot = np.sum((y_arr - np.mean(y_arr)) ** 2)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0

        # 构建高极性 Log10 分步的平滑视界专属采样轴
        min_log = np.log10(np.min(x_arr)) - 0.2
        max_log = np.log10(np.max(x_arr)) + 0.2
        curve_x = np.logspace(min_log, max_log, 200)
        curve_y = _four_pl_equation(curve_x, a, b, c, d)

        # 反向破算待推未知物的精准实重与越线报警判定
        min_asym = min(a, d)
        max_asym = max(a, d)
        # 通过评估标曲在最小端与最大端的计算 OD 大小精准决定单调增或是单调减
        y_at_min_x = _four_pl_equation(np.min(x_arr), a, b, c, d)
        y_at_max_x = _four_pl_equation(np.max(x_arr), a, b, c, d)
        is_increasing = y_at_max_x > y_at_min_x

        res_sample_points = []
        for sp in sample_points:
            # 依准说明书规约：“当样本 OD 值落在 [a, d] 之外时，严禁数学外推，直接返回 >上限 或 <下限。”
            if sp.y > max_asym:
                calc_x = ">上限" if is_increasing else "<下限"
            elif sp.y < min_asym:
                calc_x = "<下限" if is_increasing else ">上限"
            else:
                try:
                    # 代数翻转分解：1 + (x/c)^b = (a - d) / (y - d)  =>  (x/c)^b = (a - d) / (y - d) - 1.0
                    numerator_val = (a - d) / (sp.y - d) - 1.0
                    if numerator_val < 0:
                        calc_x = "Err (幂定义空间无真零解)"
                    else:
                        ans = c * np.power(numerator_val, 1.0 / b)
                        calc_x = float(ans)
                except Exception:
                    calc_x = "Err"
            res_sample_points.append(SamplePoint(sample_id=sp.sample_id, y=sp.y, calc_x=calc_x, row_idx=sp.row_idx))

        eq_str = f"y = {d:.4f} + ({a:.4f} - {d:.4f}) / [1 + (x / {c:.4f}) ^ {b:.4f}]"

        return CurveFitResult(
            model_name=self.name,
            success=True,
            equation_str=eq_str,
            parameters={"a (极小值界)": float(a), "b (转换斜率)": float(b), "c (半效应值 EC50)": float(c), "d (极大值界)": float(d)},
            r_squared=float(r_squared),
            is_log_x=True,
            std_points=std_points,
            sample_points=res_sample_points,
            curve_x=curve_x,
            curve_y=curve_y
        )


class LogitLogStrategy(BaseFitStrategy):
    """
    Logit-Log 竞争比对免疫转化回归策略
    把 B/B0 用自然对数展开为极强关联线性结构配合 Log(X) 展开分析
    """
    @property
    def name(self) -> str:
        return "Logit-Log 回归 (竞争法)"

    @property
    def description(self) -> str:
        return "预选出至上吸光度充当零效最大结合位点 (B0)，按公式 logit(y) = a·log10(x) + b 将非线态解为对数空间完美一次线段。"

    def fit_and_predict(self, std_points: List[StandardPoint], sample_points: List[SamplePoint],
                        weights=None, **kwargs) -> CurveFitResult:
        self.validate_std_points_length(std_points, min_len=3)

        # 零值负根强固隔离
        for sp in std_points:
            if sp.x <= 0:
                raise FitEngineError("对数/4PL模型要求浓度必须大于0")

        x_arr = np.array([p.x for p in std_points], dtype=float)
        y_arr = np.array([p.y for p in std_points], dtype=float)

        # 计算并寻取竞争平衡至高抗位界限 B0（取现存标准或探本吸光实值顶峰的 1.05 倍安全容余免防分母为空陷阱）
        max_y_obs = max([p.y for p in std_points] + [p.y for p in sample_points if p.y is not None], default=max(y_arr))
        b0 = max_y_obs * 1.05 if max_y_obs > 0 else 1.0

        # 对数化转译处理 log(x) 及 logit(B/B0) = ln((Y/B0) / (1 - Y/B0))
        log_x_arr = np.log10(x_arr)

        y_ratio = np.clip(y_arr / b0, 0.001, 0.999)
        logit_y_arr = np.log(y_ratio / (1.0 - y_ratio))

        try:
            coeffs = np.polyfit(log_x_arr, logit_y_arr, deg=1)
            a, b = coeffs[0], coeffs[1]
        except Exception as e:
            raise FitEngineError(f"Logit-Log 代数空间映射崩溃：\n{e}")

        if abs(a) < 1e-12:
            raise FitEngineError("Logit 对数轴衰损近为不变一条水平平线，回归瘫痪无解析根！")

        # R² 检验于真实 OD 回原测参
        y_pred_logit = a * log_x_arr + b
        # 逆还原 y_pred_ratio = exp(logit) / (1 + exp(logit))
        y_pred_ratio = np.exp(y_pred_logit) / (1.0 + np.exp(y_pred_logit))
        y_pred = y_pred_ratio * b0

        ss_res = np.sum((y_arr - y_pred) ** 2)
        ss_tot = np.sum((y_arr - np.mean(y_arr)) ** 2)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0

        # 对数化视距渲染画幅点集
        min_log, max_log = min(log_x_arr) - 0.2, max(log_x_arr) + 0.2
        curve_x = np.logspace(min_log, max_log, 150)
        c_log_x = np.log10(curve_x)
        c_logit = a * c_log_x + b
        c_ratio = np.exp(c_logit) / (1.0 + np.exp(c_logit))
        curve_y = c_ratio * b0

        # 针对全样池代入推演逆解：x = 10 ^ [ (logit(y/B0) - b) / a ]
        is_increasing = a > 0  # 随浓度攀升 OD 同升或降
        res_sample_points = []
        for sp in sample_points:
            ratio = sp.y / b0
            if ratio >= 0.999:
                calc_x = ">上限" if is_increasing else "<下限"
            elif ratio <= 0.001:
                calc_x = "<下限" if is_increasing else ">上限"
            else:
                try:
                    val_logit = np.log(ratio / (1.0 - ratio))
                    log10_ans = (val_logit - b) / a
                    calc_x = float(np.power(10.0, log10_ans))
                except Exception:
                    calc_x = "Err"
            res_sample_points.append(SamplePoint(sample_id=sp.sample_id, y=sp.y, calc_x=calc_x, row_idx=sp.row_idx))

        eq_str = f"logit(Y / {b0:.4f}) = {a:.5f}·log10(X) " + (f"+ {b:.5f}" if b >= 0 else f"- {abs(b):.5f}")

        return CurveFitResult(
            model_name=self.name,
            success=True,
            equation_str=eq_str,
            parameters={"a (对数斜率)": float(a), "b (常数顶偏)": float(b), "B0 (最大饱和结合)": float(b0)},
            r_squared=float(r_squared),
            is_log_x=True,
            std_points=std_points,
            sample_points=res_sample_points,
            curve_x=curve_x,
            curve_y=curve_y
        )
