"""界面共用件：文本面板、只读表格、可注入的通知通道。

三条纪律写在这里：

1. **界面不重排事实**。`fill_table` 只把 payload 里已有的字段摆成行，不换算、不补默认值、
   不改写措辞（口径 K41）。要给人看结论原文，就显示命令面用的同一个渲染函数的输出。
2. **通知一律走 `NotifyMixin.notify`**，默认收进本页的 `messages` 列表，主窗口注册了
   通知回调时同时写状态栏。这里**不允许**出现模态框：offscreen 平台上的模态对话框会
   把测试批挂死（plan/03 §六 的测试口径）。
3. 文件对话框只在按钮槽函数里构造，测试 monkeypatch `QFileDialog` 即可完全避开。
"""

from typing import Any, Iterable, List, Optional, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QPlainTextEdit, QPushButton, QScrollArea,
                               QSplitter, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

MONO_FAMILY = "Consolas"
MONO_POINT_SIZE = 10

HEADERS_RESULT = ("步序", "公式 id", "式体", "代入", "结果", "单位", "符号含义")
HEADERS_BASIS = ("条款 id", "标题", "kind", "status", "强条")
HEADERS_BLOCKED = ("kind", "id", "status", "原因")


def mono_font() -> QFont:
    font = QFont(MONO_FAMILY)
    font.setPointSize(MONO_POINT_SIZE)
    return font


def make_text_view(placeholder: str = "") -> QPlainTextEdit:
    view = QPlainTextEdit()
    view.setReadOnly(True)
    view.setFont(mono_font())
    view.setLineWrapMode(QPlainTextEdit.NoWrap)
    if placeholder:
        view.setPlaceholderText(placeholder)
    return view


def fill_table(table: QTableWidget, headers: Sequence[str],
               rows: Iterable[Sequence[Any]]) -> QTableWidget:
    """用 payload 里现成的字段填表；None 显示成空串，其余一律 `str()`。"""
    material = list(rows)
    table.clear()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.setRowCount(len(material))
    for r, row in enumerate(material):
        for c, value in enumerate(row):
            item = QTableWidgetItem("" if value is None else str(value))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(r, c, item)
    table.resizeColumnsToContents()
    return table


def make_table(headers: Sequence[str], rows: Iterable[Sequence[Any]] = ()) -> QTableWidget:
    table = QTableWidget()
    fill_table(table, headers, rows)
    return table


def text_group(title: str, view: QPlainTextEdit) -> QGroupBox:
    box = QGroupBox(title)
    layout = QVBoxLayout(box)
    layout.addWidget(view)
    return box


def button_row(*buttons: QPushButton) -> QHBoxLayout:
    row = QHBoxLayout()
    for button in buttons:
        row.addWidget(button)
    row.addStretch(1)
    return row


def scroll_form(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidget(widget)
    area.setWidgetResizable(True)
    return area


def form_layout(pairs: Iterable) -> QFormLayout:
    layout = QFormLayout()
    for label, field in pairs:
        layout.addRow(label, field)
    return layout


class NotifyMixin(object):
    """可注入的通知通道；`messages` 是测试读回通知的唯一入口。"""

    def init_notify(self) -> None:
        self._notifier: Optional[Any] = None
        self.messages: List[str] = []

    def set_notifier(self, notifier) -> None:
        self._notifier = notifier

    def notify(self, message: str, level: str = "info") -> None:
        line = "[%s] %s" % (level, message)
        self.messages.append(line)
        if self._notifier is not None:
            self._notifier(message, level)


class BasePage(QWidget, NotifyMixin):
    """页签基类：拿到主窗口的通知回调，自己不制造模态交互。"""

    def __init__(self, data_dir: str, parent: Optional[QWidget] = None):
        QWidget.__init__(self, parent)
        self.init_notify()
        self.data_dir = data_dir
        self.setWindowTitle(self.__class__.__name__)

    def add_notice_label(self, layout: QVBoxLayout) -> QLabel:
        label = QLabel("")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.notice_label = label
        return label

    def notify(self, message: str, level: str = "info") -> None:
        NotifyMixin.notify(self, message, level)
        if getattr(self, "notice_label", None) is not None:
            self.notice_label.setText(message)


__all__ = [
    "BasePage", "HEADERS_BASIS", "HEADERS_BLOCKED", "HEADERS_RESULT",
    "NotifyMixin", "button_row", "fill_table", "form_layout", "make_table",
    "make_text_view", "mono_font", "scroll_form", "text_group",
]
