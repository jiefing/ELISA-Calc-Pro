# -*- coding: utf-8 -*-
"""
用户自定义模型模块 (models_user.py) - V3.0
支持用户在界面中定义任意回归模型（表达式语言与 CurveExpert 1.4 一致），
并持久化保存到 user_models.json，供跨会话复用。
"""

import os
import sys
import json
import numpy as np
from typing import List, Dict, Optional
from scipy.optimize import curve_fit
from core.data_models import StandardPoint, SamplePoint, CurveFitResult
from core.expression_parser import UserModelEvaluator, ExpressionError
from .strategy_base import BaseFitStrategy, FitEngineError


def _user_models_path() -> str:
    """用户模型存储路径：与主程序同目录（兼容 PyInstaller 打包）"""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "user_models.json")


def load_user_model_definitions() -> List[dict]:
    """读取全部已保存的用户模型定义 [{'name': ..., 'expression': ...}]"""
    path = _user_models_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict) and d.get("name") and d.get("expression")]
    except Exception:
        return []
    return []


def save_user_model_definitions(defs: List[dict]) -> None:
    """保存用户模型定义列表到磁盘"""
    path = _user_models_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(defs, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class UserDefinedModelStrategy(BaseFitStrategy):
    """
    用户自定义模型策略。
    通过 expression 编译出 evaluator，参数按字母出现顺序自动检测。
    """

    family = "用户自定义"

    def __init__(self, name: str = "", expression: str = ""):
        self._name = name or "用户自定义模型"
        self._expression = expression
        self._evaluator = None
        self._last_params: Optional[Dict[str, float]] = None
        if expression:
            self.rebuild(expression)

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"用户自定义模型：y = {self._expression}（表达式语言与 CurveExpert 一致）"

    @property
    def expression(self) -> str:
        return self._expression

    def rebuild(self, expression: str):
        """重新编译表达式（非法时抛 ExpressionError）"""
        self._expression = expression
        self._evaluator = UserModelEvaluator(expression)
        self._last_params = None

    @property
    def param_names(self) -> List[str]:
        return list(self._evaluator.param_names) if self._evaluator else []

    def predict(self, x, params):
        if self._evaluator is None:
            raise FitEngineError("用户模型尚未定义表达式。")
        special = self._evaluator.compute_special_vars(np.asarray([np.nan]), np.asarray([np.nan]))
        # 通用拟合流程中 special 变量由 fit 时计算；此处用于渲染曲线
        return self._evaluator.evaluate(x, params, self._fit_special)

    def guess_initial(self, x, y):
        """多组初始猜测尝试：优先上次成功参数，其次 1.0 / 0.5 / 均值尺度"""
        k = len(self.param_names)
        if self._last_params and len(self._last_params) == k:
            return [self._last_params[p] for p in self.param_names]
        mean_y = float(np.mean(y))
        candidates = []
        if abs(mean_y) > 1e-9:
            candidates.append([mean_y] + [1.0] * (k - 1))
        candidates.append([1.0] * k)
        candidates.append([0.5] * k)
        return candidates[0]

    def fit_and_predict(self, std_points, sample_points, weights=None, **kwargs):
        if self._evaluator is None:
            raise FitEngineError("用户模型尚未定义表达式，请先在【自定义模型】对话框中创建。")
        n_params = len(self.param_names)
        self.validate_std_points_length(std_points, min_len=n_params + 1)

        x_arr, y_arr = self._extract_xy(std_points)
        self._fit_special = self._evaluator.compute_special_vars(x_arr, y_arr)
        sigma = self._weights_to_sigma(x_arr, y_arr, weights)

        def eq(x, *args):
            params = dict(zip(self.param_names, args))
            return self._evaluator.evaluate(np.asarray(x, dtype=float), params, self._fit_special)

        # 多种初始猜测依次尝试，直至收敛
        k = n_params
        mean_y = float(np.mean(y_arr))
        candidates = []
        if self._last_params and len(self._last_params) == k:
            candidates.append([self._last_params[p] for p in self.param_names])
        if abs(mean_y) > 1e-9:
            candidates.append([mean_y] + [1.0] * (k - 1))
        candidates.append([1.0] * k)
        candidates.append([0.5] * k)
        if k >= 2:
            candidates.append([0.1] * k)

        best = None  # (popt, y_pred, r_squared)
        last_err = ""
        for p0 in candidates:
            try:
                popt, _ = curve_fit(eq, x_arr, y_arr, p0=p0, sigma=sigma, method="lm", maxfev=30000)
                y_pred = self._evaluator.evaluate(x_arr, dict(zip(self.param_names, popt)), self._fit_special)
                r2 = self._r_squared(y_arr, y_pred)
                if best is None or r2 > best[2]:
                    best = (popt, y_pred, r2)
                if r2 > 0.99:
                    break
            except RuntimeError as e:
                last_err = str(e)
            except Exception as e:
                last_err = str(e)
        if best is None:
            raise FitEngineError(f"自定义模型无法收敛，请检查表达式与初始值（可尝试调整参数初值）。\n{last_err}")
        popt, y_pred, r_squared = best

        params = dict(zip(self.param_names, [float(v) for v in popt]))
        self._last_params = params
        se = self._standard_error(y_arr, y_pred, n_params)
        aic = self._aic(len(y_arr), n_params, float(np.sum((y_arr - y_pred) ** 2)))

        span = float(np.max(x_arr) - np.min(x_arr))
        curve_x = np.linspace(float(np.min(x_arr)) - span * 0.05, float(np.max(x_arr)) + span * 0.05, 200)
        curve_y = self._evaluator.evaluate(curve_x, params, self._fit_special)

        res_samples = self._solve_samples(sample_points, params, x_arr, y_arr)

        return CurveFitResult(
            model_name=self.name,
            success=True,
            equation_str=f"y = {self._expression}",
            parameters=params,
            r_squared=r_squared,
            standard_error=se,
            aic=aic,
            family=self.family,
            param_names=list(self.param_names),
            is_log_x=False,
            std_points=std_points,
            sample_points=res_samples,
            curve_x=curve_x,
            curve_y=curve_y,
            predict_fn=lambda xs, prm=params: self._evaluator.evaluate(
                np.asarray(xs, dtype=float), prm, self._fit_special),
            x_range=(float(np.min(x_arr)), float(np.max(x_arr))),
        )


def build_user_strategies() -> List[UserDefinedModelStrategy]:
    """从磁盘加载全部用户模型并实例化策略"""
    strategies = []
    for item in load_user_model_definitions():
        try:
            strategies.append(UserDefinedModelStrategy(name=item["name"], expression=item["expression"]))
        except ExpressionError:
            continue
    return strategies
