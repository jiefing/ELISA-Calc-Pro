# -*- coding: utf-8 -*-
"""
策略抽象基类模块 (strategy_base.py)
定义所有曲线拟合算法的主框架规则及计算异常定义。
"""

from abc import ABC, abstractmethod
from typing import List
from core.data_models import StandardPoint, SamplePoint, CurveFitResult


class FitEngineError(Exception):
    """
    数学引擎专门捕获和抛出的物理及计算错误，
    将被前端捕获并用于 UI QMessageBox 弹窗或控制台友好提示。
    """
    pass


class BaseFitStrategy(ABC):
    """
    非线性/线性归纳算法统一抽象策略基类。
    所有数学分析策略均须继承该基类并重构属性和 fit_and_predict 函数。
    """
    @property
    @abstractmethod
    def name(self) -> str:
        """模型显示完整名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """算法描述与适用实验场景简记"""
        pass

    @abstractmethod
    def fit_and_predict(self, std_points: List[StandardPoint], sample_points: List[SamplePoint]) -> CurveFitResult:
        """
        根据标准品序列执行模型参数估算，后反推样品计算结果。

        参数:
            std_points: 有效的标准品散点列表 [StandardPoint, ...]
            sample_points: 待测样的原始吸光度数据流 [SamplePoint, ...]

        返回:
            CurveFitResult 完整计算汇总结果实体
        """
        pass

    def validate_std_points_length(self, std_points: List[StandardPoint], min_len: int = 2):
        """
        公共检测辅助函数：效验标准品的最少散点数量限制
        """
        if len(std_points) < min_len:
            raise FitEngineError(f"[{self.name}] 拟合算法要求至少提供 {min_len} 个有效的标准品浓度点，当前仅有 {len(std_points)} 个有效点！")
# -*- coding: utf-8 -*-
"""
策略抽象基类模块 (strategy_base.py) - V3.0
定义所有曲线拟合算法的主框架规则及计算异常定义。
V3.0 新增：模型族分组、参数元数据、权重回归、标准误/AIC 等排名指标、
通用 Levenberg-Marquardt 拟合流程与数值反推引擎。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Callable, Tuple
import numpy as np
from scipy.optimize import curve_fit, brentq
from core.data_models import StandardPoint, SamplePoint, CurveFitResult


class FitEngineError(Exception):
    """
    数学引擎专门捕获和抛出的物理及计算错误，
    将被前端捕获并用于 UI QMessageBox 弹窗或控制台友好提示。
    """
    pass


# 权重模式字典：显示名 -> (x, y) -> 权重数组
WEIGHT_MODES = {
    "不加权": None,
    "1/y²": "1/y^2",
    "1/y": "1/y",
    "1/x²": "1/x^2",
    "1/x": "1/x",
    "1/标准差²": "1/std^2",
}


