"""桌面界面（M5）：PySide6 五页签，只消费 CLI/引擎层的公开 API。

纪律（口径 D08/K41）：界面不实现第二套判定、第二套渲染、第二套查表。每个页签显示的
正文都是命令面用的那一个渲染函数的输出，结构化表格只是同一份 payload 的另一种视图。

PySide6 是可选 extras：本包在 `sdc gui` 或 GUI exe 里才被导入，CLI 的其它命令都不碰它。
"""

from .app import build_main_window, capture, run

__all__ = ["build_main_window", "capture", "run"]
