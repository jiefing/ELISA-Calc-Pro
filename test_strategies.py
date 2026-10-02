# -*- coding: utf-8 -*-
"""
单元测试与策略校验脚本 (test_strategies.py)
对基础扣减、4PL 曲线拟合及细胞活力策略进行算法校验。
"""

import sys
import unittest
import numpy as np

from models.data_structures import Plate, WellType
from strategies import BlankSubtractionStrategy, FourPLStrategy, CellViabilityStrategy
from strategies.math_models import four_pl_func as four_param_logistic


class TestAssayStrategies(unittest.TestCase):

    def setUp(self):
        # 初始化一个 96 孔板
        self.plate = Plate(96)

    def test_blank_subtraction(self):
        """测试基础扣减策略"""
        print("\n[测试] 运行基础扣减策略校验...")

        # 标记空白孔并设值
        self.plate.get_well("A", 12).well_type = WellType.BLANK
        self.plate.get_well("A", 12).raw_value = 0.050

        self.plate.get_well("B", 12).well_type = WellType.BLANK
        self.plate.get_well("B", 12).raw_value = 0.060

        # 期望均值 0.055

        # 标记样品孔并设值
        self.plate.get_well("C", 1).well_type = WellType.SAMPLE
        self.plate.get_well("C", 1).raw_value = 0.855

        # 运行策略
        strategy = BlankSubtractionStrategy()
        strategy.calculate(self.plate, {})

        result_well = self.plate.get_well("C", 1)
        expected_result = round(0.855 - 0.055, 4)

        print(f"  原始值: 0.855, 空白均值: 0.055, 计算结果: {result_well.calc_result}, 期望值: {expected_result}")
        self.assertEqual(round(result_well.calc_result, 4), expected_result)

    def test_cell_viability(self):
        """测试细胞活力计算策略"""
        print("\n[测试] 运行细胞活力 (CCK-8) 策略校验...")

        # 标记空白孔
        self.plate.get_well("A", 12).well_type = WellType.BLANK
        self.plate.get_well("A", 12).raw_value = 0.05

        # 标记对照孔
        self.plate.get_well("A", 5).well_type = WellType.CONTROL
        self.plate.get_well("A", 5).raw_value = 1.25

        # 标记样品孔
        self.plate.get_well("A", 3).well_type = WellType.SAMPLE
        self.plate.get_well("A", 3).raw_value = 0.65

        # 计算逻辑：
        # Blank均值 = 0.05
        # Control均值 = 1.25
        # 分母 = 1.25 - 0.05 = 1.20
        # 样品扣除空白 = 0.65 - 0.05 = 0.60
        # 活力 = 0.60 / 1.20 * 100 = 50.0%

        strategy = CellViabilityStrategy()
        strategy.calculate(self.plate, {})

        result_well = self.plate.get_well("A", 3)
        print(f"  样品值: 0.65, 对照均值: 1.25, 空白均值: 0.05, 计算结果: {result_well.calc_result}%, 期望值: 50.0%")
        self.assertEqual(result_well.calc_result, 50.0)

    def test_four_pl_fit(self):
        """测试 4PL 回归拟合策略"""
        print("\n[测试] 运行 4PL 拟合策略校验...")

        # 模拟 4PL 参数
        # A=0.05 (底), B=1.2 (斜率), C=50 (EC50), D=2.5 (顶)
        A, B, C, D = 0.05, 1.2, 50.0, 2.5

        concs = [0.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0]

        # 标记 Standard 并设定模拟 OD 值
        std_wells = []
        for i, conc in enumerate(concs):
            row = chr(ord("A") + i)
            well = self.plate.get_well(row, 1)
            well.well_type = WellType.STANDARD
            # 根据 4PL 方程计算 OD，如果 conc 为 0，我们加一点极小值防止除以 0
            x = conc if conc > 0 else 1e-5
            well.raw_value = float(four_param_logistic(x, A, B, C, D))
            well.std_conc = conc
            std_wells.append(well)

        # 标记 Sample 孔
        sample_well = self.plate.get_well("B", 3)
        sample_well.well_type = WellType.SAMPLE
        # 设定一个已知的浓度反推，如浓度为 80.0
        sample_well.raw_value = float(four_param_logistic(80.0, A, B, C, D))

        # 运行拟合策略 (设置不扣减空白)
        strategy = FourPLStrategy()
        # 传入 std_concs 列表
        strategy.calculate(self.plate, {"subtract_blank": False, "std_concentrations": concs})

        # 校验反推的浓度是否接近 80.0
        calc_conc = sample_well.calc_result
        print(f"  设定已知浓度: 80.0, 拟合反推得到浓度: {calc_conc}")

        self.assertIsNotNone(calc_conc)
        self.assertTrue(abs(calc_conc - 80.0) < 1.0)


if __name__ == "__main__":
    unittest.main()
