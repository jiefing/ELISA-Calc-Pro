# -*- coding: utf-8 -*-
"""
指数族与幂律族回归模型模块 (models_exponential.py) - V3.0
忠实移植 CurveExpert 1.4 的 Exponential Family（5 个）与 Power Family（8 个）模型。
全部采用线性化变换生成初始猜测，再经通用 Levenberg-Marquardt 精修。
"""

import numpy as np
from typing import List, Dict
from .strategy_base import BaseFitStrategy


def _safe_ln(vals: np.ndarray) -> np.ndarray:
    """安全对数：非正值置为极小正数，避免 nan"""
    return np.log(np.maximum(vals, 1e-12))


def _lin_guess(cols: np.ndarray, target: np.ndarray) -> List[float]:
    """
    最小二乘求解 target = cols @ coef（cols 第一列应为常数 1）。
    返回系数列表；失败时回退到平庸猜测。
    """
    try:
        coef, *_ = np.linalg.lstsq(cols, target, rcond=None)
        if np.all(np.isfinite(coef)):
            return [float(v) for v in coef]
    except Exception:
        pass
    return [float(np.mean(target))] + [0.0] * (cols.shape[1] - 1)


# =====================================================================
# Exponential Family
# =====================================================================

class ExponentialStrategy(BaseFitStrategy):
    """y = a·exp(b·x)"""
    name = "指数函数 y=a·e^(b·x)"
    description = "经典指数增长/衰减模型。ln(y) 对 x 呈直线，参数 a 为 x=0 截距值。"
    family = "指数族"
    param_names = ["a", "b"]

    def predict(self, x, params):
        return params["a"] * np.exp(params["b"] * x)

    def guess_initial(self, x, y):
        c = _lin_guess(np.column_stack([np.ones_like(x), x]), _safe_ln(y))
        return [np.exp(c[0]), c[1]]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}·e^({params['b']:.6g}·x)"


class ModifiedExponentialStrategy(BaseFitStrategy):
    """y = a·exp(b/x)"""
    name = "修正指数函数 y=a·e^(b/x)"
    description = "指数模型变体，自变量以倒数进入指数，适合快速饱和类响应。"
    family = "指数族"
    param_names = ["a", "b"]

    def predict(self, x, params):
        return params["a"] * np.exp(params["b"] / np.maximum(x, 1e-12))

    def guess_initial(self, x, y):
        c = _lin_guess(np.column_stack([np.ones_like(x), 1.0 / np.maximum(x, 1e-12)]), _safe_ln(y))
        return [np.exp(c[0]), c[1]]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}·e^({params['b']:.6g}/x)"


class LogarithmStrategy(BaseFitStrategy):
    """y = a + b·ln(x)"""
    name = "对数函数 y=a+b·ln(x)"
    description = "浓度对数与响应呈线性，常用于宽动态范围定量。要求 x > 0。"
    family = "指数族"
    param_names = ["a", "b"]
    needs_positive_x = True

    def predict(self, x, params):
        return params["a"] + params["b"] * _safe_ln(x)

    def guess_initial(self, x, y):
        return _lin_guess(np.column_stack([np.ones_like(x), _safe_ln(x)]), y)

    def format_equation(self, params):
        return f"y = {params['a']:.6g} + {params['b']:.6g}·ln(x)"


class ReciprocalLogarithmStrategy(BaseFitStrategy):
    """y = 1/(a + b·ln(x))"""
    name = "倒数对数函数 y=1/(a+b·ln(x))"
    description = "竞争法免疫分析常用倒数转换模型。要求 x > 0。"
    family = "指数族"
    param_names = ["a", "b"]
    needs_positive_x = True

    def predict(self, x, params):
        return 1.0 / (params["a"] + params["b"] * _safe_ln(x))

    def guess_initial(self, x, y):
        return _lin_guess(np.column_stack([np.ones_like(x), _safe_ln(x)]), 1.0 / np.maximum(y, 1e-12))

    def format_equation(self, params):
        return f"y = 1/({params['a']:.6g} + {params['b']:.6g}·ln(x))"


