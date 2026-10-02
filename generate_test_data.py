# -*- coding: utf-8 -*-
"""
生成模拟酶标仪测试数据文件 (CSV/XLSX)
用于测试“基础扣减”、“4PL ELISA”和“细胞活力”功能。
"""

import os
import pandas as pd
import numpy as np


def generate_test_data():
    print("开始生成测试数据文件...")

    # 1. 模拟 96 孔板 (8行 x 12列) 的原始 OD 读数
    # 行：A-H，列：1-12
    # 我们为标曲设置一些已知的 OD 值（随梯度降低）
    # 为 Blank 设定一些背景噪音 OD 值（约 0.05）
    # 为 Sample 设定一些待测 OD 值

    rows = list("ABCDEFGH")
    cols = list(range(1, 13))

    # 默认空矩阵
    data = np.zeros((8, 12))

    # 模拟真实读数
    # A1-H1: Standard 标曲孔（从高浓度到低浓度对应的 OD 值为 2.5 下降到 0.1 左右）
    # A2-H2: 另一列 Standard 重复孔
    std_curves = [2.45, 1.88, 1.25, 0.76, 0.42, 0.22, 0.12, 0.07]
    for r_idx, r in enumerate(rows):
        data[r_idx, 0] = std_curves[r_idx] + np.random.normal(0, 0.01) # 列1
        data[r_idx, 1] = std_curves[r_idx] + np.random.normal(0, 0.01) # 列2（重复孔）

    # A12-H12: Blank 空白孔 (背景值约 0.045 - 0.055)
    for r_idx in range(8):
        data[r_idx, 11] = 0.05 + np.random.normal(0, 0.003)

    # 其他孔 A3-H11: 样品孔 (Sample) 或 阴性对照 (Control)
    # 我们在列 3, 4 放 Sample；列 5 放 Control (CCK-8 阴性对照，活力约 100%，即 OD 约 1.2)
    # 样品孔 (列 3, 4) 是药筛处理组，OD 随行在 0.2 到 1.1 之间波动
    for r_idx in range(8):
        # Control 孔（有细胞未加药，OD 设定在 1.1 到 1.3 之间）
        data[r_idx, 4] = 1.2 + np.random.normal(0, 0.03)

        # Sample 药筛组，比如加药浓度逐渐升高，存活率从 95% 下降到 15%
        # 对应 OD 从 1.15 下降到 0.20
        viabilities = [0.95, 0.85, 0.70, 0.55, 0.40, 0.30, 0.20, 0.12]
        base_od = viabilities[r_idx] * 1.2 + 0.05
        data[r_idx, 2] = base_od + np.random.normal(0, 0.02) # Sample 重复1
        data[r_idx, 3] = base_od + np.random.normal(0, 0.02) # Sample 重复2

        # 其他未用孔也填一些背景或留空，这里我们填一些 0.04 - 0.08 的背景
        for c_idx in [5, 6, 7, 8, 9, 10]:
            data[r_idx, c_idx] = 0.06 + np.random.normal(0, 0.01)

    # 2. 将数据转换为 DataFrame 格式并输出
    df = pd.DataFrame(data, index=rows, columns=cols)

    # 导出为 Excel 格式 (.xlsx)
    xlsx_path = "模拟酶标仪原始数据.xlsx"
    df.to_excel(xlsx_path, sheet_name="Plate1")
    print(f"已生成 Excel 测试数据：{xlsx_path}")

    # 导出为 CSV 格式 (.csv)
    csv_path = "模拟酶标仪原始数据.csv"
    df.to_csv(csv_path)
    print(f"已生成 CSV 测试数据：{csv_path}")


if __name__ == "__main__":
    generate_test_data()
