# -*- coding: utf-8 -*-
"""
I/O 模块防崩清洗解析器 (IOManager)
负责 Excel/CSV/TXT 文件的物理提取与格点清洗。
"""

import os
import re
import csv
import logging
import pandas as pd
from typing import List

logger = logging.getLogger("IOManager")

class IOManagerError(Exception):
    pass

class IOManager:
    """
    纯静态 I/O 中枢，负责数据文件的清洗与格式解析。
    严格实施“全局预览优先，二次清洗提取”的安全机制。
    """

    @staticmethod
    def clean_cell(value: str) -> float:
        """
        二次清洗提取：
        移除非数字和非小数点字符，防止带有如 "OD:1.23" 的污染，遇空单元格或乱码安全置零。
        """
        if value is None:
            return 0.0
        val_str = str(value).strip()
        # 严格执行项目书正则：移除非数字和非小数点字符
        cleaned = re.sub(r'[^\d.]', '', val_str)
        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0 # 安全置零

    @staticmethod
    def read_to_grid(filepath: str) -> List[List[str]]:
        """
        全局预览优先：
        无论读取何种数据文件，优先将全部内容按行、按制表符/逗号拆解为二维字符串 List[List[str]]。
        """
        if not os.path.exists(filepath):
            raise IOManagerError("找不到指定的数据文件")

        ext = os.path.splitext(filepath)[1].lower()
        split_data: List[List[str]] = []

        try:
            if ext in {".xlsx", ".xls"}:
                # 借助 pandas 读取 Excel 文件的全部 Sheet 原貌
                df = pd.read_excel(filepath, header=None)
                df = df.fillna("")
                for row in df.values.tolist():
                    row_cells = []
                    for cell in row:
                        cell_str = str(cell).strip()
                        # 去除浮点数整数后缀的多余 .0
                        if cell_str.endswith(".0"):
                            cell_str = cell_str[:-2]
                        row_cells.append(cell_str)
                    split_data.append(row_cells)

            elif ext == ".csv":
                with open(filepath, "r", encoding="utf-8-sig", errors="replace") as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) == 1 and '\t' in row[0]:
                            split_data.append([item.strip(' \t\r\n"') for item in row[0].split('\t')])
                        else:
                            split_data.append([item.strip(' \t\r\n"') for item in row])

            else: # .txt 或其它文本文件
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    raw_lines = [line.rstrip("\n") for line in f.readlines()]
                for line in raw_lines:
                    # 如果行被引号整体包裹，先剥离双引号
                    cleaned_line = line.strip(' \t\r\n"')
                    # 使用制表符或多个空格作为切片依据
                    row_cells = re.split(r'\t+| {2,}', cleaned_line)
                    if not row_cells or (len(row_cells) == 1 and row_cells[0] == ""):
                        split_data.append([""])
                    else:
                        split_data.append([item.strip(' \t\r\n"') for item in row_cells])

            # 💡 二次兜底切分：防止由于引号包裹等原因导致 csv 读成一列
            cleaned_split_data: List[List[str]] = []
            for row in split_data:
                if len(row) == 1 and row[0] is not None:
                    cell_str = str(row[0]).strip()
                    if "\t" in cell_str:
                        cleaned_split_data.append(cell_str.split("\t"))
                    elif "," in cell_str:
                        cleaned_split_data.append(cell_str.split(","))
                    else:
                        row_cells = re.split(r' {2,}', cell_str)
                        cleaned_split_data.append(row_cells)
                else:
                    cleaned_split_data.append(row)
            split_data = cleaned_split_data

            return split_data

        except Exception as e:
            logger.error(f"全局预览解析文件失败：{e}", exc_info=True)
            raise IOManagerError(f"读取文件原貌数据失败：{e}")
