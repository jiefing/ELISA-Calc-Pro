# -*- coding: utf-8 -*-
"""
多项式直线回归模型模块 (models_linear.py)
含经典一阶直线回归与二次多项式回归算法的完全实现
"""

import numpy as np
from typing import List
from core.data_models import StandardPoint, SamplePoint, CurveFitResult
from .strategy_base import BaseFitStrategy, FitEngineError


class LinearRegressionStrategy(BaseFitStrategy):
    """
    直线回归模型算法: y = k * x + b
    适用广泛的高浓度或者比色法测定（例如BCA蛋白质浓度量化等）
    """
    @property
    def name(self) -> str:
        return "直线回归 (Linear Regression)"

    @property
    def description(self) -> str:
        return "经典一阶直线多项式公式 y = k·x + b，直接计算吸光度与浓度的正比线性关系。"

    def fit_and_predict(self, std_points: List[StandardPoint], sample_points: List[SamplePoint],
                        weights=None, **kwargs) -> CurveFitResult:
        self.validate_std_points_length(std_points, min_len=2)

        x_arr = np.array([p.x for p in std_points], dtype=float)
        y_arr = np.array([p.y for p in std_points], dtype=float)

        try:
            # 执行多项式直线回想
            coeffs = np.polyfit(x_arr, y_arr, deg=1)
            k, b = coeffs[0], coeffs[1]
        except Exception as e:
            raise FitEngineError(f"直线回归计算遭遇算数迭代失效：\n{e}")

        if abs(k) < 1e-12:
            raise FitEngineError("直线拟合斜率近乎为 0，标准品响应可能处于无梯度瘫痪区域，无法完成精确浓度回推！")

        # 估测决定系数 R²
        y_pred = k * x_arr + b
        ss_res = np.sum((y_arr - y_pred) ** 2)
        ss_tot = np.sum((y_arr - np.mean(y_arr)) ** 2)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0

        # 生成可视化连通曲线序列 (50 点平滑连线即可满足无畸形极速直缝)
        min_x, max_x = min(x_arr), max(x_arr)
        span = max_x - min_x if max_x > min_x else 1.0
        curve_x = np.linspace(min_x - span * 0.05, max_x + span * 0.05, 100)
        curve_y = k * curve_x + b

        # 回调解得全部目标未知品的计算值 (x = (y - b) / k)
        res_sample_points = []
        for sp in sample_points:
            calc_val = (sp.y - b) / k
            # 不进行硬编码上下限截短以方便蛋白质大区间伸长定量
            res_sample_points.append(SamplePoint(sample_id=sp.sample_id, y=sp.y, calc_x=float(calc_val), row_idx=sp.row_idx))

        equation_str = f"y = {k:.5f}·x " + (f"+ {b:.5f}" if b >= 0 else f"- {abs(b):.5f}")

        return CurveFitResult(
            model_name=self.name,
            success=True,
            equation_str=equation_str,
            parameters={"k (斜率)": float(k), "b (截距)": float(b)},
            r_squared=float(r_squared),
            is_log_x=False,
            std_points=std_points,
            sample_points=res_sample_points,
            curve_x=curve_x,
            curve_y=curve_y
        )


