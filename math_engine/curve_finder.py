# -*- coding: utf-8 -*-
"""
CurveFinder 自动寻优引擎 (curve_finder.py) - V3.0
忠实移植 CurveExpert 1.4 的 CurveFinder 概念：
对指定模型族逐一尝试拟合，按 R²（或标准误）从好到坏排名；
发散/异常的模型自动剔除；插值模型不参与自动寻优。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Callable, Iterable
import warnings
import numpy as np
from scipy.optimize import OptimizeWarning
from core.data_models import StandardPoint, SamplePoint
from .strategy_base import BaseFitStrategy, FitEngineError
from .models_linear import PolynomialStrategy


@dataclass
class RankingEntry:
    """单个模型的拟合排名条目"""
    rank: int = 0
    model_name: str = ""
    family: str = ""
    r_squared: float = 0.0
    standard_error: float = 0.0
    aic: float = float("inf")
    note: str = ""
    strategy: Optional[BaseFitStrategy] = None
    result: object = None


def run_curve_finder(
    std_points: List[StandardPoint],
    sample_points: List[SamplePoint],
    models: Iterable[BaseFitStrategy],
    families: Optional[List[str]] = None,
    max_poly_order: int = 6,
    weights: Optional[str] = None,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    abort_flag: Optional[Callable[[], bool]] = None,
) -> List[RankingEntry]:
    """
    对给定模型列表执行全量拟合与排名。
    families 为 None 表示全部模型族；多项式按 2..max_poly_order 展开。
    """
    work_list: List[BaseFitStrategy] = []
    for model in models:
        if model.is_interpolation:
            continue
        if families and model.family not in families:
            continue
        if isinstance(model, PolynomialStrategy):
            for order in range(2, max_poly_order + 1):
                work_list.append(PolynomialStrategy(order=order))
        else:
            work_list.append(model)

    entries: List[RankingEntry] = []
    total = len(work_list)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", OptimizeWarning)
        with np.errstate(all="ignore"):
            for idx, model in enumerate(work_list):
                if abort_flag is not None and abort_flag():
                    break
                if progress_cb is not None:
                    progress_cb(idx + 1, total, model.name)
                try:
                    result = model.fit_and_predict(std_points, sample_points, weights=weights)
                    entries.append(RankingEntry(
                        model_name=model.name,
                        family=model.family,
                        r_squared=result.r_squared,
                        standard_error=result.standard_error,
                        aic=result.aic,
                        strategy=model,
                        result=result,
                    ))
                except FitEngineError as e:
                    entries.append(RankingEntry(
                        model_name=model.name,
                        family=model.family,
                        note=str(e)[:120],
                        strategy=model,
                    ))
                except Exception as e:
                    entries.append(RankingEntry(
                        model_name=model.name,
                        family=model.family,
                        note=f"异常: {e}"[:120],
                        strategy=model,
                    ))

    # 排序：成功者按 R² 降序（并列按标准误升序），失败者排最后
    def sort_key(entry: RankingEntry):
        if entry.result is not None:
            return (0, -entry.r_squared, entry.standard_error)
        return (1, 0.0, 0.0)

    entries.sort(key=sort_key)
    for i, entry in enumerate(entries, start=1):
        entry.rank = i
    return entries
