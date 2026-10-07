"""页签②设计说明核查：docx/txt → IR → 三级判定清单。

**解析不在本进程发生**：文档抽取由 `sdc parse` 子进程完成（口径 K39 的桌面侧延伸，
本机 `sre_parse` 是已知崩溃点，界面不该跟着一起倒）。通路取 `sdc.suite.cli_channel()`，
源码态是当前解释器 `-m sdc`，打包态是同侧的 `sdc-cli` exe（口径 K45）；两条都不成立时
界面显示子进程给出的原因，不假装解析成功。

判定部分与 `sdc check` 共用 `sdc.cli.check_command`，正文用 `sdc.rules.render_report`，
所以清单一字不差地就是终端那一份（口径 K41）。
"""

import os
import tempfile
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSplitter, QVBoxLayout, QWidget)

from ..cli import check_command
from ..rules import render_report
from ..suite import cli_channel, run_cli
from .widgets import BasePage, button_row, fill_table, make_table, make_text_view, text_group

HEADERS_FINDINGS = ("等级", "规则 id", "规则名", "判定", "依据档位", "条款", "原文证据")
HEADERS_INACTIVE = ("规则 id", "未启用原因")
DOC_FILTER = "设计说明 (*.docx *.txt *.md)"


def finding_rows(report: Dict[str, Any]) -> List[tuple]:
    rows = []
    for item in report["findings"]:
        evidence = item["evidence"][0] if item["evidence"] else None
        where = ""
        if evidence is not None:
            where = "第 %s 段：%s" % (evidence["para"], evidence["text"])
        rows.append((item["level"], item["rule_id"], item["name"], item["outcome"],
                     item["status"], ", ".join(item["clause_ids"]), where))
    return rows


class CheckPage(BasePage):
    """②设计说明核查。"""

    def __init__(self, data_dir: str, parent: Optional[QWidget] = None):
        BasePage.__init__(self, data_dir, parent)
        self.report = None
        self.exit_code = None
        self.ir_path = ""

        layout = QVBoxLayout(self)
        self.doc_field = QLineEdit()
        self.doc_field.setPlaceholderText("设计说明文档（.docx/.txt/.md）")
        self.ir_field = QLineEdit()
        self.ir_field.setPlaceholderText("IR 文件（解析后自动填；也可以直接指向现成 IR）")
        pick_doc = QPushButton("选择文档…")
        pick_ir = QPushButton("选择 IR…")
        self.parse_button = QPushButton("① 解析为 IR（子进程）")
        self.check_button = QPushButton("② 核查（三级判定）")
        pick_doc.clicked.connect(self._pick_doc)
        pick_ir.clicked.connect(self._pick_ir)
        self.parse_button.clicked.connect(self.parse_document)
        self.check_button.clicked.connect(self.check)

        paths = QWidget()
        form = QVBoxLayout(paths)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("文档"))
        row1.addWidget(self.doc_field)
        row1.addWidget(pick_doc)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("IR"))
        row2.addWidget(self.ir_field)
        row2.addWidget(pick_ir)
        form.addLayout(row1)
        form.addLayout(row2)
        layout.addWidget(paths)
        layout.addLayout(button_row(self.parse_button, self.check_button))

        self.summary = QLabel("尚未核查。异常/可疑的分级由依据条款的档位决定，依据未核对时限值类规则不硬判不符合。")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.add_notice_label(layout)

        self.parse_text = make_text_view("sdc parse 子进程的输出（原文）")
        self.check_text = make_text_view("sdc check 的输出（与终端同一批行）")
        self.findings = make_table(HEADERS_FINDINGS)
        self.inactive = make_table(HEADERS_INACTIVE)

        panes = QSplitter(Qt.Vertical)
        panes.addWidget(text_group("核查清单原文", self.check_text))
        panes.addWidget(text_group("非 pass 项 findings", self.findings))
        panes.addWidget(text_group("未启用的规则", self.inactive))
        panes.addWidget(text_group("解析输出", self.parse_text))
        layout.addWidget(panes)

    # -- 通路 ---------------------------------------------------------------
    def _scratch_dir(self) -> str:
        directory = os.path.join(tempfile.gettempdir(), "sdc-gui")
        if not os.path.isdir(directory):
            os.makedirs(directory)
        return directory

    def _pick_doc(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择设计说明", "", DOC_FILTER)
        if path:
            self.doc_field.setText(path)

    def _pick_ir(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 IR", "", "IR JSON (*.ir.json *.json)")
        if path:
            self.ir_field.setText(path)

    def parse_document(self) -> Optional[str]:
        """把文档交给 `sdc parse` 子进程；返回落盘的 IR 路径，失败返回 None。"""
        doc = self.doc_field.text().strip()
        if not doc:
            self.notify("先选择设计说明文档", "warn")
            return None
        stem = os.path.splitext(os.path.basename(doc))[0]
        target = os.path.join(self._scratch_dir(), "%s.ir.json" % stem)
        channel, _cwd = cli_channel()
        if channel is None:
            self.parse_text.setPlainText(
                "解析通路不可用：打包版需要同目录的 sdc-cli.exe（或把 SDC_CLI_EXE 指向它）。"
                "文档解析只在 `sdc parse` 与套件子进程里发生（口径 K39/K45），界面不自己跑正则。")
            self.notify("解析通路不可用", "error")
            return None
        rc, output = run_cli(["parse", "--doc", os.path.abspath(doc),
                              "--out", os.path.abspath(target)], self.data_dir)
        self.parse_text.setPlainText(output)
        if rc != 0:
            self.notify("解析子进程退出码 %s，未生成 IR" % rc, "error")
            return None
        self.ir_field.setText(os.path.abspath(target))
        self.ir_path = os.path.abspath(target)
        self.notify("已生成 IR：%s" % os.path.basename(target))
        return self.ir_path

    def check(self, ir_path: Optional[str] = None) -> Dict[str, Any]:
        path = (ir_path or self.ir_field.text() or "").strip()
        if not path:
            self.notify("先解析文档或选择现成 IR", "warn")
            return {}
        report, code, error = check_command(self.data_dir, path)
        self.report = report
        self.exit_code = code
        if report is None:
            fill_table(self.findings, HEADERS_FINDINGS, [])
            fill_table(self.inactive, HEADERS_INACTIVE, [])
            self.check_text.setPlainText(error)
            self.summary.setText("核查未完成（退出码 %d）：%s" % (code, error.strip()))
            self.notify(error.strip(), "error")
            return {}
        counts = report["counts"]
        self.summary.setText("文档级结论：%s｜异常 %d｜可疑 %d｜退出码 %d｜规则库 %d 条｜指纹 %s" % (
            report["conclusion"], counts["abnormal"], counts["suspicious"], code,
            report["rules_total"], report["meta"]["data_fingerprint"][:12]))
        fill_table(self.findings, HEADERS_FINDINGS, finding_rows(report))
        fill_table(self.inactive, HEADERS_INACTIVE,
                   [(item["rule_id"], item["reason"]) for item in report["not_activated"]])
        self.check_text.setPlainText(render_report(report))
        return report
