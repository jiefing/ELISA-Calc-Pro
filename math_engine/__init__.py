# -*- coding: utf-8 -*-
"""
Math Engine 数学计算策略包入口
统一暴露核心计算算法列表与实例寻优指派路由。
"""

from .strategy_base import BaseFitStrategy, FitEngineError
from .models_linear import LinearRegressionStrategy, QuadraticRegressionStrategy
from .models_logistic import FourPLStrategy, LogitLogStrategy

# 注册可用的全局科学分析算能清单（供左侧顶栏 QComboBox 自动枚举加载使用）
AVAILABLE_MODELS = [
    FourPLStrategy(),
    LinearRegressionStrategy(),
    QuadraticRegressionStrategy(),
    LogitLogStrategy(),
]

MODEL_NAME_MAP = {model.name: model for model in AVAILABLE_MODELS}


def get_strategy_by_name(model_name: str) -> BaseFitStrategy:
    """
    根据给出的中文可读策略名拉出具体的算数解算分析子引擎
    """
    strategy = MODEL_NAME_MAP.get(model_name)
    if not strategy:
        # 如无找到精准匹配优先指派最具通用度名片级的四参数策略
        return AVAILABLE_MODELS[0]
    return strategy
# -*- coding: utf-8 -*-
"""
Math Engine 数学计算策略包入口 - V3.0
统一暴露核心计算算法列表与实例寻优指派路由。
V3.0 起内置约 40 个回归/插值模型（对齐 CurveExpert 1.4），
并支持用户自定义模型与 CurveFinder 自动寻优。
"""

from typing import List

from .strategy_base import BaseFitStrategy, FitEngineError, WEIGHT_MODES
from .models_linear import LinearRegressionStrategy, QuadraticRegressionStrategy, PolynomialStrategy
from .models_logistic import FourPLStrategy, LogitLogStrategy
from .models_exponential import EXPONENTIAL_MODELS
from .models_growth import GROWTH_MODELS
from .models_misc import MISC_MODELS
from .models_interp import INTERP_MODELS
from .models_user import (
    UserDefinedModelStrategy,
    build_user_strategies,
    load_user_model_definitions,
    save_user_model_definitions,
)
from .curve_finder import run_curve_finder, RankingEntry


# 内置模型注册清单（按族分组顺序）
_BASE_MODELS: List[BaseFitStrategy] = [
    LinearRegressionStrategy(),
    QuadraticRegressionStrategy(),
    PolynomialStrategy(order=3),
    FourPLStrategy(),
    LogitLogStrategy(),
]

AVAILABLE_MODELS: List[BaseFitStrategy] = (
    _BASE_MODELS + EXPONENTIAL_MODELS + GROWTH_MODELS + MISC_MODELS + INTERP_MODELS
)


def get_all_models() -> List[BaseFitStrategy]:
    """全部可计算模型 = 内置模型 + 用户自定义模型"""
    return AVAILABLE_MODELS + build_user_strategies()


def get_families() -> List[str]:
    """按出现顺序返回全部模型族名（供 CurveFinder 勾选）"""
    seen = []
    for model in AVAILABLE_MODELS:
        if model.family not in seen:
            seen.append(model.family)
    return seen


def get_strategy_by_name(model_name: str) -> BaseFitStrategy:
    """
    根据给出的中文可读策略名拉出具体的算数解算分析子引擎。
    找不到时依次在用户自定义模型中查找，最后兜底四参数策略。
    """
    for model in AVAILABLE_MODELS:
        if model.name == model_name:
            return model
    for model in build_user_strategies():
        if model.name == model_name:
            return model
    return AVAILABLE_MODELS[0]
