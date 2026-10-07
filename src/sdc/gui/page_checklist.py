"""页签③GB 55006-2021 符合性检查单：逐项核对 + 符合性清单。

自动初判与人工答复的合流走 `sdc.cli.checklist_command`（即 `sdc checklist --ir --answers`
那条通路），人工答复先落成 JSON 再交进去：界面不自己判符合性，也不把人工答复与自动初判
混成一体（口径 K5 的档位约束在判定层，不在界面）。
"""

import json
import os
import tempfile
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QTableWidgetItem,
                               QTableWidget, QVBoxLayout, QWidget)

from ..checklist import ANSWER_OPTIONS
from ..checklist import render_text as render_checklist
from ..cli import checklist_command
from .widgets import BasePage, button_row, make_text_view, text_group

HEADERS = ("条目 id", "章", "标题", "自动初判", "人工答复", "status", "强条", "出处渠道")
ANSWER_COLUMN = 4
NO_ANSWER = ""


class ChecklistPage(BasePage):
    """③通用规范检查单。"""

    def __init__(self, data_dir: str, parent: Optional[QWidget] = None):
        BasePage.__init__(self, data_dir, parent)
        self.report: Optional[Dict[str, Any]] = None
        self.exit_code: Optional[int] = None
        self._combos: List[QComboBox] = []

        layout = QVBoxLayout(self)
        self.ir_field = QLineEdit()
        self.ir_field.setPlaceholderText("可选：接 IR 做自动初判；不接则全部条目只能待人工确认")
        pick = QPushButton("选择 IR…")
        pick.clicked.connect(self._pick_ir)
        self.build_button = QPushButton("生成检查单")
        self.apply_button = QPushButton("按人工答复重新判定")
        self.build_button.clicked.connect(self.build)
        self.apply_button.clicked.connect(self.apply_answers)

        row = QHBoxLayout()
        row.addWidget(QLabel("IR"))
        row.addWidget(self.ir_field)
        row.addWidget(pick)
        layout.addLayout(row)
        layout.addLayout(button_row(self.build_button, self.apply_button))

        self.summary = QLabel("尚未生成。共 107 条（全 8 章），只有少数条目挂得上自动初判，"
                              "其余必须人工确认——这是事实，界面不替它涂绿。")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.add_notice_label(layout)

        self.table = QTableWidget()
        self.table.setColumnCount(len(HEADERS))
        self.table.setHorizontalHeaderLabels(list(HEADERS))
        layout.addWidget(text_group("检查单条目", self.table))

        self.text = make_text_view("sdc checklist 的输出（与终端同一批行）")
        layout.addWidget(text_group("清单原文", self.text))

    def _pick_ir(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 IR", "", "IR JSON (*.ir.json *.json)")
        if path:
            self.ir_field.setText(path)

    def build(self, ir_path: Optional[str] = None,
              answers_path: Optional[str] = None) -> Dict[str, Any]:
        path = (ir_path if ir_path is not None else self.ir_field.text()).strip()
        report, code, error = checklist_command(self.data_dir, path or None,
                                                answers_path or None)
        self.report = report
        self.exit_code = code
        if report is None:
            self.text.setPlainText(error)
            self.summary.setText("未完成（退出码 %d）：%s" % (code, error.strip()))
            self.notify(error.strip(), "error")
            return {}
        summary = report["summary"]
        missing = summary["chapters_missing"]
        self.summary.setText("条目 %d 条｜覆盖 %d 章｜判定分布 %s｜退出码 %d%s" % (
            summary["total"], len(summary["chapters_covered"]),
            "、".join("%s=%d" % pair for pair in sorted(summary["by_verdict"].items())),
            code,
            "｜未覆盖的章：%s" % "、".join(missing) if missing else ""))
        self.fill(report)
        self.text.setPlainText(render_checklist(report))
        return report

    def fill(self, report: Dict[str, Any]) -> None:
        self._combos = []
        self.table.clear()
        self.table.setColumnCount(len(HEADERS))
        self.table.setHorizontalHeaderLabels(list(HEADERS))
        entries = report["entries"]
        self.table.setRowCount(len(entries))
        answers = dict((row["id"], row["human_answer"]) for row in entries
                       if row["human_answer"])
        for r, row in enumerate(entries):
            cells = (row["id"], row["chapter_text"], row["title"], row["verdict_label"],
                     "", row["status"], "是" if row["mandatory"] else "", row["source"])
            for c, value in enumerate(cells):
                if c == ANSWER_COLUMN:
                    continue
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(r, c, item)
            combo = QComboBox()
            combo.addItems([NO_ANSWER] + list(ANSWER_OPTIONS))
            if row["id"] in answers:
                combo.setCurrentText(answers[row["id"]])
            self.table.setCellWidget(r, ANSWER_COLUMN, combo)
            self._combos.append(combo)
        self.table.resizeColumnsToContents()

    def collected_answers(self) -> Dict[str, str]:
        ids = [row["id"] for row in (self.report or {}).get("entries", [])]
        out = {}  # type: Dict[str, str]
        for index, combo in enumerate(self._combos):
            text = combo.currentText()
            if text and index < len(ids):
                out[ids[index]] = text
        return out

    def answers_file(self) -> str:
        directory = os.path.join(tempfile.gettempdir(), "sdc-gui")
        if not os.path.isdir(directory):
            os.makedirs(directory)
        path = os.path.join(directory, "answers.json")
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(self.collected_answers(), ensure_ascii=False,
                                    indent=2, sort_keys=True))
        return path

    def apply_answers(self) -> Dict[str, Any]:
        answers = self.collected_answers()
        if not answers:
            self.notify("没有人工答复可提交（先在「人工答复」列里选）", "warn")
            return {}
        return self.build(answers_path=self.answers_file())
