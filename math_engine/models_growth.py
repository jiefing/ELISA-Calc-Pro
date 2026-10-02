# -*- coding: utf-8 -*-
"""
生长曲线族回归模型模块 (models_growth.py) - V3.0
忠实移植 CurveExpert 1.4 的 Growth Family（3 个）与 Sigmoidal Family（5 个）模型：
指数关联、饱和生长、Gompertz、Logistic、Richards、MMF、Weibull。
"""

import numpy as np
from typing import List, Dict
from .strategy_base import BaseFitStrategy


def _lin_guess(cols: np.ndarray, target: np.ndarray) -> List[float]:
    try:
        coef, *_ = np.linalg.lstsq(cols, target, rcond=None)
        if np.all(np.isfinite(coef)):
            return [float(v) for v in coef]
    except Exception:
        pass
    return [float(np.mean(target))] + [0.0] * (cols.shape[1] - 1)


class ExponentialAssociation2Strategy(BaseFitStrategy):
    """y = a·(1 - exp(-b·x))"""
    name = "指数关联 (2) y=a·(1-e^(-b·x))"
    description = "从 0 单调增长到渐近线 a 的单分子关联模型，a 为饱和值。"
    family = "生长曲线族"
    param_names = ["a", "b"]

    def predict(self, x, params):
        return params["a"] * (1.0 - np.exp(-params["b"] * x))

    def guess_initial(self, x, y):
        a0 = float(np.max(y)) * 1.05 if np.max(y) > 0 else 1.0
        # y/a = 1 - exp(-bx) → -ln(1 - y/a) = b·x
        t = -np.log(np.clip(1.0 - y / a0, 1e-9, 1.0))
        b0 = _lin_guess(np.column_stack([x]), t)
        return [a0, b0[0] if b0[0] > 1e-9 else 1.0 / max(float(np.max(x)), 1e-9)]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}·(1 - e^(-{params['b']:.6g}·x))"


class ExponentialAssociation3Strategy(BaseFitStrategy):
    """y = a·(b - exp(-c·x))"""
    name = "指数关联 (3) y=a·(b-e^(-c·x))"
    description = "带初始偏移的关联模型，y(0)=a·(b-1)，渐近线 y(∞)=a·b。"
    family = "生长曲线族"
    param_names = ["a", "b", "c"]

    def predict(self, x, params):
        return params["a"] * (params["b"] - np.exp(-params["c"] * x))

    def guess_initial(self, x, y):
        y_lo = float(np.min(y))
        y_hi = float(np.max(y))
        a0 = max(y_hi - y_lo, 1e-9)
        b0 = 1.0 + max(y_lo / a0, 0.0)
        t = -np.log(np.clip(b0 - y / a0, 1e-9, 1.0))
        c0 = _lin_guess(np.column_stack([x]), t)
        return [a0, b0, c0[0] if c0[0] > 1e-9 else 1.0 / max(float(np.max(x)), 1e-9)]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}·({params['b']:.6g} - e^(-{params['c']:.6g}·x))"


class SaturationGrowthStrategy(BaseFitStrategy):
    """y = a·x/(b + x)（Michaelis-Menten）"""
    name = "饱和生长模型 y=a·x/(b+x)"
    description = "Michaelis-Menten 型饱和曲线，a 为最大速率，b 为半饱和常数。"
    family = "生长曲线族"
    param_names = ["a", "b"]

    def predict(self, x, params):
        return params["a"] * x / (params["b"] + x)

    def guess_initial(self, x, y):
        # 双倒数线性化：1/y = (b/a)·(1/x) + 1/a
        inv_y = 1.0 / np.maximum(y, 1e-12)
        inv_x = 1.0 / np.maximum(x, 1e-12)
        c = _lin_guess(np.column_stack([inv_x, np.ones_like(inv_x)]), inv_y)
        slope, inter = c[0], c[1]
        if abs(inter) < 1e-12:
            a0, b0 = float(np.max(y)) * 1.05, float(np.median(x))
        else:
            a0, b0 = 1.0 / inter, slope / inter
        return [a0 if a0 > 1e-9 else 1.0, b0 if b0 > 0 else float(np.median(x))]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}·x/({params['b']:.6g} + x)"


class GompertzStrategy(BaseFitStrategy):
    """y = a·exp(-exp(b - c·x))"""
    name = "Gompertz 模型 y=a·e^(-e^(b-c·x))"
    description = "经典 S 型生长模型，拐点位于 y = a/e 处，适合细胞与群体生长。"
    family = "S 形曲线族"
    param_names = ["a", "b", "c"]

    def predict(self, x, params):
        return params["a"] * np.exp(-np.exp(params["b"] - params["c"] * x))

    def guess_initial(self, x, y):
        a0 = float(np.max(y)) * 1.05 if np.max(y) > 0 else 1.0
        # ln(-ln(y/a)) = b - c·x
        t = np.log(-np.log(np.clip(y / a0, 1e-9, 1.0 - 1e-9)))
        c = _lin_guess(np.column_stack([np.ones_like(x), x]), t)
        return [a0, c[0], -c[1] if c[1] != 0 else 1.0]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}·e^(-e^({params['b']:.6g}-{params['c']:.6g}·x))"


