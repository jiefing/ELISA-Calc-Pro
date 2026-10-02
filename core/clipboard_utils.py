# -*- coding: utf-8 -*-
"""
剪贴板及数据清洗交互模块 (clipboard_utils.py)
对和 Office (Excel/WPS) / 文本间复杂的复制粘贴与空白/隐藏非标准回车、不可见制表符做彻底防错解析清理！
"""

import re
from typing import List, Tuple, Any


def parse_clipboard_text(text: str) -> List[List[str]]:
    """
    解析来自 Excel / WPS / 自定义剪贴板里传出来的表格文本。
    多列间往往由 `\t` 分隔，各行往往是由 `\r\n` / `\r` / `\n` 进行间隔。
    返回结构: [ ['cell_row1_col1', 'cell_row1_col2', ...], ['cell_row2_col1', ...] ]
    """
    if not text or not text.strip():
        return []

    # 替换各种可能的平台特异换行符
    normalized = re.sub(r'\r\n|\r|\n', '\n', text.strip())
    raw_rows = normalized.split('\n')

    parsed_grid = []
    for r in raw_rows:
        # 使用制表符进行多字段切词；如纯单一字元直接成为长度一数组
        cells = r.split('\t')
        # 去掉任何收尾不可见的空白垃圾或隐蔽字符
        cleaned_cells = [c.strip() for c in cells]
        parsed_grid.append(cleaned_cells)

    return parsed_grid


def format_to_clipboard_text(grid_data: List[List[Any]]) -> str:
    """
    将 QTableWidget 或后台矩阵数据组合还原成 Excel / WPS 标准剪贴板字符串。
    用 `\\t` 连接同行的各主元，以 `\\r\\n` 作为行的结尾。
    """
    if not grid_data:
        return ""

    rows = []
    for row in grid_data:
        str_row = [str(item) if item is not None else "" for item in row]
        rows.append("\t".join(str_row))

    return "\r\n".join(rows) + "\r\n"


def clean_float_array(raw_array: List[str]) -> Tuple[List[float], List[int]]:
    """
    对从界面表格获取的某列字符串进行数据清洗：
    - 忽略和截流各种回车换行或空白占位符 ('', ' ', '\\t')
    - 抛弃或拦截非数学性非标符号干扰并提报索引，提取合规有效的真实 float 数据流

    返回：
      float_list: 有效浮点数值完整有序清单
      valid_indices:  有效行所在原输入的位置编号（用以和 ID 列同步或回贴反馈计算位置）
    """
    float_list = []
    valid_indices = []

    for idx, val in enumerate(raw_array):
        if not isinstance(val, str):
            val = str(val)
        val = val.strip()
        if val == "" or val.lower() in ["nan", "none", "null"]:
            continue
        try:
            num = float(val)
            float_list.append(num)
            valid_indices.append(idx)
        except ValueError:
            # 如该字段不是合规数字（例如文字行头部标签、特殊注释），则予以跳过或忽视
            continue

    return float_list, valid_indices