class BaseFitStrategy(ABC):
    """
    非线性/线性归纳算法统一抽象策略基类。
    所有数学分析策略均须继承该基类并重构属性和 fit_and_predict 函数。
    V3.0 起提供通用默认实现：子类只需定义 predict / guess_initial / param_names，
    即可获得完整的 LM 拟合、权重支持、指标计算与样本浓度反推能力。
    """

    # ---------------- 子类必须实现的元数据 ----------------
    @property
    @abstractmethod
    def name(self) -> str:
        """模型显示完整名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """算法描述与适用实验场景简记"""
        pass

    # ---------------- 子类可覆盖的元数据 ----------------
    @property
    def family(self) -> str:
        """模型族（用于下拉分组 / CurveFinder 勾选）"""
        return "通用模型"

    @property
    def param_names(self) -> List[str]:
        """参数名称有序列表，如 ['a', 'b', 'c']"""
        return []

    @property
    def needs_positive_x(self) -> bool:
        """该模型是否要求浓度 x 严格 > 0（对数/幂底模型）"""
        return False

    @property
    def is_interpolation(self) -> bool:
        """是否为插值型（穿过全部数据点，误差为 0）"""
        return False

    @property
    def supports_weight(self) -> bool:
        """是否支持权重回归"""
        return True

    @property
    def extrapolate(self) -> bool:
        """是否允许超出标准品范围外推（插值模型为 False）"""
        return True

    # ---------------- 数学模型（子类实现） ----------------
    def predict(self, x: np.ndarray, params: Dict[str, float]) -> np.ndarray:
        """根据参数计算模型值 f(x)。默认用 params 顺序调用 _equation。"""
        raise NotImplementedError

    def _equation(self, x, *args):
        """供 curve_fit 使用的裸方程（参数按 param_names 顺序展开）"""
        params = dict(zip(self.param_names, args))
        return self.predict(np.asarray(x, dtype=float), params)

    def guess_initial(self, x: np.ndarray, y: np.ndarray) -> List[float]:
        """
        自动初始猜测生成器（每个模型必须给出合理启发式初值）。
        返回与 param_names 等长的列表。
        """
        raise NotImplementedError

    # ---------------- 公共校验与工具 ----------------
    def validate_std_points_length(self, std_points: List[StandardPoint], min_len: int = 2):
        """公共检测辅助函数：效验标准品的最少散点数量限制"""
        if len(std_points) < min_len:
            raise FitEngineError(
                f"[{self.name}] 拟合算法要求至少提供 {min_len} 个有效的标准品浓度点，当前仅有 {len(std_points)} 个有效点！"
            )

    def _check_positive_x(self, std_points: List[StandardPoint]):
        if self.needs_positive_x:
            for sp in std_points:
                if sp.x <= 0:
                    raise FitEngineError("对数/4PL模型要求浓度必须大于0")

    def _extract_xy(self, std_points: List[StandardPoint]) -> Tuple[np.ndarray, np.ndarray]:
        x_arr = np.array([p.x for p in std_points], dtype=float)
        y_arr = np.array([p.y for p in std_points], dtype=float)
        return x_arr, y_arr

    def _weights_to_sigma(self, x: np.ndarray, y: np.ndarray, weights: Optional[str]) -> Optional[np.ndarray]:
        """
        将 CurveExpert 风格权重模式转换为 scipy.curve_fit 的 sigma（标准差）。
        权重 w = 1 / sigma²，故 sigma = 1 / sqrt(w)。
        """
        if not weights or weights == "none":
            return None
        with np.errstate(divide="ignore", invalid="ignore"):
            if weights == "1/y^2":
                w = 1.0 / (y ** 2)
            elif weights == "1/y":
                w = 1.0 / np.abs(y)
            elif weights == "1/x^2":
                w = 1.0 / (x ** 2)
            elif weights == "1/x":
                w = 1.0 / np.abs(x)
            elif weights == "1/std^2":
                s = np.std(y)
                w = np.full_like(y, 1.0 / (s * s) if s > 1e-12 else 1.0)
            else:
                return None
        w = np.nan_to_num(w, nan=0.0, posinf=0.0, neginf=0.0)
        w = np.clip(w, 1e-12, None)
        return 1.0 / np.sqrt(w)

    def _r_squared(self, y_arr: np.ndarray, y_pred: np.ndarray) -> float:
        ss_res = float(np.sum((y_arr - y_pred) ** 2))
        ss_tot = float(np.sum((y_arr - np.mean(y_arr)) ** 2))
        if ss_tot > 1e-12:
            return 1.0 - ss_res / ss_tot
        return 0.0 if ss_res > 1e-12 else 1.0

    def _standard_error(self, y_arr: np.ndarray, y_pred: np.ndarray, n_params: int) -> float:
        """回归标准误 se = sqrt(SS_res / (n - p))"""
        n = len(y_arr)
        dof = n - n_params
        if dof <= 0:
            return 0.0
        ss_res = float(np.sum((y_arr - y_pred) ** 2))
        return float(np.sqrt(ss_res / dof))

    def _aic(self, n: int, n_params: int, ss_res: float) -> float:
        """赤池信息准则（小样本修正）"""
        if n <= 0 or ss_res <= 0:
            return float("inf")
        aic = n * np.log(ss_res / n) + 2 * n_params
        k = n_params + 1
        if n - k - 1 > 0:
            aic += 2 * k * (k + 1) / (n - k - 1)
        return float(aic)

    # ---------------- 数值反推引擎 ----------------
    def solve_x(self, y_target: float, params: Dict[str, float], x_lo: float, x_hi: float,
                preferred_x: Optional[float] = None) -> Optional[float]:
        """
        数值反推 x = f^-1(y)：将 [x_lo, x_hi] 分段扫描符号变化，逐段二分求根。
        对非单调曲线（如正弦）可返回多个根，此时取最接近 preferred_x（标准品中位浓度）的根。
        若无任何根则返回 None（越界 / 无解）。
        """
        if not (x_hi > x_lo):
            return None

        def g(xv):
            return float(self.predict(np.asarray([xv], dtype=float), params)[0]) - y_target

        n_seg = 60
        xs = np.linspace(x_lo, x_hi, n_seg + 1)
        roots = []
        with np.errstate(all="ignore"):
            try:
                prev_x, prev_f = xs[0], g(xs[0])
                for i in range(1, n_seg + 1):
                    cur_x, cur_f = xs[i], g(xs[i])
                    if np.isnan(prev_f) or np.isnan(cur_f):
                        prev_x, prev_f = cur_x, cur_f
                        continue
                    if prev_f == 0.0:
                        roots.append(float(prev_x))
                    elif prev_f * cur_f < 0:
                        try:
                            root = brentq(g, prev_x, cur_x, xtol=1e-9, maxiter=200)
                            roots.append(float(root))
                        except Exception:
                            pass
                    prev_x, prev_f = cur_x, cur_f
            except Exception:
                return None

        if not roots:
            return None
        if preferred_x is None or len(roots) == 1:
            return roots[0]
        return min(roots, key=lambda r: abs(r - preferred_x))

    def _solve_samples(self, sample_points, params, x_arr, y_arr):
        """通用样本反推：数值求根，失败时按端点响应分类越界方向"""
        x_lo = float(np.min(x_arr))
        x_hi = float(np.max(x_arr))
        if self.extrapolate:
            span = x_hi - x_lo if x_hi > x_lo else 1.0
            if self.needs_positive_x:
                x_lo = max(x_lo * 0.5, 1e-9)
            else:
                x_lo -= span * 0.2
            x_hi += span * 0.2

        preferred_x = float(np.median(x_arr))
        res_points = []
        for sp in sample_points:
            root = self.solve_x(sp.y, params, x_lo, x_hi, preferred_x=preferred_x)
            if root is not None:
                calc_x = float(root)
            elif not self.extrapolate and (sp.y > float(np.max(y_arr)) + 1e-12 or sp.y < float(np.min(y_arr)) - 1e-12):
                calc_x = "越界 (插值模型不支持外推)"
            else:
                # 分类越界方向：密集采样求响应极值，方向按端点判断
                with np.errstate(all="ignore"):
                    try:
                        probe = np.linspace(x_lo, x_hi, 200)
                        probe_y = self.predict(probe, params)
                        edge = self.predict(np.asarray([x_lo, x_hi], dtype=float), params)
                    except Exception:
                        probe_y = np.array([np.nan])
                        edge = np.array([np.nan, np.nan])
                if np.any(np.isnan(probe_y)) or np.any(np.isnan(edge)):
                    calc_x = "无法解析"
                else:
                    y_min, y_max = float(np.min(probe_y)), float(np.max(probe_y))
                    f_lo, f_hi = float(edge[0]), float(edge[1])
                    if sp.y > y_max:
                        calc_x = ">上限" if f_hi > f_lo else "<下限"
                    elif sp.y < y_min:
                        calc_x = "<下限" if f_hi > f_lo else ">上限"
                    else:
                        calc_x = "无法解析"
            res_points.append(SamplePoint(sample_id=sp.sample_id, y=sp.y, calc_x=calc_x, row_idx=sp.row_idx))
        return res_points

    # ---------------- 通用默认拟合流程 ----------------
    def fit_and_predict(self, std_points: List[StandardPoint], sample_points: List[SamplePoint],
                        weights: Optional[str] = None, **kwargs) -> CurveFitResult:
        """
        通用默认实现：
        1. 校验点数与正 x 约束
        2. 自动初始猜测 + Levenberg-Marquardt 拟合（支持权重）
        3. 计算 R² / 标准误 / AIC
        4. 生成平滑渲染曲线
        5. 数值反推样本浓度
        """
        n_params = len(self.param_names)
        self.validate_std_points_length(std_points, min_len=n_params + 1)
        self._check_positive_x(std_points)

        x_arr, y_arr = self._extract_xy(std_points)
        sigma = self._weights_to_sigma(x_arr, y_arr, weights)
        p0 = self.guess_initial(x_arr, y_arr)
        if len(p0) != n_params:
            raise FitEngineError(f"[{self.name}] 初始猜测生成异常：期望 {n_params} 个参数，实际 {len(p0)} 个。")

        with np.errstate(all="ignore"):
            try:
                popt, _ = curve_fit(
                    self._equation, x_arr, y_arr, p0=p0,
                    sigma=sigma, method="lm", maxfev=30000
                )
            except RuntimeError:
                raise FitEngineError("无法收敛，请检查数据趋势。这有可能来自于实验散点发散失衡或者严重欠离轴无生理学单调对应规律！")
            except ValueError as ve:
                raise FitEngineError(f"拟合参数越界或数据无效：\n{ve}")
            except Exception as e:
                raise FitEngineError(f"Levenberg-Marquardt 拟合异常终了：\n{e}")

        params = dict(zip(self.param_names, [float(v) for v in popt]))
        y_pred = self.predict(x_arr, params)
        r_squared = self._r_squared(y_arr, y_pred)
        se = self._standard_error(y_arr, y_pred, n_params)
        aic = self._aic(len(y_arr), n_params, float(np.sum((y_arr - y_pred) ** 2)))

        # 平滑渲染曲线（按 x 分布采样 200 点）
        span = float(np.max(x_arr) - np.min(x_arr))
        if self.needs_positive_x:
            lo = max(float(np.min(x_arr)) * 0.5, float(np.min(x_arr)) - span * 0.2)
            hi = float(np.max(x_arr)) * 1.5
            curve_x = np.geomspace(max(lo, 1e-12), hi, 200) if lo > 0 else np.linspace(lo, hi, 200)
        else:
            curve_x = np.linspace(float(np.min(x_arr)) - span * 0.05, float(np.max(x_arr)) + span * 0.05, 200)
        curve_y = self.predict(curve_x, params)

        res_samples = self._solve_samples(sample_points, params, x_arr, y_arr)

        return CurveFitResult(
            model_name=self.name,
            success=True,
            equation_str=self.format_equation(params),
            parameters=params,
            r_squared=r_squared,
            standard_error=se,
            aic=aic,
            family=self.family,
            param_names=list(self.param_names),
            is_log_x=self.needs_positive_x,
            std_points=std_points,
            sample_points=res_samples,
            curve_x=curve_x,
            curve_y=curve_y,
            predict_fn=lambda xs, prm=params: self.predict(np.asarray(xs, dtype=float), prm),
            x_range=(float(np.min(x_arr)), float(np.max(x_arr))),
        )

    def format_equation(self, params: Dict[str, float]) -> str:
        """生成方程字符串（子类可覆盖以获得更美观的排版）"""
        return f"y = f(x; {', '.join(f'{k}={v:.4g}' for k, v in params.items())})"

    # ---------------- 分析工具（微分/积分/弧长） ----------------
    def derivative(self, x_val: float, params: Dict[str, float], h: float = 1e-5) -> float:
        """中心差分数值微分"""
        xv = np.asarray([x_val - h, x_val + h], dtype=float)
        yv = self.predict(xv, params)
        return float((yv[1] - yv[0]) / (2 * h))

    def integrate(self, a: float, b: float, params: Dict[str, float], n: int = 4000) -> float:
        """Simpson 数值积分"""
        xs = np.linspace(a, b, n * 2 + 1)
        ys = self.predict(xs, params)
        h = (b - a) / (2 * n)
        return float(h / 3.0 * (ys[0] + ys[-1] + 4 * np.sum(ys[1::2]) + 2 * np.sum(ys[2:-1:2])))

    def arclength(self, a: float, b: float, params: Dict[str, float], n: int = 2000) -> float:
        """弧长 ∫ sqrt(1 + f'(x)²) dx，用采样折线逼近"""
        xs = np.linspace(a, b, n)
        ys = self.predict(xs, params)
        return float(np.sum(np.hypot(np.diff(xs), np.diff(ys))))