class LogisticStrategy(BaseFitStrategy):
    """y = a/(1 + exp(b - c·x))"""
    name = "Logistic 模型 y=a/(1+e^(b-c·x))"
    description = "四参数逻辑回归的 3 参数形式，拐点 y = a/2，对称 S 曲线。"
    family = "S 形曲线族"
    param_names = ["a", "b", "c"]

    def predict(self, x, params):
        return params["a"] / (1.0 + np.exp(params["b"] - params["c"] * x))

    def guess_initial(self, x, y):
        a0 = float(np.max(y)) * 1.05 if np.max(y) > 0 else 1.0
        # ln(a/y - 1) = b - c·x
        t = np.log(np.clip(a0 / y - 1.0, 1e-9, 1e9))
        c = _lin_guess(np.column_stack([np.ones_like(x), x]), t)
        return [a0, c[0], -c[1] if c[1] != 0 else 1.0]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}/(1 + e^({params['b']:.6g}-{params['c']:.6g}·x))"


class RichardsStrategy(BaseFitStrategy):
    """y = a/(1 + exp(b - c·x))^(1/d)"""
    name = "Richards 模型 y=a/(1+e^(b-c·x))^(1/d)"
    description = "非对称 S 曲线，d 控制拐点位置，比 Logistic 更灵活。"
    family = "S 形曲线族"
    param_names = ["a", "b", "c", "d"]

    def predict(self, x, params):
        return params["a"] / np.power(1.0 + np.exp(params["b"] - params["c"] * x), 1.0 / params["d"])

    def guess_initial(self, x, y):
        a0 = float(np.max(y)) * 1.05 if np.max(y) > 0 else 1.0
        d0 = 1.0
        # d=1 时退化为 Logistic，用其线性化估计 b、c
        t = np.log(np.clip(np.power(a0 / y, d0) - 1.0, 1e-9, 1e9))
        c = _lin_guess(np.column_stack([np.ones_like(x), x]), t)
        return [a0, c[0], -c[1] if c[1] != 0 else 1.0, d0]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}/(1 + e^({params['b']:.6g}-{params['c']:.6g}·x))^(1/{params['d']:.6g})"


class MMFStrategy(BaseFitStrategy):
    """y = (a·b + c·x^d)/(b + x^d)"""
    name = "MMF 模型 y=(a·b+c·x^d)/(b+x^d)"
    description = "Morgan-Mercer-Flodin 模型：y(0)=a 下渐近线，y(∞)=c 上渐近线，Hill 型斜率。"
    family = "S 形曲线族"
    param_names = ["a", "b", "c", "d"]

    def predict(self, x, params):
        xd = np.power(x, params["d"])
        return (params["a"] * params["b"] + params["c"] * xd) / (params["b"] + xd)

    def guess_initial(self, x, y):
        a0 = float(np.min(y))
        c0 = float(np.max(y)) * 1.02
        d0 = 1.0
        # 中值点处解 b：y_mid = (a·b + c·x_mid^d)/(b + x_mid^d) → b = x_mid^d·(c-y_mid)/(y_mid-a)
        x_mid = float(np.median(x))
        y_mid = float(np.median(y))
        b0 = (c0 - y_mid) / max(y_mid - a0, 1e-9) * (x_mid ** d0)
        return [a0, b0 if b0 > 1e-9 else 1.0, c0, d0]

    def format_equation(self, params):
        return f"y = ({params['a']:.6g}·{params['b']:.6g} + {params['c']:.6g}·x^{params['d']:.6g})/({params['b']:.6g} + x^{params['d']:.6g})"


class WeibullStrategy(BaseFitStrategy):
    """y = a - b·exp(-c·x^d)"""
    name = "Weibull 模型 y=a-b·e^(-c·x^d)"
    description = "从 a-b 增长到渐近线 a 的可靠性/生长模型，d 为形状参数。"
    family = "S 形曲线族"
    param_names = ["a", "b", "c", "d"]

    def predict(self, x, params):
        return params["a"] - params["b"] * np.exp(-params["c"] * np.power(x, params["d"]))

    def guess_initial(self, x, y):
        y_min, y_max = float(np.min(y)), float(np.max(y))
        a0 = y_max * 1.05 if y_max > 0 else 1.0
        b0 = max(a0 - y_min, 1e-9)
        d0 = 1.0
        # 中值点处解 c：exp(-c·x^d) = (a - y)/b
        x_mid = float(np.median(x))
        y_mid = float(np.median(y))
        ratio = np.clip((a0 - y_mid) / b0, 1e-9, 1.0)
        c0 = -np.log(ratio) / max(x_mid ** d0, 1e-12)
        return [a0, b0, c0 if c0 > 1e-9 else 1.0, d0]

    def format_equation(self, params):
        return f"y = {params['a']:.6g} - {params['b']:.6g}·e^(-{params['c']:.6g}·x^{params['d']:.6g})"


# 注册清单
GROWTH_MODELS = [
    ExponentialAssociation2Strategy(),
    ExponentialAssociation3Strategy(),
    SaturationGrowthStrategy(),
    GompertzStrategy(),
    LogisticStrategy(),
    RichardsStrategy(),
    MMFStrategy(),
    WeibullStrategy(),
]
