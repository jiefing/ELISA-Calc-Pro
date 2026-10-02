# -*- coding: utf-8 -*-
"""
V3.0 模型库全量验证测试 (test_models_v3.py)
用每个模型的已知参数生成合成数据，验证：
  1. 拟合收敛且 R² 接近 1
  2. 样本浓度反推准确
  3. 表达式解析器与 CurveFinder 工作正常
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
import numpy as np
from core.data_models import StandardPoint, SamplePoint
from core.expression_parser import UserModelEvaluator, ExpressionError
from math_engine import (
    AVAILABLE_MODELS, get_all_models, get_strategy_by_name,
    run_curve_finder, FitEngineError,
)
from math_engine.models_linear import PolynomialStrategy


def make_points(xs, ys):
    return [StandardPoint(x=float(x), y=float(y)) for x, y in zip(xs, ys)]


class TestModelLibrary(unittest.TestCase):

    def _check_model(self, model, xs, ys, probe_x, model_name_hint=""):
        """拟合 + 反推校验"""
        stds = make_points(xs, ys)
        samples = [SamplePoint(sample_id="T", y=float(np.interp(probe_x, xs, ys)))]
        res = model.fit_and_predict(stds, samples)
        self.assertTrue(res.success, f"{model.name} 拟合失败")
        self.assertGreater(res.r_squared, 0.98, f"{model.name} R²={res.r_squared} 偏低")
        calc = res.sample_points[0].calc_x
        if isinstance(calc, (int, float)):
            self.assertAlmostEqual(calc, probe_x, delta=abs(probe_x) * 0.2 + 0.2,
                                   msg=f"{model.name} 反推 {calc} != {probe_x}")
        else:
            self.fail(f"{model.name} 反推结果异常: {calc}")
        return res

    def test_exponential_family(self):
        cases = [
            (get_strategy_by_name("指数函数 y=a·e^(b·x)"), np.linspace(0, 5, 10), lambda x: 2 * np.exp(0.3 * x), 3.0),
            (get_strategy_by_name("修正指数函数 y=a·e^(b/x)"), np.linspace(1, 10, 10), lambda x: 3 * np.exp(2 / x), 4.0),
            (get_strategy_by_name("对数函数 y=a+b·ln(x)"), np.linspace(1, 10, 10), lambda x: 1 + 2 * np.log(x), 5.0),
            (get_strategy_by_name("倒数对数函数 y=1/(a+b·ln(x))"), np.linspace(1, 10, 10), lambda x: 1 / (0.5 + 0.3 * np.log(x)), 5.0),
            (get_strategy_by_name("蒸汽压模型 y=e^(a+b/x+c·ln(x))"), np.linspace(1, 10, 10), lambda x: np.exp(1 + 2 / x + 0.5 * np.log(x)), 5.0),
        ]
        for model, xs, fn, px in cases:
            ys = fn(xs)
            if np.any(ys <= 0):
                ys = ys - np.min(ys) + 0.5
            self._check_model(model, xs, ys, px)

    def test_power_family(self):
        cases = [
            (get_strategy_by_name("幂函数 y=a·x^b"), np.linspace(1, 10, 10), lambda x: 2 * x ** 1.5, 4.0),
            (get_strategy_by_name("修正幂函数 y=a·b^x"), np.linspace(0, 5, 10), lambda x: 3 * 1.5 ** x, 3.0),
            (get_strategy_by_name("平移幂函数 y=a·(x-b)^c"), np.linspace(2, 10, 10), lambda x: 2 * (x - 1) ** 0.8, 5.0),
            (get_strategy_by_name("几何函数 y=a·x^(b·x)"), np.linspace(1, 5, 10), lambda x: 2 * x ** (0.2 * x), 3.0),
            (get_strategy_by_name("修正几何函数 y=a·x^(b/x)"), np.linspace(1, 5, 10), lambda x: 2 * x ** (1 / x), 3.0),
            (get_strategy_by_name("根函数 y=a^(1/x)"), np.linspace(0.5, 5, 10), lambda x: 2 ** (1 / x), 2.0),
            (get_strategy_by_name("Hoerl 模型 y=a·b^x·x^c"), np.linspace(1, 8, 10), lambda x: 2 * 1.3 ** x * x ** 0.5, 4.0),
            (get_strategy_by_name("修正 Hoerl 模型 y=a·b^(1/x)·x^c"), np.linspace(1, 8, 10), lambda x: 2 * 1.2 ** (1 / x) * x ** 0.6, 4.0),
        ]
        for model, xs, fn, px in cases:
            ys = fn(xs)
            self._check_model(model, xs, ys, px)

    def test_growth_family(self):
        cases = [
            (get_strategy_by_name("指数关联 (2) y=a·(1-e^(-b·x))"), np.linspace(0, 6, 10), lambda x: 5 * (1 - np.exp(-0.8 * x)), 3.0),
            (get_strategy_by_name("指数关联 (3) y=a·(b-e^(-c·x))"), np.linspace(0, 6, 10), lambda x: 2 * (1.5 - np.exp(-0.8 * x)), 3.0),
            (get_strategy_by_name("饱和生长模型 y=a·x/(b+x)"), np.linspace(0.2, 10, 10), lambda x: 10 * x / (2 + x), 5.0),
            (get_strategy_by_name("Gompertz 模型 y=a·e^(-e^(b-c·x))"), np.linspace(0, 10, 12), lambda x: 8 * np.exp(-np.exp(2 - 0.8 * x)), 5.0),
            (get_strategy_by_name("Logistic 模型 y=a/(1+e^(b-c·x))"), np.linspace(0, 10, 12), lambda x: 8 / (1 + np.exp(2 - 0.8 * x)), 5.0),
            (get_strategy_by_name("Richards 模型 y=a/(1+e^(b-c·x))^(1/d)"), np.linspace(0, 10, 12), lambda x: 8 / (1 + np.exp(2 - 0.8 * x)) ** 2, 5.0),
            (get_strategy_by_name("MMF 模型 y=(a·b+c·x^d)/(b+x^d)"), np.linspace(0, 10, 12), lambda x: (1 * 5 + 8 * x ** 1.5) / (5 + x ** 1.5), 5.0),
            (get_strategy_by_name("Weibull 模型 y=a-b·e^(-c·x^d)"), np.linspace(0, 10, 12), lambda x: 10 - 6 * np.exp(-0.5 * x ** 1.2), 5.0),
        ]
        for model, xs, fn, px in cases:
            ys = fn(xs)
            self._check_model(model, xs, ys, px)

    def test_yield_density_family(self):
        cases = [
            (get_strategy_by_name("倒数模型 y=1/(a+b·x)"), np.linspace(0, 8, 10), lambda x: 1 / (2 + 0.5 * x), 4.0),
            (get_strategy_by_name("倒数二次模型 y=1/(a+b·x+c·x²)"), np.linspace(0, 8, 10), lambda x: 1 / (2 + 0.5 * x + 0.1 * x ** 2), 4.0),
            (get_strategy_by_name("Bleasdale 模型 y=(a+b·x)^(-1/c)"), np.linspace(0, 8, 10), lambda x: (2 + 0.5 * x) ** (-1 / 1.5), 4.0),
            (get_strategy_by_name("Harris 模型 y=1/(a+b·x^c)"), np.linspace(0, 8, 10), lambda x: 1 / (2 + 0.5 * x ** 1.5), 4.0),
        ]
        for model, xs, fn, px in cases:
            ys = fn(xs)
            self._check_model(model, xs, ys, px)

    def test_misc_family(self):
        xs = np.linspace(0, 10, 16)
        self._check_model(get_strategy_by_name("正弦拟合 y=a+b·cos(c·x+d)"), xs, 3 + 2 * np.cos(1.5 * xs + 0.5), 4.0)
        xs2 = np.linspace(0, 6, 12)
        self._check_model(get_strategy_by_name("高斯模型 y=a·e^(-(x-b)²/(2c²))"), xs2, 5 * np.exp(-(xs2 - 3) ** 2 / (2 * 1.2 ** 2)), 3.0)
        xs3 = np.linspace(0.5, 8, 10)
        self._check_model(get_strategy_by_name("双曲拟合 y=a+b/x"), xs3, 1 + 3 / xs3, 4.0)
        self._check_model(get_strategy_by_name("热容模型 y=a+b·x+c/x²"), xs3, 2 + 0.5 * xs3 + 4 / xs3 ** 2, 4.0)
        xs4 = np.linspace(0, 8, 12)
        self._check_model(get_strategy_by_name("有理函数 y=(a+b·x)/(1+c·x+d·x²)"), xs4, (1 + 2 * xs4) / (1 + 0.5 * xs4 + 0.2 * xs4 ** 2), 4.0)

    def test_polynomial(self):
        model = get_strategy_by_name("多项式 (Polynomial)")
        xs = np.linspace(0, 6, 10)
        ys = 1 + 2 * xs + 0.5 * xs ** 2 + 0.1 * xs ** 3
        self._check_model(model, xs, ys, 3.0)

    def test_interpolation_models(self):
        from math_engine.models_interp import INTERP_MODELS
        xs = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
        ys = np.array([1.0, 1.8, 3.1, 4.5, 6.2, 8.0])
        for model in INTERP_MODELS:
            res = model.fit_and_predict(make_points(xs, ys), [SamplePoint(sample_id="T", y=4.5)])
            self.assertTrue(res.success, f"{model.name} 失败")
            self.assertEqual(res.r_squared, 1.0)
            self.assertAlmostEqual(res.sample_points[0].calc_x, 3.0, delta=0.5, msg=model.name)

    def test_all_models_count_and_families(self):
        self.assertGreaterEqual(len(AVAILABLE_MODELS), 40)
        names = [m.name for m in AVAILABLE_MODELS]
        self.assertEqual(len(names), len(set(names)), "存在重名模型")

    def test_curve_finder(self):
        xs = np.linspace(1, 10, 10)
        ys = 2 * xs ** 1.5  # 幂函数数据
        stds = make_points(xs, ys)
        entries = run_curve_finder(stds, [], get_all_models(), max_poly_order=4)
        self.assertGreater(len(entries), 0)
        best = entries[0]
        self.assertIsNotNone(best.result)
        self.assertGreaterEqual(best.r_squared, 0.99)
        # 排名按 R² 降序
        r2s = [e.r_squared for e in entries if e.result is not None]
        self.assertEqual(r2s, sorted(r2s, reverse=True))


class TestExpressionParser(unittest.TestCase):

    def test_param_detection(self):
        ev = UserModelEvaluator("a + b*exp(-c*x)")
        self.assertEqual(ev.param_names, ["a", "b", "c"])
        ev2 = UserModelEvaluator("a*(x<b) + c*(x>=b)")
        self.assertEqual(ev2.param_names, ["a", "b", "c"])

    def test_evaluate(self):
        ev = UserModelEvaluator("a + b*x")
        special = ev.compute_special_vars(np.array([1.0, 2.0]), np.array([3.0, 4.0]))
        out = ev.evaluate(np.array([1.0, 2.0]), {"a": 1.0, "b": 2.0}, special)
        np.testing.assert_allclose(out, [3.0, 5.0])

    def test_functions_and_constants(self):
        ev = UserModelEvaluator("a*sin(pi*x) + log10(b)")
        self.assertEqual(ev.param_names, ["a", "b"])
        special = ev.compute_special_vars(np.array([1.0]), np.array([1.0]))
        out = ev.evaluate(np.array([0.5]), {"a": 2.0, "b": 100.0}, special)
        np.testing.assert_allclose(out, [2.0 * np.sin(np.pi * 0.5) + 2.0])

    def test_special_vars(self):
        ev = UserModelEvaluator("avgx + stdy*2")
        self.assertEqual(ev.param_names, [])
        special = ev.compute_special_vars(np.array([1.0, 3.0]), np.array([2.0, 6.0]))
        out = ev.evaluate(np.array([0.0]), {}, special)
        np.testing.assert_allclose(out, [2.0 + 2.0 * 2.0])

    def test_unsafe_rejected(self):
        for bad in ["__import__('os')", "a.b", "x[0]", "a=1", "1;2", "os.system('x')"]:
            with self.assertRaises(ExpressionError, msg=bad):
                UserModelEvaluator(bad)

    def test_too_many_params(self):
        expr = " + ".join(f"{c}*x" for c in "abcdefghijklmnopqrst")
        with self.assertRaises(ExpressionError):
            UserModelEvaluator(expr)

    def test_user_model_fit(self):
        from math_engine.models_user import UserDefinedModelStrategy
        model = UserDefinedModelStrategy(name="自定义指数", expression="a*exp(b*x)")
        xs = np.linspace(0, 5, 10)
        ys = 2 * np.exp(0.4 * xs)
        res = model.fit_and_predict(make_points(xs, ys), [SamplePoint(sample_id="T", y=2 * np.exp(0.4 * 3))])
        self.assertTrue(res.success)
        self.assertGreater(res.r_squared, 0.99)
        self.assertAlmostEqual(res.sample_points[0].calc_x, 3.0, delta=0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
