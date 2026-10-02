# -*- coding: utf-8 -*-
"""
数据模型层 (Model)
定义 WellType 枚举, Well 类, Plate 类
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Union

class WellType(Enum):
    UNUSED = 0
    BLANK = 1
    STANDARD = 2
    SAMPLE = 3
    CONTROL = 4
    CUSTOM = 5

@dataclass
class Well:
    row: str                # 行标识，如 'A'
    col: int                # 列标识，如 1
    label: str              # 组合标识，如 "A1"
    raw_value: float        # 主波长原始 OD
    ref_value: Optional[float] = None  # 参比波长原始 OD (可选)
    well_type: WellType = WellType.UNUSED
    std_conc: Optional[float] = None   # 已知标曲浓度
    calc_result: Optional[Union[float, str]] = None # 最终计算结果(浓度或存活率，支持>Max, <Min等拦截词)
    group_id: str = ""      # 样品复孔组编号，如 "S1"

    @property
    def corrected_value(self) -> float:
        """核心业务逻辑：如果存在参比波长，强制返回主波长-参比波长的净值"""
        if self.ref_value is not None:
            return self.raw_value - self.ref_value
        return self.raw_value

@dataclass
class Plate:
    plate_size: int = 96 # 96 或 384
    wells: Dict[str, Well] = field(default_factory=dict)
    source_file: str = ""
    # 存储全局计算的统计参数，例如 4PL 的拟合参数 A, B, C, D 和 R_squared 等
    statistics: dict = field(default_factory=dict)

    def __post_init__(self):
        # 如果 wells 为空，则自动根据 plate_size 初始化孔位
        if not self.wells:
            self._initialize_wells()

    @property
    def rows(self) -> int:
        return 16 if self.plate_size == 384 else 8

    @property
    def cols(self) -> int:
        return 24 if self.plate_size == 384 else 12

    @property
    def row_labels(self) -> List[str]:
        if self.plate_size == 384:
            return [chr(65 + i) for i in range(16)]  # A-P
        return [chr(65 + i) for i in range(8)]    # A-H

    def _initialize_wells(self):
        row_lbls = self.row_labels
        for r in row_lbls:
            for c in range(1, self.cols + 1):
                label = f"{r}{c}"
                # 初始原始 OD 值置为 0.0，类型设为 UNUSED
                self.wells[label] = Well(
                    row=r,
                    col=c,
                    label=label,
                    raw_value=0.0,
                    well_type=WellType.UNUSED
                )

    def get_well(self, row: str, col: int) -> Optional[Well]:
        label = f"{row}{col}"
        return self.wells.get(label)

    def set_well_value(self, row: str, col: int, val: float, ref_val: Optional[float] = None):
        well = self.get_well(row, col)
        if well:
            well.raw_value = val
            well.ref_value = ref_val

    def get_wells_by_type(self, well_type: WellType) -> List[Well]:
        """返回所有符合指定类型的孔"""
        return [w for w in self.wells.values() if w.well_type == well_type]

    def all_wells(self) -> List[Well]:
        """返回板上所有孔的列表"""
        return list(self.wells.values())