class QuadraticRegressionStrategy(BaseFitStrategy):
    """
    二次多项式拟合算法: y = a * x^2 + b * x + c
    应对试剂盒响应处于微弧段线性变化非完美情况时的优良补充计算手段。
    """
    @property
    def name(self) -> str:
        return "二次多项式拟合 (Quadratic)"

    @property
    def description(self) -> str:
        return "二阶抛物线模型 y = a·x² + b·x + c。利用一元二次求根原理且具备根据单调向性自适应剔除冗余反生理伪实根的能力。"

    def fit_and_predict(self, std_points: List[StandardPoint], sample_points: List[SamplePoint],
                        weights=None, **kwargs) -> CurveFitResult:
        self.validate_std_points_length(std_points, min_len=3)

        x_arr = np.array([p.x for p in std_points], dtype=float)
        y_arr = np.array([p.y for p in std_points], dtype=float)

        try:
            coeffs = np.polyfit(x_arr, y_arr, deg=2)
            a, b, c = coeffs[0], coeffs[1], coeffs[2]
        except Exception as e:
            raise FitEngineError(f"二次多项式运算回归异常：\n{e}")

        # 计算决定系数 R²
        y_pred = a * (x_arr ** 2) + b * x_arr + c
        ss_res = np.sum((y_arr - y_pred) ** 2)
        ss_tot = np.sum((y_arr - np.mean(y_arr)) ** 2)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0

        min_x, max_x = min(x_arr), max(x_arr)
        span = max_x - min_x if max_x > min_x else 1.0
        curve_x = np.linspace(min_x - span * 0.05, max_x + span * 0.05, 150)
        curve_y = a * (curve_x ** 2) + b * curve_x + c

        # 反推运算：求根公式解 0 = a*x^2 + b*x + (c-y)
        # 如果方程不具现实单调或者解值离出量限需要筛选处理
        # 计算整根标准品的宏观单调性方向 (增还是减)
        is_increasing = y_arr[-1] > y_arr[0] if len(y_arr) >= 2 else (b > 0)

        res_sample_points = []
        for sp in sample_points:
            delta = (b ** 2) - 4 * a * (c - sp.y)
            if delta < 0:
                # 根式内部为负数说明远破顶部或深陷地表顶弧
                # 依靠是向上凸还是向下凹确定属于上破仍或下探
                if is_increasing:
                    calc_x = ">上限" if sp.y > max(y_arr) else "<下限"
                else:
                    calc_x = "<下限" if sp.y > max(y_arr) else ">上限"
            elif abs(a) < 1e-12:
                # 若 a 近乎为 0 退化成一维一次单数公式
                calc_x = (sp.y - c) / b if abs(b) > 1e-12 else "Err"
                if isinstance(calc_x, float) and calc_x < 0:
                    calc_x = float(0.0)
            else:
                sqrt_delta = np.sqrt(delta)
                root1 = (-b + sqrt_delta) / (2 * a)
                root2 = (-b - sqrt_delta) / (2 * a)

                # 自动判识与生物学舍弃：弃绝任何长于远郊无意义的奇异数根或超大异常根
                valid_roots = []
                for r in (root1, root2):
                    # 如果轻微小于 0，可能只是本底误差微晃，宽容认定合规为近零底端
                    if -span * 0.2 <= r <= max_x + span * 0.5:
                        valid_roots.append(max(0.0, r)) # 如轻微小于零纠错直转为 0

                if len(valid_roots) == 1:
                    calc_x = float(valid_roots[0])
                elif len(valid_roots) > 1:
                    # 发现存在多偶实值落在范域外，则选用同段曲线里一阶导和原函数单调趋性最为协同并且靠近中位数中心点的实根
                    mid_val = np.median(x_arr)
                    calc_x = float(min(valid_roots, key=lambda val: abs(val - mid_val)))
                else:
                    # 如果任何一解连极宽的容错距离都不存留下
                    calc_x = ">上限" if sp.y > max(y_arr) else "<下限"

            res_sample_points.append(SamplePoint(sample_id=sp.sample_id, y=sp.y, calc_x=calc_x, row_idx=sp.row_idx))

        equation_str = f"y = {a:.5f}·x² " + (f"+ {b:.5f}·x " if b >= 0 else f"- {abs(b):.5f}·x ") + (f"+ {c:.5f}" if c >= 0 else f"- {abs(c):.5f}")

        return CurveFitResult(
            model_name=self.name,
            success=True,
            equation_str=equation_str,
            parameters={"a (二次项)": float(a), "b (一次项)": float(b), "c (常数项)": float(c)},
            r_squared=float(r_squared),
            is_log_x=False,
            std_points=std_points,
            sample_points=res_sample_points,
            curve_x=curve_x,
            curve_y=curve_y
        )