class VaporPressureStrategy(BaseFitStrategy):
    """y = exp(a + b/x + c·ln(x))"""
    name = "蒸汽压模型 y=e^(a+b/x+c·ln(x))"
    description = "克劳修斯-克拉佩龙类热力学模型，要求 x > 0。"
    family = "指数族"
    param_names = ["a", "b", "c"]
    needs_positive_x = True

    def predict(self, x, params):
        return np.exp(params["a"] + params["b"] / np.maximum(x, 1e-12) + params["c"] * _safe_ln(x))

    def guess_initial(self, x, y):
        cols = np.column_stack([np.ones_like(x), 1.0 / np.maximum(x, 1e-12), _safe_ln(x)])
        return _lin_guess(cols, _safe_ln(y))

    def format_equation(self, params):
        return f"y = e^({params['a']:.6g} + {params['b']:.6g}/x + {params['c']:.6g}·ln(x))"


# =====================================================================
# Power Family
# =====================================================================

class PowerStrategy(BaseFitStrategy):
    """y = a·x^b"""
    name = "幂函数 y=a·x^b"
    description = "双对数线性模型，广泛用于剂量-反应与标度律。要求 x > 0。"
    family = "幂律族"
    param_names = ["a", "b"]
    needs_positive_x = True

    def predict(self, x, params):
        return params["a"] * np.power(x, params["b"])

    def guess_initial(self, x, y):
        c = _lin_guess(np.column_stack([np.ones_like(x), _safe_ln(x)]), _safe_ln(y))
        return [np.exp(c[0]), c[1]]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}·x^{params['b']:.6g}"


class ModifiedPowerStrategy(BaseFitStrategy):
    """y = a·b^x"""
    name = "修正幂函数 y=a·b^x"
    description = "指数底参数模型，b>1 增长、0<b<1 衰减。"
    family = "幂律族"
    param_names = ["a", "b"]

    def predict(self, x, params):
        return params["a"] * np.power(params["b"], x)

    def guess_initial(self, x, y):
        c = _lin_guess(np.column_stack([np.ones_like(x), x]), _safe_ln(y))
        return [np.exp(c[0]), np.exp(c[1])]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}·{params['b']:.6g}^x"


class ShiftedPowerStrategy(BaseFitStrategy):
    """y = a·(x-b)^c"""
    name = "平移幂函数 y=a·(x-b)^c"
    description = "带 x 偏移的幂律模型，适合截距非零的标度关系。"
    family = "幂律族"
    param_names = ["a", "b", "c"]

    def predict(self, x, params):
        return params["a"] * np.power(np.maximum(x - params["b"], 1e-12), params["c"])

    def guess_initial(self, x, y):
        # 先估偏移 b 为最小 x 的 0.5 倍，再线性化求解 a、c
        b0 = float(np.min(x)) * 0.5
        xs = np.maximum(x - b0, 1e-12)
        c = _lin_guess(np.column_stack([np.ones_like(x), _safe_ln(xs)]), _safe_ln(y))
        return [np.exp(c[0]), b0, c[1]]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}·(x-{params['b']:.6g})^{params['c']:.6g}"


class GeometricStrategy(BaseFitStrategy):
    """y = a·x^(b·x)"""
    name = "几何函数 y=a·x^(b·x)"
    description = "指数随 x 线性变化的超指数模型。要求 x > 0。"
    family = "幂律族"
    param_names = ["a", "b"]
    needs_positive_x = True

    def predict(self, x, params):
        return params["a"] * np.power(x, params["b"] * x)

    def guess_initial(self, x, y):
        c = _lin_guess(np.column_stack([np.ones_like(x), x * _safe_ln(x)]), _safe_ln(y))
        return [np.exp(c[0]), c[1]]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}·x^({params['b']:.6g}·x)"


