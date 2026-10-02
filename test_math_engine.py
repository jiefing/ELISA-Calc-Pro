# -*- coding: utf-8 -*-
"""
数学回归与清洗体系独立联调测试本 (test_math_engine.py)
自动验证 4PL、线性多项式、对数回归及剪贴板字符智能清理防护边界情况！
"""

import io
import sys
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception:
        pass

import unittest
from core.data_models import StandardPoint, SamplePoint
from core.clipboard_utils import parse_clipboard_text, format_to_clipboard_text, clean_float_array
from math_engine import get_strategy_by_name, AVAILABLE_MODELS, FitEngineError


class TestMathEngineAndCore(unittest.TestCase):

    def test_clipboard_utils(self):
        print("\n[回归检测 1] 开始效验剪贴板文本与隐匿垃圾行深层洗脑引擎...")
        raw_clip = "0.123\t0.456 \r\n 0.789\t \n\t\n  1.234 \t nan "
        parsed = parse_clipboard_text(raw_clip)
        self.assertTrue(len(parsed) >= 3)

        # 验证数组洗提列能力 (过滤空和脏文)
        test_col = [" 1.23 ", " ", "null", "\t0.05", "", "abc", "50.0"]
        floats, idx_list = clean_float_array(test_col)
        print(f"  原始脏数据列: {test_col}\n  洗尽浮点精细实干清单: {floats}, 对照原位号: {idx_list}")
        self.assertEqual(floats, [1.23, 0.05, 50.0])
        self.assertEqual(idx_list, [0, 3, 6])

    def test_linear_regression(self):
        print("\n[回归检测 2] 验证 直线回归 算法拟合与可塑回算能力...")
        model = get_strategy_by_name("直线回归 (Linear Regression)")
        stds = [StandardPoint(x=10, y=0.2), StandardPoint(x=50, y=1.0), StandardPoint(x=100, y=2.0)]
        samples = [SamplePoint(sample_id="S01", y=1.5), SamplePoint(sample_id="S02", y=0.5)]

        result = model.fit_and_predict(stds, samples)
        print("  【直线优度报告】：")
        print(result.generate_report_text())
        self.assertTrue(result.success)
        self.assertAlmostEqual(result.sample_points[0].calc_x, 75.0, places=1)
        self.assertAlmostEqual(result.sample_points[1].calc_x, 25.0, places=1)

    def test_quadratic_regression(self):
        print("\n[回归检测 3] 验证 二次多项式 抛物回归根式优投解析方案...")
        model = get_strategy_by_name("二次多项式拟合 (Quadratic)")
        # 精确二次曲线 y = 0.0001 * x^2 + 0.01 * x + 0.1
        stds = [StandardPoint(x=0, y=0.1), StandardPoint(x=50, y=0.85), StandardPoint(x=100, y=2.1), StandardPoint(x=150, y=3.85)]
        samples = [SamplePoint(sample_id="Q1", y=0.85), SamplePoint(sample_id="Q2", y=15.0)] # 15.0大笔超界触发异常屏蔽

        res = model.fit_and_predict(stds, samples)
        print("  【二次参数运算简表】:")
        print(res.generate_report_text())
        self.assertTrue(res.success)
        self.assertAlmostEqual(res.sample_points[0].calc_x, 50.0, places=4)
        self.assertEqual(res.sample_points[1].calc_x, ">上限")

    def test_four_pl_regression(self):
        print("\n[回归检测 4] 核心经典：四参数逻辑回归 (4PL) 极限保护与平稳回流验证...")
        model = get_strategy_by_name("四参数逻辑回归 (4PL)")
        # A=0.05, D=2.5, B=1.2, C=40
        stds = [
            StandardPoint(x=1.0, y=0.08),
            StandardPoint(x=10.0, y=0.45),
            StandardPoint(x=40.0, y=1.27),
            StandardPoint(x=100.0, y=1.95),
            StandardPoint(x=300.0, y=2.35)
        ]
        samples = [
            SamplePoint(sample_id="T01", y=1.27),
            SamplePoint(sample_id="T_Max", y=3.00), # 超天涯极大界线
            SamplePoint(sample_id="T_Min", y=0.01)  # 低破地板极小渐近极位
        ]

        res = model.fit_and_predict(stds, samples)
        print(f"  解归报告输出:\n{res.generate_report_text()}")
        self.assertTrue(res.success)
        self.assertAlmostEqual(res.sample_points[0].calc_x, 40.0, delta=5.0)
        self.assertEqual(res.sample_points[1].calc_x, ">上限")
        self.assertEqual(res.sample_points[2].calc_x, "<下限")

        print("  正在验证 4PL 对输入浓度 x<=0 的安全极锁屏断抛错机能...")
        with self.assertRaises(FitEngineError) as ctx:
            model.fit_and_predict([StandardPoint(x=0, y=0.05)] + stds[:3], samples)
        print(f"  成功斩收异常言令: {ctx.exception}")
        self.assertIn("要求浓度必须大于0", str(ctx.exception))

    def test_logit_log_regression(self):
        print("\n[回归检测 5] 验证 竞争性转换比对法 (Logit-Log) ...")
        model = get_strategy_by_name("Logit-Log 回归 (竞争法)")
        stds = [StandardPoint(x=1, y=2.0), StandardPoint(x=10, y=1.2), StandardPoint(x=100, y=0.4)]
        samples = [SamplePoint(sample_id="L1", y=1.2)]
        res = model.fit_and_predict(stds, samples)
        self.assertTrue(res.success)
        print(res.generate_report_text())
        print(f"  代值 y=1.2 回转实测浓度: {res.sample_points[0].calc_x}")
        self.assertIsNotNone(res.sample_points[0].calc_x)


if __name__ == "__main__":
    unittest.main()
