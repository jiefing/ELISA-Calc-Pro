# -*- coding: utf-8 -*-
"""
产量密度族与杂项族回归模型模块 (models_misc.py) - V3.0
忠实移植 CurveExpert 1.4 的 Yield-Density Family（4 个）与 Miscellaneous Family（5 个）。
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


# =====================================================================
# Yield-Density Family
# =====================================================================

class ReciprocalStrategy(BaseFitStrategy):
    """y = 1/(a + b·x)"""
    name = "倒数模型 y=1/(a+b·x)"
    description = "渐近型产量-密度模型，响应随 x 增大单调递减至 0。"
    family = "产量密度族"
    param_names = ["a", "b"]

    def predict(self, x, params):
        return 1.0 / (params["a"] + params["b"] * x)

    def guess_initial(self, x, y):
        # 1/y = a + b·x
        return _lin_guess(np.column_stack([np.ones_like(x), x]), 1.0 / np.maximum(y, 1e-12))

    def format_equation(self, params):
        return f"y = 1/({params['a']:.6g} + {params['b']:.6g}·x)"


class ReciprocalQuadraticStrategy(BaseFitStrategy):
    """y = 1/(a + b·x + c·x²)"""
    name = "倒数二次模型 y=1/(a+b·x+c·x²)"
    description = "抛物型产量-密度模型，可呈现单峰（最优密度）响应。"
    family = "产量密度族"
    param_names = ["a", "b", "c"]

    def predict(self, x, params):
        return 1.0 / (params["a"] + params["b"] * x + params["c"] * x ** 2)

    def guess_initial(self, x, y):
        inv_y = 1.0 / np.maximum(y, 1e-12)
        coef = np.polyfit(x, inv_y, 2)
        return [float(v) for v in coef[::-1]]

    def format_equation(self, params):
        return f"y = 1/({params['a']:.6g} + {params['b']:.6g}·x + {params['c']:.6g}·x²)"


class BleasdaleStrategy(BaseFitStrategy):
    """y = (a + b·x)^(-1/c)"""
    name = "Bleasdale 模型 y=(a+b·x)^(-1/c)"
    description = "农业产量-密度经典模型，c 控制曲线形状。"
    family = "产量密度族"
    param_names = ["a", "b", "c"]

    def predict(self, x, params):
        return np.power(params["a"] + params["b"] * x, -1.0 / params["c"])

    def guess_initial(self, x, y):
        # c=1 时退化为倒数模型，先线性化求 a、b
        c0 = 1.0
        ab = _lin_guess(np.column_stack([np.ones_like(x), x]), 1.0 / np.maximum(y, 1e-12))
        return [ab[0], ab[1], c0]

    def format_equation(self, params):
        return f"y = ({params['a']:.6g} + {params['b']:.6g}·x)^(-1/{params['c']:.6g})"


class HarrisStrategy(BaseFitStrategy):
    """y = 1/(a + b·x^c)"""
    name = "Harris 模型 y=1/(a+b·x^c)"
    description = "倒数-幂混合模型，c 控制衰减曲率。"
    family = "产量密度族"
    param_names = ["a", "b", "c"]

    def predict(self, x, params):
        return 1.0 / (params["a"] + params["b"] * np.power(x, params["c"]))

    def guess_initial(self, x, y):
        # c=1 时退化为倒数模型
        c0 = 1.0
        ab = _lin_guess(np.column_stack([np.ones_like(x), x]), 1.0 / np.maximum(y, 1e-12))
        return [ab[0], ab[1], c0]

    def format_equation(self, params):
        return f"y = 1/({params['a']:.6g} + {params['b']:.6g}·x^{params['c']:.6g})"


# =====================================================================
# Miscellaneous Family
# =====================================================================

class SinusoidalStrategy(BaseFitStrategy):
    """y = a + b·cos(c·x + d)"""
    name = "正弦拟合 y=a+b·cos(c·x+d)"
    description = "周期性响应模型，a 为基线，b 为振幅，c 为角频率，d 为相位。"
    family = "杂项模型"
    param_names = ["a", "b", "c", "d"]

    def predict(self, x, params):
        return params["a"] + params["b"] * np.cos(params["c"] * x + params["d"])

    def guess_initial(self, x, y):
        a0 = float(np.mean(y))
        b0 = (float(np.max(y)) - float(np.min(y))) / 2.0
        span = float(np.max(x) - np.min(x))
        # 过零间隔估计主频率：信号每周期约穿越均值两次
        y_d = y - a0
        signs = np.sign(y_d)
        crossings = np.where(np.diff(signs) != 0)[0]
        if len(crossings) >= 2:
            spacing = np.diff(x[crossings])
            period = 2.0 * float(np.median(spacing))
            c0 = 2.0 * np.pi / period if period > 1e-9 else 1.0
        else:
            c0 = 2.0 * np.pi / span if span > 1e-12 else 1.0
        return [a0, b0 if b0 > 1e-12 else 1.0, c0, 0.0]

    def format_equation(self, params):
        return f"y = {params['a']:.6g} + {params['b']:.6g}·cos({params['c']:.6g}·x + {params['d']:.6g})"


class GaussianStrategy(BaseFitStrategy):
    """y = a·exp(-(x-b)²/(2c²))"""
    name = "高斯模型 y=a·e^(-(x-b)²/(2c²))"
    description = "钟形峰模型，a 为峰高，b 为峰位，c 为标准差。"
    family = "杂项模型"
    param_names = ["a", "b", "c"]

    def predict(self, x, params):
        return params["a"] * np.exp(-(x - params["b"]) ** 2 / (2.0 * params["c"] ** 2))

    def guess_initial(self, x, y):
        idx = int(np.argmax(y))
        a0 = float(np.max(y))
        b0 = float(x[idx])
        span = float(np.max(x) - np.min(x))
        c0 = span / 4.0 if span > 1e-12 else 1.0
        return [a0, b0, c0 if c0 > 1e-12 else 1.0]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}·e^(-(x-{params['b']:.6g})²/(2·{params['c']:.6g}²))"


class HyperbolicStrategy(BaseFitStrategy):
    """y = a + b/x"""
    name = "双曲拟合 y=a+b/x"
    description = "倒数衰减模型，适合底物消耗等双曲线关系。"
    family = "杂项模型"
    param_names = ["a", "b"]

    def predict(self, x, params):
        return params["a"] + params["b"] / np.maximum(x, 1e-12)

    def guess_initial(self, x, y):
        return _lin_guess(np.column_stack([np.ones_like(x), 1.0 / np.maximum(x, 1e-12)]), y)

    def format_equation(self, params):
        return f"y = {params['a']:.6g} + {params['b']:.6g}/x"


class HeatCapacityStrategy(BaseFitStrategy):
    """y = a + b·x + c/x²"""
    name = "热容模型 y=a+b·x+c/x²"
    description = "经典低温热容拟合（Debye 修正），a+bx 线性项叠加 1/x² 修正。"
    family = "杂项模型"
    param_names = ["a", "b", "c"]

    def predict(self, x, params):
        return params["a"] + params["b"] * x + params["c"] / (x ** 2 + 1e-12)

    def guess_initial(self, x, y):
        cols = np.column_stack([np.ones_like(x), x, 1.0 / (x ** 2 + 1e-12)])
        return _lin_guess(cols, y)

    def format_equation(self, params):
        return f"y = {params['a']:.6g} + {params['b']:.6g}·x + {params['c']:.6g}/x²"


class RationalFunctionStrategy(BaseFitStrategy):
    """y = (a + b·x)/(1 + c·x + d·x²)"""
    name = "有理函数 y=(a+b·x)/(1+c·x+d·x²)"
    description = "分子一次/分母二次的有理函数，可呈现多种峰谷形态。"
    family = "杂项模型"
    param_names = ["a", "b", "c", "d"]

    def predict(self, x, params):
        return (params["a"] + params["b"] * x) / (1.0 + params["c"] * x + params["d"] * x ** 2)

    def guess_initial(self, x, y):
        # 乘开线性化：y = a + b·x - c·x·y - d·x²·y
        cols = np.column_stack([np.ones_like(x), x, -x * y, -x * x * y])
        return _lin_guess(cols, y)

    def format_equation(self, params):
        return f"y = ({params['a']:.6g} + {params['b']:.6g}·x)/(1 + {params['c']:.6g}·x + {params['d']:.6g}·x²)"


# 注册清单
MISC_MODELS = [
    ReciprocalStrategy(),
    ReciprocalQuadraticStrategy(),
    BleasdaleStrategy(),
    HarrisStrategy(),
    SinusoidalStrategy(),
    GaussianStrategy(),
    HyperbolicStrategy(),
    HeatCapacityStrategy(),
    RationalFunctionStrategy(),
]