class ModifiedGeometricStrategy(BaseFitStrategy):
    """y = a·x^(b/x)"""
    name = "修正几何函数 y=a·x^(b/x)"
    description = "指数随 1/x 变化的模型，适合初始陡峭后趋缓的数据。要求 x > 0。"
    family = "幂律族"
    param_names = ["a", "b"]
    needs_positive_x = True

    def predict(self, x, params):
        return params["a"] * np.power(x, params["b"] / np.maximum(x, 1e-12))

    def guess_initial(self, x, y):
        c = _lin_guess(np.column_stack([np.ones_like(x), _safe_ln(x) / np.maximum(x, 1e-12)]), _safe_ln(y))
        return [np.exp(c[0]), c[1]]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}·x^({params['b']:.6g}/x)"


class RootStrategy(BaseFitStrategy):
    """y = a^(1/x)"""
    name = "根函数 y=a^(1/x)"
    description = "单参数模型，x 增大时趋近 1。用于衰减型快响应的粗拟合。"
    family = "幂律族"
    param_names = ["a"]

    def predict(self, x, params):
        return np.power(params["a"], 1.0 / np.maximum(x, 1e-12))

    def guess_initial(self, x, y):
        # ln(y) = ln(a)/x → ln(a) 为 1/x 对 ln(y) 回归的斜率
        c = _lin_guess(np.column_stack([1.0 / np.maximum(x, 1e-12)]), _safe_ln(y))
        return [np.exp(c[0])]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}^(1/x)"


class HoerlStrategy(BaseFitStrategy):
    """y = a·b^x·x^c"""
    name = "Hoerl 模型 y=a·b^x·x^c"
    description = "指数与幂的组合，可呈现单峰响应。要求 x > 0。"
    family = "幂律族"
    param_names = ["a", "b", "c"]
    needs_positive_x = True

    def predict(self, x, params):
        return params["a"] * np.power(params["b"], x) * np.power(x, params["c"])

    def guess_initial(self, x, y):
        cols = np.column_stack([np.ones_like(x), x, _safe_ln(x)])
        c = _lin_guess(cols, _safe_ln(y))
        return [np.exp(c[0]), np.exp(c[1]), c[2]]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}·{params['b']:.6g}^x·x^{params['c']:.6g}"


class ModifiedHoerlStrategy(BaseFitStrategy):
    """y = a·b^(1/x)·x^c"""
    name = "修正 Hoerl 模型 y=a·b^(1/x)·x^c"
    description = "Hoerl 变体，指数部分以 1/x 进入，适合先降后升的响应。要求 x > 0。"
    family = "幂律族"
    param_names = ["a", "b", "c"]
    needs_positive_x = True

    def predict(self, x, params):
        return params["a"] * np.power(params["b"], 1.0 / np.maximum(x, 1e-12)) * np.power(x, params["c"])

    def guess_initial(self, x, y):
        cols = np.column_stack([np.ones_like(x), 1.0 / np.maximum(x, 1e-12), _safe_ln(x)])
        c = _lin_guess(cols, _safe_ln(y))
        return [np.exp(c[0]), np.exp(c[1]), c[2]]

    def format_equation(self, params):
        return f"y = {params['a']:.6g}·{params['b']:.6g}^(1/x)·x^{params['c']:.6g}"


# 注册清单（供 __init__ 自动加载）
EXPONENTIAL_MODELS = [
    ExponentialStrategy(),
    ModifiedExponentialStrategy(),
    LogarithmStrategy(),
    ReciprocalLogarithmStrategy(),
    VaporPressureStrategy(),
    PowerStrategy(),
    ModifiedPowerStrategy(),
    ShiftedPowerStrategy(),
    GeometricStrategy(),
    ModifiedGeometricStrategy(),
    RootStrategy(),
    HoerlStrategy(),
    ModifiedHoerlStrategy(),
]
