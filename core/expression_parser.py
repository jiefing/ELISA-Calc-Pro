# -*- coding: utf-8 -*-
"""
自定义模型表达式解析器 (expression_parser.py) - V3.0
忠实移植 CurveExpert 1.4 的用户自定义模型语言：
  - 运算符: + - * / ^ 以及比较运算符 < > <= >= == !=（结果为 0/1，可构造分段模型）
  - 特殊变量: pi, avgx, avgy, stdx, stdy, minx, miny, maxx, maxy, x
  - 函数库: abs, fact, sqrt, exp, log, log10, sin, cos, tan, asin, acos, atan,
            sinh, cosh, tanh, ceil, floor, j0, j1, y0, y1
  - 参数: 除保留字外的单个字母（最多 19 个），如 a, b, c
使用 Python AST 白名单校验，禁止任何属性访问/下标/赋值等危险语法。
"""

import ast
import numpy as np
from scipy.special import j0, j1, y0, y1, factorial


# 内置函数库（与 CurveExpert 完全一致）
FUNCTION_LIB = {
    "abs": np.abs,
    "fact": factorial,
    "sqrt": np.sqrt,
    "exp": np.exp,
    "log": np.log,
    "log10": np.log10,
    "sin": np.sin,
    "cos": np.cos,
    "tan": np.tan,
    "asin": np.arcsin,
    "acos": np.arccos,
    "atan": np.arctan,
    "sinh": np.sinh,
    "cosh": np.cosh,
    "tanh": np.tanh,
    "ceil": np.ceil,
    "floor": np.floor,
    "j0": j0,
    "j1": j1,
    "y0": y0,
    "y1": y1,
}

# 特殊变量（数据统计量 + 自变量）
SPECIAL_VARS = ["pi", "avgx", "avgy", "stdx", "stdy", "minx", "miny", "maxx", "maxy"]
MAX_PARAMS = 19

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_ALLOWED_CMPOPS = (ast.Lt, ast.Gt, ast.LtE, ast.GtE, ast.Eq, ast.NotEq)
_ALLOWED_UNARY = (ast.UAdd, ast.USub)


class ExpressionError(Exception):
    """表达式语法或语义错误"""
    pass


def _ordered_walk(node):
    """按源码书写顺序遍历 AST（ast.walk 是 BFS 顺序，不保证参数检测顺序）"""
    yield node
    for _field, value in ast.iter_fields(node):
        if isinstance(value, list):
            for item in value:
                if isinstance(item, ast.AST):
                    yield from _ordered_walk(item)
        elif isinstance(value, ast.AST):
            yield from _ordered_walk(value)


class UserModelEvaluator:
    """
    编译并执行用户自定义模型表达式。
    evaluate(x, params, special) -> np.ndarray
    """

    def __init__(self, expression: str):
        self.raw_expression = expression
        self.param_names: list = []
        self._namespace = {}
        self._compile(expression)

    def _compile(self, expression: str):
        text = expression.strip()
        if not text:
            raise ExpressionError("表达式不能为空。")
        try:
            tree = ast.parse(text, mode="eval")
        except SyntaxError as e:
            raise ExpressionError(f"表达式语法错误：{e.msg}（第 {e.lineno} 行）")

        param_names = []
        for node in _ordered_walk(tree):
            # 运算符/一元符/比较符/逻辑符/上下文节点：合法性已在其父节点处校验，直接跳过
            if isinstance(node, (ast.operator, ast.unaryop, ast.cmpop, ast.boolop, ast.expr_context)):
                continue
            if isinstance(node, ast.BinOp):
                if not isinstance(node.op, _ALLOWED_BINOPS):
                    raise ExpressionError(f"不支持的二元运算符：{type(node.op).__name__}")
            elif isinstance(node, ast.UnaryOp):
                if not isinstance(node.op, _ALLOWED_UNARY):
                    raise ExpressionError(f"不支持的一元运算符：{type(node.op).__name__}")
            elif isinstance(node, ast.Compare):
                if len(node.ops) != 1 or len(node.comparators) != 1:
                    raise ExpressionError("不支持链式比较，请用逻辑连接符组合。")
                if not isinstance(node.ops[0], _ALLOWED_CMPOPS):
                    raise ExpressionError("仅支持 < > <= >= == != 比较运算符。")
            elif isinstance(node, ast.BoolOp):
                if not isinstance(node.op, (ast.And, ast.Or)):
                    raise ExpressionError("仅支持 and / or 逻辑运算。")
            elif isinstance(node, ast.IfExp):
                pass  # 三目表达式 a if cond else b
            elif isinstance(node, ast.Call):
                if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTION_LIB:
                    raise ExpressionError("仅允许调用内置函数库中的函数。")
                if node.keywords:
                    raise ExpressionError("函数调用不支持关键字参数。")
            elif isinstance(node, ast.Name):
                name = node.id
                if name in FUNCTION_LIB or name in SPECIAL_VARS or name == "x":
                    continue
                if len(name) != 1 or not name.isalpha():
                    raise ExpressionError(
                        f"未知标识符 '{name}'：参数必须是单个字母（如 a、b、c），"
                        f"或使用内置函数/特殊变量。"
                    )
                if name not in param_names:
                    param_names.append(name)
            elif isinstance(node, ast.Constant):
                if not isinstance(node.value, (int, float)):
                    raise ExpressionError("仅支持数值常量。")
            elif isinstance(node, ast.Expression):
                continue
            else:
                raise ExpressionError(f"表达式包含不允许的语法元素：{type(node).__name__}")

        if len(param_names) > MAX_PARAMS:
            raise ExpressionError(f"参数数量超过上限（{MAX_PARAMS} 个），当前检测到 {len(param_names)} 个。")

        self.param_names = param_names
        try:
            self._code = compile(tree, "<user_model>", "eval")
        except Exception as e:
            raise ExpressionError(f"表达式编译失败：{e}")

    def evaluate(self, x: np.ndarray, params: dict, special: dict) -> np.ndarray:
        """在给定 x、参数值、数据统计量命名空间下求值"""
        namespace = dict(FUNCTION_LIB)
        namespace["x"] = np.asarray(x, dtype=float)
        namespace.update({k: float(v) for k, v in special.items()})
        namespace.update({k: float(v) for k, v in params.items()})
        try:
            result = eval(self._code, {"__builtins__": {}}, namespace)
            return np.asarray(result, dtype=float)
        except ZeroDivisionError:
            raise ExpressionError("表达式求值出现除零错误，请检查模型定义。")
        except FloatingPointError:
            raise ExpressionError("表达式求值出现浮点溢出，请检查模型定义。")
        except Exception as e:
            raise ExpressionError(f"表达式求值失败：{e}")

    def compute_special_vars(self, x: np.ndarray, y: np.ndarray) -> dict:
        """根据数据计算特殊变量值（avgx/avgy/stdx/stdy/min/max）"""
        xf = np.asarray(x, dtype=float)
        yf = np.asarray(y, dtype=float)
        return {
            "pi": float(np.pi),
            "avgx": float(np.mean(xf)),
            "avgy": float(np.mean(yf)),
            "stdx": float(np.std(xf)),
            "stdy": float(np.std(yf)),
            "minx": float(np.min(xf)),
            "miny": float(np.min(yf)),
            "maxx": float(np.max(xf)),
            "maxy": float(np.max(yf)),
        }


def validate_expression(expression: str):
    """仅校验表达式合法性，返回参数名列表；非法时抛 ExpressionError"""
    return UserModelEvaluator(expression).param_names
