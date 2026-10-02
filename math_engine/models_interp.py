# -*- coding: utf-8 -*-
"""
插值模型模块 (models_interp.py) - V3.0
忠实移植 CurveExpert 1.4 的插值工具：Lagrangian 插值、线性/二次/三次样条、张力样条。
插值模型穿过全部数据点，误差为 0；不参与回归排名（或恒为 R²=1）。
"""

import numpy as np
from typing import List, Dict, Optional
from scipy.interpolate import BarycentricInterpolator, CubicSpline
from core.data_models import StandardPoint, SamplePoint, CurveFitResult
from .strategy_base import BaseFitStrategy, FitEngineError


class _TensionSpline:
    """
    Nielson (1974) 张力样条实现。
    张力参数 σ：σ→0 退化为三次样条，σ→∞ 逼近线性样条。
    """

    def __init__(self, x: np.ndarray, y: np.ndarray, tension: float = 5.0):
        self.x = np.asarray(x, dtype=float)
        self.y = np.asarray(y, dtype=float)
        self.tension = float(tension)
        n = len(self.x)
        self.h = np.diff(self.x)
        self.rho = self.tension * self.h
        # 求解二阶导数节点值 M（三对角系统，自然边界 M0 = M_{n-1} = 0）
        self.M = self._solve_m()

    # ---- 小 ρ 级数展开辅助（保证 σ→0 数值稳定） ----
    @staticmethod
    def _s1(rho):
        """1/sinh(ρ) - 1/ρ"""
        rho = np.asarray(rho, dtype=float)
        out = np.empty_like(rho)
        small = np.abs(rho) < 0.05
        if np.any(small):
            r = rho[small]
            out[small] = -r / 6.0 + 7.0 * r ** 3 / 360.0 - 31.0 * r ** 5 / 15120.0
        if np.any(~small):
            r = rho[~small]
            out[~small] = 1.0 / np.sinh(r) - 1.0 / r
        return out

    @staticmethod
    def _s2(rho):
        """ρ·coth(ρ) - 1"""
        rho = np.asarray(rho, dtype=float)
        out = np.empty_like(rho)
        small = np.abs(rho) < 0.05
        if np.any(small):
            r = rho[small]
            out[small] = r ** 2 / 3.0 - r ** 4 / 45.0 + 2.0 * r ** 6 / 945.0
        if np.any(~small):
            r = rho[~small]
            out[~small] = r / np.tanh(r) - 1.0
        return out

    def _solve_m(self) -> np.ndarray:
        n = len(self.x)
        if n < 3:
            return np.zeros(n)
        rho = self.rho
        h = self.h
        a = self._s1(rho[:-1]) / h[:-1]
        c = self._s1(rho[1:]) / h[1:]
        b = self._s2(rho[:-1]) / h[:-1] + self._s2(rho[1:]) / h[1:]
        rhs = (self.y[2:] - self.y[1:-1]) / h[1:] ** 2 - (self.y[1:-1] - self.y[:-2]) / h[:-1] ** 2
        # 三对角矩阵 A·M = rhs
        A = np.zeros((n - 2, n - 2))
        for i in range(n - 2):
            A[i, i] = b[i]
            if i > 0:
                A[i, i - 1] = a[i]
            if i < n - 3:
                A[i, i + 1] = c[i]
        try:
            m_inner = np.linalg.solve(A, rhs)
        except np.linalg.LinAlgError:
            m_inner = np.zeros(n - 2)
        return np.concatenate([[0.0], m_inner, [0.0]])

    def __call__(self, xs: np.ndarray) -> np.ndarray:
        xs = np.asarray(xs, dtype=float)
        out = np.full_like(xs, np.nan, dtype=float)
        x, y, h, rho, M = self.x, self.y, self.h, self.rho, self.M
        n = len(x)
        for i in range(n - 1):
            mask = (xs >= x[i]) & (xs <= x[i + 1])
            if not np.any(mask):
                continue
            t = (xs[mask] - x[i]) / h[i]
            r = rho[i]
            t1 = 1.0 - t
            if abs(r) < 0.05:
                # 级数展开基函数
                phi1 = t1 + r ** 2 / 6.0 * (t1 ** 3 - t1) + r ** 4 / 120.0 * (t1 ** 5 - t1)
                phi2 = t + r ** 2 / 6.0 * (t ** 3 - t) + r ** 4 / 120.0 * (t ** 5 - t)
                psi1 = h[i] ** 2 * ((t1 ** 3 - t1) / 6.0 + r ** 2 * (t1 ** 5 - t1) / 120.0)
                psi2 = h[i] ** 2 * ((t ** 3 - t) / 6.0 + r ** 2 * (t ** 5 - t) / 120.0)
            else:
                shr = np.sinh(r)
                phi1 = np.sinh(r * t1) / shr
                phi2 = np.sinh(r * t) / shr
                psi1 = h[i] ** 2 / r ** 2 * (phi1 - t1)
                psi2 = h[i] ** 2 / r ** 2 * (phi2 - t)
            out[mask] = phi1 * y[i] + phi2 * y[i + 1] + psi1 * M[i] + psi2 * M[i + 1]
        return out