class PolynomialStrategy(BaseFitStrategy):
    """
    n 次多项式回归模型: y = c0 + c1·x + c2·x² + ... + cn·x^n
    直接最小二乘求解（线性问题无需迭代），阶数可在界面调整。
    """

    def __init__(self, order: int = 3):
        self.order = max(1, int(order))

    @property
    def name(self) -> str:
        return "多项式 (Polynomial)"

    @property
    def description(self) -> str:
        return f"n={self.order} 阶多项式回归 y = c0 + c1·x + ... + c{self.order}·x^{self.order}，直接最小二乘求解。"

    @property
    def param_names(self) -> List[str]:
        return [f"c{i}" for i in range(self.order + 1)]

    def fit_and_predict(self, std_points, sample_points, weights=None, **kwargs):
        order = int(kwargs.get("order", self.order))
        self.order = max(1, order)
        n_params = self.order + 1
        self.validate_std_points_length(std_points, min_len=n_params)

        x_arr, y_arr = self._extract_xy(std_points)
        sigma = self._weights_to_sigma(x_arr, y_arr, weights)
        try:
            if sigma is not None:
                # 加权最小二乘：构造权重矩阵后调用 lstsq
                w = 1.0 / sigma
                V = np.vander(x_arr, n_params, increasing=True)
                Vw = V * w[:, None]
                yw = y_arr * w
                coeffs, *_ = np.linalg.lstsq(Vw, yw, rcond=None)
            else:
                coeffs = np.polyfit(x_arr, y_arr, deg=self.order)[::-1]
        except Exception as e:
            raise FitEngineError(f"多项式回归计算异常：\n{e}")

        params = {f"c{i}": float(coeffs[i]) for i in range(n_params)}
        y_pred = self.predict(x_arr, params)
        r_squared = self._r_squared(y_arr, y_pred)
        se = self._standard_error(y_arr, y_pred, n_params)
        aic = self._aic(len(y_arr), n_params, float(np.sum((y_arr - y_pred) ** 2)))

        min_x, max_x = float(np.min(x_arr)), float(np.max(x_arr))
        span = max_x - min_x if max_x > min_x else 1.0
        curve_x = np.linspace(min_x - span * 0.05, max_x + span * 0.05, 250)
        curve_y = self.predict(curve_x, params)

        # 样本反推：多项式求根 + 单调区间筛选
        poly_coeffs = coeffs[::-1]  # 高次在前，np.roots 格式
        deriv = np.polyder(poly_coeffs)
        is_increasing = y_arr[-1] > y_arr[0] if len(y_arr) >= 2 else (poly_coeffs[-2] > 0)
        res_points = []
        for sp in sample_points:
            shifted = poly_coeffs.copy()
            shifted[-1] -= sp.y
            roots = np.roots(shifted)
            real_roots = [float(r.real) for r in roots if abs(r.imag) < 1e-7]
            valid = [r for r in real_roots if -span * 0.2 <= r <= max_x + span * 0.5]
            if not valid:
                calc_x = ">上限" if sp.y > np.max(y_arr) else "<下限"
            elif len(valid) == 1:
                calc_x = float(max(0.0, valid[0]))
            else:
                # 多实根：按一阶导符号与整体单调性一致的根优先，其次靠近中位数
                mid = float(np.median(x_arr))
                target_sign = 1.0 if is_increasing else -1.0
                scored = []
                for r in valid:
                    d = float(np.polyval(deriv, r))
                    score = 0 if d * target_sign > 0 else 1
                    scored.append((score, abs(r - mid), r))
                scored.sort()
                calc_x = float(max(0.0, scored[0][2]))
            res_points.append(SamplePoint(sample_id=sp.sample_id, y=sp.y, calc_x=calc_x, row_idx=sp.row_idx))

        terms = []
        for i, v in enumerate(coeffs):
            if i == 0:
                terms.append(f"{v:.6g}")
            elif i == 1:
                terms.append(f"{v:.6g}·x" if v >= 0 else f"- {abs(v):.6g}·x")
            else:
                terms.append(f"{v:.6g}·x^{i}" if v >= 0 else f"- {abs(v):.6g}·x^{i}")
        equation_str = "y = " + terms[0] + "".join(" + " + t if not t.startswith("-") else " " + t for t in terms[1:])

        return CurveFitResult(
            model_name=self.name,
            success=True,
            equation_str=equation_str,
            parameters=params,
            r_squared=r_squared,
            standard_error=se,
            aic=aic,
            family="多项式",
            param_names=list(self.param_names),
            is_log_x=False,
            std_points=std_points,
            sample_points=res_points,
            curve_x=curve_x,
            curve_y=curve_y,
            predict_fn=lambda xs, prm=params: self.predict(np.asarray(xs, dtype=float), prm),
            x_range=(min_x, max_x),
        )

    def predict(self, x, params):
        xa = np.asarray(x, dtype=float)
        out = np.zeros_like(xa, dtype=float)
        for i in range(self.order + 1):
            out += params[f"c{i}"] * np.power(xa, i)
        return out

    def format_equation(self, params) -> str:
        return self.name

    def guess_initial(self, x, y):
        return [1.0] * (self.order + 1)
