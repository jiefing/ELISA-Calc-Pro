# -*- coding: utf-8 -*-
"""
算法策略抽象基类
"""
from abc import ABC, abstractmethod
from models.data_structures import Plate

class StrategyError(Exception):
    """策略算法计算中的自定义异常类"""
    pass

class BaseAssayStrategy(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """策略的中文名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """策略的功能描述说明"""
        pass

    @abstractmethod
    def calculate(self, plate: Plate, params: dict = None) -> Plate:
        """
        所有算法子类必须实现此方法。
        注意：任何计算必须调用 Well.corrected_value 获取基础数据。
        """
        pass

    def post_process_samples(self, plate: Plate) -> Plate:
        """
        样品复孔与编号管理合并统计。
        遍历所有 Sample 孔，按 group_id 进行分组 (GroupBy)，
        计算它们的 OD 均值、最终浓度/活力均值和复孔 CV%。
        """
        from collections import defaultdict
        import numpy as np
        from models.data_structures import WellType

        # 1. 搜集并按 group_id 分组
        sample_groups = defaultdict(list)
        for well in plate.all_wells():
            if well.well_type == WellType.SAMPLE:
                # 若没有分配 group_id，则独立分为一个单孔组
                g_id = well.group_id.strip() if (well.group_id and well.group_id.strip()) else f"U_{well.label}"
                sample_groups[g_id].append(well)

        # 2. 对每个组分别汇总
        summary = {}
        for g_id, wells in sample_groups.items():
            # 获取孔位标号列表，排序以更易读
            labels = sorted([w.label for w in wells])

            # 计算 OD 均值 (使用 corrected_value)
            ods = [w.corrected_value for w in wells if w.raw_value is not None]
            od_mean = float(np.mean(ods)) if ods else 0.0

            # 计算最终结果均值 (仅统计 float 实数，拦截的 >Max / <Min 字符排除不统计)
            calcs = [w.calc_result for w in wells if isinstance(w.calc_result, float)]
            calc_mean = float(np.mean(calcs)) if calcs else 0.0

            # 计算浓度/活力值 CV%
            if len(calcs) > 1 and calc_mean > 1e-5:
                calc_std = np.std(calcs, ddof=1)
                calc_cv = float((calc_std / calc_mean) * 100.0)
            else:
                calc_cv = 0.0

            summary[g_id] = {
                "wells": labels,
                "od_mean": od_mean,
                "calc_mean": calc_mean,
                "calc_cv": calc_cv
            }

        # 存回 plate 统计字典
        plate.statistics["sample_summary"] = summary
        return plate
