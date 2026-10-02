# -*- coding: utf-8 -*-
"""
数据实体模块 (data_models.py)
定义标准品数据点、样口数据点，以及曲线拟合结果实体。
采用普通类/ dataclass 构建，确保 Python 3.8+ 环境高度可靠。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Union, Optional, Callable
import numpy as np


@dataclass
class StandardPoint:
    """
    标准品数据点实体
    x: 浓度 (X)
    y: 吸光度 OD (Y)
    row_idx: 来源于表中的所在行号（可选）
    """
    x: float
    y: float
    row_idx: int = -1

    def __repr__(self) -> str:
        return f"StandardPoint(X={self.x}, Y={self.y})"


@dataclass
class SamplePoint:
    """
    样口数据点实体
    sample_id: 样口编号 (可选)
    y: 吸光度 OD (Y)
    calc_x: 反推得到的浓度 X（可是 float 或 ">上限"/"<下限"/"无法解析"/"0.0" 等字符串）
    row_idx: 来源于表中的所在行号（可选）
    """
    y: float
    sample_id: str = ""
    calc_x: Union[float, str] = ""
    row_idx: int = -1

    def __repr__(self) -> str:
        return f"SamplePoint(ID='{self.sample_id}', Y={self.y}, calc_X={self.calc_x})"


@dataclass
class CurveFitResult:
    """
    算法拟合分析结果与参数包
    V3.0 新增：标准误 / AIC / 模型族 / 参数名 / 求值函数 / x 范围，
    供排名面板与分析工具（求值、反推、微分、积分、弧长）使用。
    """
    model_name: str = ""                         # 当前采用的拟合策略算法名
    success: bool = False                        # 是否收敛及执行成功
    error_message: str = ""                      # 若异常或发散情况下的错误提醒语句

    equation_str: str = ""                       # 完整的拟合方程式显示格式
    parameters: Dict[str, float] = field(default_factory=dict)  # 参数矩阵如 {'a': x, 'b': y...} 或 {'k': k, 'b': b}
    r_squared: float = 0.0                       # 判定系数 R² (拟合优度)
    standard_error: float = 0.0                   # 回归标准误 se = sqrt(SS_res/(n-p))
    aic: float = float("inf")                    # 赤池信息准则（越小越好）
    family: str = "通用模型"                      # 模型族（分组显示）
    param_names: List[str] = field(default_factory=list)  # 参数名列表
    predict_fn: Optional[Callable] = None         # 求值函数 f(x) -> y（分析工具用）
    x_range: tuple = ()                           # 标准品 x 范围 (min, max)

    is_log_x: bool = False                       # 是否要求以 Log10 对数坐标系渲染 X 轴

    # 可视化渲染点位映射
    std_points: List[StandardPoint] = field(default_factory=list)      # 标准品数据列表
    sample_points: List[SamplePoint] = field(default_factory=list)    # 反推成功/尝试后样品点完整集

    # 平滑渲染专属曲线上样散点（建议生成 200 个分层点以便绘制一条丝般滑顺的完美黑曲线）
    curve_x: np.ndarray = field(default_factory=lambda: np.array([]))
    curve_y: np.ndarray = field(default_factory=lambda: np.array([]))
    preprocessing: Dict[str, Any] = field(default_factory=dict)

    def generate_report_text(self) -> str:
        """
        生成规范化的统计参数输出报告，提供渲染于右下部 QTextEdit 面板
        """
        if not self.success:
            return f"【模型拟合失败】: {self.model_name}\n\n错误原因及建议：\n{self.error_message}\n\n建议排查输入标准品数据是否满足收敛条件（例如 4PL 及对数模型需 x > 0）及具备正常的单调渐近特性。"

        lines = [
            f"=========================================",
            f"【回归分析简报】 {self.model_name}",
            f"=========================================",
            f"· 模型族：{self.family}",
            f"· 回归方程模型：\n   {self.equation_str}\n",
            f"· 拟合参数说明："
        ]

        for p_name, p_val in self.parameters.items():
            if isinstance(p_val, float):
                lines.append(f"   - 参数 [{p_name}]:  {p_val:.6g}")
            else:
                lines.append(f"   - 参数 [{p_name}]:  {p_val}")

        lines.append(f"\n· 决定系数 (R²)：\n   R² = {self.r_squared:.6f}")

        if self.standard_error:
            lines.append(f"\n· 回归标准误 (SE)：\n   SE = {self.standard_error:.6g}")
        if self.aic != float("inf") and self.aic != float("-inf"):
            lines.append(f"\n· 赤池信息准则 (AIC)：\n   AIC = {self.aic:.4g}（越小越好）")

        if self.r_squared < 0.95:
            lines.append("   ⚠️ [提示] R² < 0.95，当前拟合回归度相对偏低，建议检查标准品复孔离群点或尝试改换计算模型。")
        else:
            lines.append("   ✔ [评估] R² >= 0.95，曲线回归匹配良好。")

        lines.append("=========================================\n")
        return "\n".join(lines)
