"""Build the public application with the current Python interpreter."""
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parent
    subprocess.run([sys.executable, str(root / "build_icon.py")], cwd=root, check=True)
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--onedir", "--windowed",
        "--name=ELISA-Calc-Pro", "--icon=assets/logo.ico",
        "--add-data=assets;assets", "--hidden-import=openpyxl",
        "--hidden-import=matplotlib.backends.backend_qt5agg",
        "--distpath=dist", "--workpath=build", "--specpath=build",
        "main.py",
    ], cwd=root, check=True)


if __name__ == "__main__":
    main()
