"""GUI 测试共用件。

**offscreen 平台必须在首次导入 PySide6 之前定下来**（plan/03 §六 的测试口径），所以这个
模块在 import PySide6 之前先写 `QT_QPA_PLATFORM`。测试批全部 offscreen，抓帧/GIF 才需要
另跑 native QPA（见 `sdc gui --screenshot`）。

`cli_call()` 是契约测试的量尺：它跑的就是 `sdc.cli.main`，GUI 的文本面板必须与它逐字相同。
"""

import contextlib
import io
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest  # noqa: E402

pytest.importorskip("PySide6.QtWidgets", reason="GUI 走 extras：pip install sdc[gui]")

from PySide6.QtWidgets import QApplication  # noqa: E402

from sdc import cli  # noqa: E402
from sdc.gui import build_main_window  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
REPO_DATA_DIR = os.path.join(ROOT, "data")
FIXTURE_KB_DIR = os.path.join(HERE, "fixtures", "kb")
DEMO_CARD = os.path.join(REPO_DATA_DIR, "examples", "A2-fillet-weld.json")
INJECTED_DOCX = os.path.join(REPO_DATA_DIR, "synth", "docx", "SYNTH-0013.docx")
CLEAN_DOCX = os.path.join(REPO_DATA_DIR, "synth", "docx", "SYNTH-0000.docx")


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def cli_call(argv):
    """在进程内跑一次命令面，返回 (退出码, stdout, stderr)。"""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def make_ir(data_dir, docx, out_dir):
    """用 `sdc parse` 造一份落盘 IR（判定层与界面都只吃现成 IR，口径 K26）。"""
    target = os.path.join(str(out_dir), "%s.ir.json" % os.path.splitext(
        os.path.basename(docx))[0])
    code, _out, err = cli_call(["--data-dir", data_dir, "parse", "--doc", docx,
                               "--out", target])
    assert code == 0, err
    return target


def write_card(out_dir, overrides=None, base=None):
    """把演示参数卡复制到临时目录，可选覆盖几个槽位（用于失败路径的对照）。"""
    import json

    with open(DEMO_CARD, "r", encoding="utf-8") as handle:
        card = json.loads(handle.read())
    card.update(overrides or {})
    for key, value in (base or {}).items():
        card[key] = value
    path = os.path.join(str(out_dir), "card.json")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(card, ensure_ascii=False, indent=2, sort_keys=True))
    return path


def window_for(data_dir):
    return build_main_window(data_dir)


def item_text(table, row, column):
    item = table.item(row, column)
    return "" if item is None else item.text()


def cell_widget_text(table, row, column):
    widget = table.cellWidget(row, column)
    if widget is None:
        return item_text(table, row, column)
    getter = getattr(widget, "currentText", None)
    return getter() if callable(getter) else ""


__all__ = [  # 常量供测试直接引用，避免每个文件重复拼路径
    "CLEAN_DOCX", "DEMO_CARD", "FIXTURE_KB_DIR", "INJECTED_DOCX", "REPO_DATA_DIR",
    "ROOT", "cell_widget_text", "cli_call", "item_text", "make_ir", "qapp",
    "window_for", "write_card",
]
