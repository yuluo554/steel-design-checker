"""`sdc-gui.exe` 的入口脚本（PyInstaller Analysis 的入口，窗口版 console=False）。

`sdc.gui.app.run()` 自己按 `find_data_dir` 的五分支优先级找数据目录（打包态命中
`sys._MEIPASS/data` 或 exe 同侧的 `_internal/data`），找不到时把原因写 stderr 并返回 2。
"""

import sys

from sdc.gui.app import run

if __name__ == "__main__":
    sys.exit(run())
