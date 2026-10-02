# ELISA-Calc-Pro

用于标准曲线拟合和酶标仪样本浓度计算的桌面工具，使用 Python、PyQt5、NumPy、SciPy 和 Matplotlib。

## 功能

- 从 Excel/WPS 复制粘贴标准品浓度、OD 和样本数据。
- 40 个内置回归/插值模型，包括直线、多项式、4PL、Logit-Log 等。
- 模型自动搜索与排名、自定义数学表达式。
- 复孔处理、空白扣除、稀释倍数设置和曲线展示。
- 样本结果 CSV/XLSX、完整 Excel 报告、TXT 和图像导出。

## Windows 免安装版

从 [GitHub Releases](https://github.com/jiefing/ELISA-Calc-Pro/releases) 下载 Windows x64 ZIP，完整解压后运行 `ELISA-Calc-Pro.exe`。请保留同目录的 `_internal` 文件夹，不要只复制 EXE。包内不需要另行安装 Python。

## 源码安装与运行

主要面向 Windows。建议创建独立环境（示例为 Python 3.12）：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

首次运行前可生成图标和启动画面：

```powershell
.venv\Scripts\python.exe build_icon.py
```

标准品表粘贴两列：浓度 X、吸光度 OD Y；样本表填写样本编号和 OD，再选择模型进行计算。4PL 要求标准品浓度大于 0。

## 测试

```powershell
.venv\Scripts\python.exe -m unittest test_math_engine test_models_v3 test_strategies -v
```

首次公开版本在本地通过现有 24 项测试，并在 Python 3.9 / Qt 5.15.2 下通过主窗口离屏加载检查。测试覆盖不完整，实际实验使用前请用已知样本核对结果。详见 [已知问题](docs/KNOWN_ISSUES.md)。

## 打包

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.venv\Scripts\python.exe build_pack.py
```

构建脚本使用当前解释器，在 `dist/ELISA-Calc-Pro/` 生成文件夹形式的 Windows 程序，不自动结束运行中的程序，也不清空整个 dist 目录。发布包使用此处脱敏源码构建，不沿用历史 EXE。

发布构建使用 Python 3.12 x64，建议把构建虚拟环境放在纯英文路径，避免 Qt 5 插件路径识别问题。复现本次依赖环境可安装 `requirements-release.txt`，构建后运行 `python package_release.py` 生成 ZIP 和 SHA-256 校验文件。

## 代码结构

- `main.py`、`ui/`：当前 V3 界面与入口。
- `core/`：数据结构、剪贴板、表达式解析。
- `math_engine/`：拟合、反推与模型排名。
- `controllers/`、`models/`、`strategies/`、`views/`：保留的旧孔板工作流及相关测试。
- `generate_test_data.py`：生成模拟孔板数据；该格式用于旧工作流，不是当前两列表格的直接导入格式。

自定义模型存储在 `user_models.json`：源码运行时位于项目根目录，打包运行时位于 EXE 同目录。请自行备份，此文件默认不提交。

## 隐私与贡献

仓库不包含历史截图、真实实验数据、原发布程序、内部工作记录或参考软件安装包。提交问题或改动时，请使用模拟数据，并移除报告中的样本身份、姓名、学校和个人路径。欢迎通过 Issues 和 Pull Requests 报告可复现问题。

## 许可证

项目代码以 [GNU GPL v3.0](LICENSE) 发布（GPL-3.0-only）。第三方依赖保留各自许可证，详见 [依赖说明](THIRD_PARTY_NOTICES.md)。
