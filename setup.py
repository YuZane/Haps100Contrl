from setuptools import setup
import sys
from cx_Freeze import setup, Executable

# 打包配置
build_exe_options = {
    "packages": ["os", "tkinter", "json", "subprocess", "threading", "time", "tempfile", "queue"],
    "includes": [],
    "include_files": ["haps_control_default.tcl", "haps_config.json"],  # 包含需要打包的文件
    "excludes": [],
    "optimize": 2
}

# 基础设置
base = None
if sys.platform == "win32":
    base = "Win32GUI"  # 不显示控制台窗口

# 执行配置
executables = [
    Executable(
        "haps_automation_gui.py",
        base=base,
        target_name="HAPSAutomation.exe",
        icon=None  # 可以指定图标文件，如 "app_icon.ico"
    )
]

setup(
    name="HAPSAutomation",
    version="1.0",
    description="HAPS自动化控制工具",
    options={"build_exe": build_exe_options},
    executables=executables
)
    