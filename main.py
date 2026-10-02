# -*- coding: utf-8 -*-
"""
ELISA-Calc-Pro 程序入口 (main.py) - V3.0
ELISA-Calc-Pro contributors
"""

import sys
import os
import ctypes
from ctypes import wintypes
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap
from ui.main_window import MainWindow


def resolve_icon_path() -> str:
    """获取图标文件路径，兼容开发环境和 PyInstaller 打包环境。"""
    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "assets", "logo.ico")


def set_windows_appusermodelid():
    """
    正确设置 Windows AppUserModelID，使任务栏将本程序识别为独立应用并显示自定义图标。
    必须在 QApplication 创建之前调用。
    """
    try:
        shell32 = ctypes.windll.shell32
        # 声明正确的函数签名：参数为 LPCWSTR，返回 HRESULT
        SetCurrentProcessExplicitAppUserModelID = shell32.SetCurrentProcessExplicitAppUserModelID
        SetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.c_wchar_p]
        SetCurrentProcessExplicitAppUserModelID.restype = wintypes.LONG
        myappid = 'ELISACalcPro.OpenSource.V3_0_0'
        SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass


def main():
    # 在创建 QApplication 之前设置 AppUserModelID
    set_windows_appusermodelid()

    # 高 DPI 适配
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    # 设置应用图标（同时设置到 app 和 window 上确保任务栏和标题栏都显示）
    app_icon_path = resolve_icon_path()
    icon = QIcon()
    if os.path.exists(app_icon_path):
        icon = QIcon(app_icon_path)
        # 如果 .ico 加载失败，尝试用同目录下的 .png
        if icon.isNull():
            png_path = app_icon_path.replace(".ico", ".png")
            if os.path.exists(png_path):
                icon = QIcon(QPixmap(png_path))

    if not icon.isNull():
        app.setWindowIcon(icon)

    app.setStyle("Fusion")

    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()

    # 主窗口显示后关闭启动画面
    try:
        import pyi_splash
        pyi_splash.close()
    except ImportError:
        pass

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
