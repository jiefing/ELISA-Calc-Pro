# -*- coding: utf-8 -*-
"""
图标和启动画面生成器 (build_icon.py)
使用 Matplotlib 和 Pillow 生成应用图标 (logo.ico) 和启动画面 (splash.png)。
"""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont


def generate_app_icon_and_splash():
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    # === 第一部分：生成应用图标 (logo.ico / logo.png) ===
    fig = plt.figure(figsize=(5.12, 5.12), dpi=100, facecolor='white')
    ax = fig.add_axes([0.15, 0.15, 0.76, 0.76])
    ax.set_facecolor('white')

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(4.5)
    ax.spines['bottom'].set_linewidth(4.5)
    ax.spines['left'].set_color('#212529')
    ax.spines['bottom'].set_color('#212529')
    ax.set_xticks([])
    ax.set_yticks([])

    # 绘制 4PL S 型曲线
    x = np.logspace(-1.8, 2.2, 200)
    a, d, c, b = 0.08, 2.95, 8.5, 1.45
    y = d + (a - d) / (1.0 + (x / c) ** b)
    ax.plot(np.log10(x), y, color='#1976D2', linewidth=8.5, zorder=3, solid_capstyle='round')

    # 标准点
    sample_indices = [15, 48, 85, 120, 155, 182]
    x_s = np.log10(x[sample_indices])
    y_s = y[sample_indices]
    ax.scatter(x_s, y_s, s=360, color='#D32F2F', edgecolor='#ffffff', linewidth=2.5, zorder=5)

    temp_png = os.path.join(out_dir, "temp_logo.png")
    plt.savefig(temp_png, format='png', dpi=100, transparent=False)
    plt.close(fig)

    # 加圆角处理
    img = Image.open(temp_png).convert("RGBA")
    size = img.size
    mask = Image.new('L', size, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle([0, 0, size[0], size[1]], radius=80, fill=255)
    output_img = Image.new('RGBA', size, (255, 255, 255, 0))
    output_img.paste(img, (0, 0), mask=mask)

    final_png = os.path.join(out_dir, "logo.png")
    final_ico = os.path.join(out_dir, "logo.ico")
    output_img.save(final_png, "PNG")
    icon_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    output_img.save(final_ico, format="ICO", sizes=icon_sizes)

    if os.path.exists(temp_png):
        os.remove(temp_png)
    print(f"图标已生成: {final_ico}")

    # === 第二部分：生成启动画面 (splash.png) ===
    splash_w, splash_h = 640, 380
    splash = Image.new("RGB", (splash_w, splash_h), color="#1565C0")
    draw = ImageDraw.Draw(splash)

    # 白色内容区
    draw.rectangle([4, 4, splash_w - 4, splash_h - 4], fill="#FFFFFF")

    # 左侧放置 logo
    resample_alg = getattr(Image, 'Resampling', Image).LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS
    logo_resized = output_img.resize((190, 190), resample=resample_alg)
    splash.paste(logo_resized, (28, 62), mask=logo_resized)

    # 查找可用中文字体
    f_path_found = None
    for fp in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyh.ttf",
               "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/arial.ttf"]:
        if os.path.exists(fp):
            f_path_found = fp
            break

    if f_path_found:
        font_title1 = ImageFont.truetype(f_path_found, 25)
        font_title2 = ImageFont.truetype(f_path_found, 22)
        font_sub = ImageFont.truetype(f_path_found, 16)
        font_author = ImageFont.truetype(f_path_found, 18)
        font_status = ImageFont.truetype(f_path_found, 14)
    else:
        font_title1 = font_title2 = font_sub = font_author = font_status = ImageFont.load_default()

    # 右侧文字
    text_x = 235
    draw.text((text_x, 62), "酶标仪数据计算系统", fill="#1A237E", font=font_title1)
    draw.text((text_x, 98), "ELISA-Calc-Pro  V3.0", fill="#1565C0", font=font_title2)

    draw.line([(text_x, 142), (splash_w - 35, 142)], fill="#90CAF9", width=2)

    draw.text((text_x, 160), "Open-source curve analysis", fill="#37474F", font=font_sub)
    draw.text((text_x, 195), "Open Source Edition", fill="#37474F", font=font_author)
    draw.text((text_x, 235), "多模型回归分析 / 标准曲线拟合", fill="#757575", font=font_status)

    # 底部加载提示
    draw.rectangle([28, 305, splash_w - 28, 345], fill="#F5F5F5", outline="#E0E0E0", width=1)
    draw.text((45, 316), "正在加载，请稍候...", fill="#616161", font=font_status)

    final_splash = os.path.join(out_dir, "splash_v3.png")
    splash.save(final_splash, "PNG")
    print(f"启动画面已生成: {final_splash}")


if __name__ == "__main__":
    generate_app_icon_and_splash()