class BaseInterpolationStrategy(BaseFitStrategy):
    """插值策略公共骨架"""
    family = "插值模型"

    @property
    def is_interpolation(self) -> bool:
        return True

    @property
    def extrapolate(self) -> bool:
        return False

    @property
    def supports_weight(self) -> bool:
        return False

    def _build(self, x: np.ndarray, y: np.ndarray):
        raise NotImplementedError

    def fit_and_predict(self, std_points, sample_points, weights=None, **kwargs):
        self.validate_std_points_length(std_points, min_len=2)
        x_arr, y_arr = self._extract_xy(std_points)
        # 插值要求 x 严格递增，自动排序去重
        order = np.argsort(x_arr)
        x_sorted = x_arr[order]
        y_sorted = y_arr[order]
        # 合并重复 x（取均值）
        uniq_x, idx = np.unique(x_sorted, return_index=True)
        if len(uniq_x) < len(x_sorted):
            y_mean = []
            for ux in uniq_x:
                y_mean.append(float(np.mean(y_sorted[x_sorted == ux])))
            x_sorted, y_sorted = uniq_x, np.array(y_mean)
        if len(x_sorted) < 2:
            raise FitEngineError("插值模型要求至少 2 个不同的有效浓度点。")

        interp = self._build(x_sorted, y_sorted)
        params = {"_interp": interp, "x_data": x_sorted, "y_data": y_sorted}

        curve_x = np.linspace(float(x_sorted[0]), float(x_sorted[-1]), 300)
        curve_y = np.asarray(interp(curve_x), dtype=float)

        res_samples = self._solve_samples(sample_points, params, x_sorted, y_sorted)

        return CurveFitResult(
            model_name=self.name,
            success=True,
            equation_str=self.format_equation(params),
            parameters={},
            r_squared=1.0,
            standard_error=0.0,
            aic=float("-inf"),
            family=self.family,
            param_names=[],
            is_log_x=False,
            std_points=std_points,
            sample_points=res_samples,
            curve_x=curve_x,
            curve_y=curve_y,
            predict_fn=lambda xs, prm=params: np.asarray(prm["_interp"](np.asarray(xs, dtype=float)), dtype=float),
            x_range=(float(x_sorted[0]), float(x_sorted[-1])),
        )

    def format_equation(self, params) -> str:
        return f"{self.name}：穿过全部 {len(params.get('x_data', []))} 个数据点，区间内误差为 0"

    # 插值模型不参与通用 LM 拟合
    def guess_initial(self, x, y):
        return []

    def predict(self, x, params):
        return np.asarray(params["_interp"](np.asarray(x, dtype=float)), dtype=float)


class LagrangianStrategy(BaseInterpolationStrategy):
    """Lagrangian 多项式插值（穿过全部点的高次多项式）"""
    name = "Lagrangian 插值"
    description = "构造穿过全部数据点的 n-1 次多项式，点数多时可能出现龙格振荡。"

    def _build(self, x, y):
        return BarycentricInterpolator(x, y)


class LinearSplineStrategy(BaseInterpolationStrategy):
    """线性样条（折线连接）"""
    name = "线性样条插值"
    description = "相邻点直线连接，最简单稳定的插值方式。"

    def _build(self, x, y):
        return lambda xs: np.interp(xs, x, y)


class QuadraticSplineStrategy(BaseInterpolationStrategy):
    """二次样条（首段直线 + 一阶导数连续）"""
    name = "二次样条插值"
    description = "每段二次多项式，一阶导数在节点连续；首段为直线（二阶导为零边界）。"

    def _build(self, x, y):
        return _QuadraticSpline(x, y)


class _QuadraticSpline:
    """首段直线边界条件的二次样条"""

    def __init__(self, x, y):
        self.x = np.asarray(x, dtype=float)
        self.y = np.asarray(y, dtype=float)
        n = len(self.x)
        h = np.diff(self.x)
        delta = np.diff(self.y) / h
        # m0 = delta0（二阶导为零 → 首段线性），递推 m_{i+1} = 2·delta_i - m_i
        m = np.empty(n)
        m[0] = delta[0]
        for i in range(n - 1):
            m[i + 1] = 2.0 * delta[i] - m[i]
        self.m = m
        self.h = h

    def __call__(self, xs):
        xs = np.asarray(xs, dtype=float)
        out = np.full_like(xs, np.nan, dtype=float)
        x, y, h, m = self.x, self.y, self.h, self.m
        for i in range(len(x) - 1):
            mask = (xs >= x[i]) & (xs <= x[i + 1])
            if not np.any(mask):
                continue
            dx = xs[mask] - x[i]
            out[mask] = y[i] + m[i] * dx + (m[i + 1] - m[i]) / (2.0 * h[i]) * dx ** 2
        return out


class CubicSplineStrategy(BaseInterpolationStrategy):
    """三次样条（自然边界）"""
    name = "三次样条插值"
    description = "每段三次多项式，一阶/二阶导数在节点连续，自然边界（端部二阶导为零）。"

    def _build(self, x, y):
        return CubicSpline(x, y, bc_type="natural")


class TensionSplineStrategy(BaseInterpolationStrategy):
    """张力样条（Nielson 算法）"""
    name = "张力样条插值"
    description = "三次样条与线性样条之间的柔性插值，张力参数越大越贴近折线。"

    def __init__(self, tension: float = 5.0):
        self.tension = float(tension)

    def _build(self, x, y):
        return _TensionSpline(x, y, tension=self.tension)

    def format_equation(self, params) -> str:
        return f"张力样条（张力 σ = {self.tension:g}）：穿过全部 {len(params.get('x_data', []))} 个数据点"


INTERP_MODELS = [
    LagrangianStrategy(),
    LinearSplineStrategy(),
    QuadraticSplineStrategy(),
    CubicSplineStrategy(),
    TensionSplineStrategy(),
]
