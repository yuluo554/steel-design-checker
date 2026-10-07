# -*- mode: utf-8 -*-
"""PyInstaller onedir 双 exe（plan/03 §一 与 §七）。

- `sdc-cli.exe`：console=True，入口就是 `sdc.cli.main`，与 `python -m sdc` 同一命令面；
  它也是 GUI 在打包版里的解析子进程通路（口径 K45）。**排除 PySide6**：界面依赖不许漏进
  控制台包，`sdc gui` 在这个 exe 里会老实报"桌面界面不可用"。
- `sdc-gui.exe`：console=False，五页签界面，只调命令面公开 API（口径 D08/K41）。

两个包各带一份 `data/`（白名单见 `scripts/bundle_rules.py`），构建后由
`scripts/verify_dist.py` 做红线断言（禁区成分 + 内嵌数据逐份对账，任一违反 exit 1）。

坑位实录：`.gitignore` 的 `*.spec` 会把这个文件吞掉，靠 `!sdc.spec` 例外入库；spec 里的
相对路径解析到 SPECPATH 而不是 CWD，所以下面一律用绝对路径；PyInstaller 没有 --workers。
"""

import os
import sys

ROOT = os.path.abspath(SPECPATH)
SRC = os.path.join(ROOT, "src")
DATA_DIR = os.path.join(ROOT, "data")

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from bundle_rules import data_pairs  # noqa: E402

DATAS = data_pairs(DATA_DIR)

# 两个包都不该出现的重依赖（numpy/scipy/faiss/网络库/python-docx 都在禁止事项里）
COMMON_EXCLUDES = [
    "PySide2", "tkinter", "numpy", "scipy", "pandas", "matplotlib", "faiss",
    "docx", "python_docx", "requests", "urllib3", "pdfplumber", "pypdf", "torch",
    "pytest", "setuptools", "pip",
]

# ---------------------------------------------------------------------------
# 控制台版：sdc-cli.exe
# ---------------------------------------------------------------------------
a_cli = Analysis(
    [os.path.join(ROOT, "scripts", "entry_cli.py")],
    pathex=[SRC],
    binaries=[],
    datas=DATAS,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 界面是 extras：CLI 包不背 PySide6，也不该背
    excludes=COMMON_EXCLUDES + ["PySide6", "shiboken6", "sdc.gui"],
    noarchive=False,
)
pyz_cli = PYZ(a_cli.pure)
exe_cli = EXE(
    pyz_cli,
    a_cli.scripts,
    [],
    exclude_binaries=True,
    name="sdc-cli",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)
coll_cli = COLLECT(exe_cli, a_cli.binaries, a_cli.zipfiles, a_cli.datas,
                   strip=False, upx=False, name="sdc-cli")

# ---------------------------------------------------------------------------
# 窗口版：sdc-gui.exe
# ---------------------------------------------------------------------------
a_gui = Analysis(
    [os.path.join(ROOT, "scripts", "entry_gui.py")],
    pathex=[SRC],
    binaries=[],
    datas=DATAS,
    hiddenimports=["PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=COMMON_EXCLUDES,
    noarchive=False,
)
pyz_gui = PYZ(a_gui.pure)
exe_gui = EXE(
    pyz_gui,
    a_gui.scripts,
    [],
    exclude_binaries=True,
    name="sdc-gui",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
coll_gui = COLLECT(exe_gui, a_gui.binaries, a_gui.zipfiles, a_gui.datas,
                   strip=False, upx=False, name="sdc-gui")
