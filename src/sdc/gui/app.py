"""主窗口：五个页签，全部只消费命令面的公开 API。

页签顺序与 plan/03 §六 一致：①验算台 ②设计说明核查 ③通用规范检查单 ④报告导出
⑤知识库与状态。免责声明常驻窗口顶部与状态栏（plan/03 §三.5），不是弹窗——
本页面的测试批跑在 offscreen 平台上，任何模态框都会把它挂死。

`run()` 是给 GUI exe 与 `sdc gui` 用的入口；测试用 `build_main_window()` 只构造不进事件循环。
"""

import os
import sys
from typing import Any, List, Optional, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QLabel, QMainWindow, QTabWidget,
                               QVBoxLayout, QWidget)

from .. import __version__
from ..engine.core import DISCLAIMER
from ..paths import DataDirNotFound, find_data_dir
from .page_check import CheckPage
from .page_checklist import ChecklistPage
from .page_export import ExportPage
from .page_status import StatusPage
from .page_verify import VerifyPage

APP_TITLE = "钢结构连接与构件验算计算器"
TAB_TITLES = ("① 验算台", "② 设计说明核查", "③ 规范检查单", "④ 报告导出", "⑤ 知识库与状态")
PAGE_CLASSES = (VerifyPage, CheckPage, ChecklistPage, ExportPage, StatusPage)


class MainWindow(QMainWindow):
    def __init__(self, data_dir: str, parent: Optional[QWidget] = None):
        QMainWindow.__init__(self, parent)
        self.data_dir = data_dir
        self.notices: List[str] = []
        self.setWindowTitle("%s（v%s）" % (APP_TITLE, __version__))
        self.resize(1280, 860)

        central = QWidget()
        layout = QVBoxLayout(central)
        header = QLabel("免责声明：%s" % DISCLAIMER)
        header.setWordWrap(True)
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        self.tabs = QTabWidget()
        self.pages = []  # type: List[Any]
        for page_class, title in zip(PAGE_CLASSES, TAB_TITLES):
            page = page_class(data_dir)
            page.set_notifier(self.notify)
            self.pages.append(page)
            self.tabs.addTab(page, title)
        layout.addWidget(self.tabs)
        self.setCentralWidget(central)

        self.status = self.statusBar()
        self.status.showMessage("数据目录：%s｜引擎版本 %s｜%s" % (
            data_dir, __version__, DISCLAIMER))

    def page(self, index: int):
        return self.pages[index]

    def notify(self, message: str, level: str = "info") -> None:
        """页签通知的唯一出口：状态栏 + `notices` 列表，不弹模态框。"""
        line = "[%s] %s" % (level, message)
        self.notices.append(line)
        self.status.showMessage(line)


def build_main_window(data_dir: str) -> MainWindow:
    return MainWindow(data_dir)


def run(data_dir: Optional[str] = None, argv: Optional[Sequence[str]] = None) -> int:
    """进入 Qt 事件循环。数据目录按 `find_data_dir` 的五分支优先级解析（口径 K11）。"""
    try:
        resolved = find_data_dir(data_dir)
    except DataDirNotFound as exc:
        sys.stderr.write("%s\n" % exc)
        return 2
    app = QApplication.instance() or QApplication(list(argv or []))
    window = build_main_window(resolved)
    window.show()
    return int(app.exec())


def capture(data_dir: Optional[str], out_path: str) -> int:
    """截一张主窗口帧（DoD 里的可演示物）。

    两个实测坑：offscreen 平台拿不到中文字体，抓帧要在 native QPA 上跑；
    `QPixmap.save(BytesIO)` 在 PySide6 6.6 不可用，所以存进 QBuffer 再落盘。
    """
    from PySide6.QtCore import QBuffer, QIODevice

    try:
        resolved = find_data_dir(data_dir)
    except DataDirNotFound as exc:
        sys.stderr.write("%s\n" % exc)
        return 2
    app = QApplication.instance() or QApplication([])
    window = build_main_window(resolved)
    window.show()
    app.processEvents()
    buffer = QBuffer()
    buffer.open(QIODevice.ReadWrite)
    window.grab().save(buffer, "PNG")
    directory = os.path.dirname(os.path.abspath(out_path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(out_path, "wb") as handle:
        handle.write(bytes(buffer.data()))
    print("界面帧已保存：%s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(run())
