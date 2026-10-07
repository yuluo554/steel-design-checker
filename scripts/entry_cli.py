"""`sdc-cli.exe` 的入口脚本（PyInstaller Analysis 的入口，控制台版）。

为什么不直接用 `src/sdc/__main__.py`：那是 `python -m sdc` 的相对导入入口，被 PyInstaller
当独立脚本跑时没有包上下文。这里薄薄一层，进的是**同一个** `sdc.cli.main` —— 打包版与
`python -m sdc` 因此不可能有两种行为（口径 D08），干净环境验证跑的就是这条命令面。
"""

import sys

from sdc.cli import main

if __name__ == "__main__":
    sys.exit(main())
