"""页签④报告导出：验算书 / 核查清单 / 符合性检查单三类 docx 交付物。

每一类都复用命令面的那一步：正文来自 `sdc.report.result_body`/`check_body`/`checklist_body`
（= 终端渲染器的同一批行，口径 K41），落盘走 `sdc.cli.export_command`。
导出前的自检不过就**不写文件**（0 外链、免责声明必存，口径 K40），界面上原样显示
`ReportError` 说明为什么没写出来，不吞异常。
"""

import os
from typing import Any, Dict, Optional, Tuple

from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout, QWidget)

from ..cli import (check_command, checklist_command, export_command,
                   run_case_command)
from ..engine.render import DISCLAIMER
from ..report import (body_text, check_body, checklist_body, find_external_refs,
                      metadata_values, result_body)
from .widgets import BasePage, make_text_view, text_group

FILTER_DOCX = "Word 文档 (*.docx)"


class ExportPage(BasePage):
    """④报告导出。"""

    def __init__(self, data_dir: str, parent: Optional[QWidget] = None):
        BasePage.__init__(self, data_dir, parent)
        layout = QVBoxLayout(self)
        self.report_text = make_text_view("导出结果与自检事实（0 外链处数、docProps 占位符、免责声明）")
        self.out_dir = QLineEdit(os.path.join(os.getcwd(), ".tmp_parse", "reports"))
        row = QHBoxLayout()
        row.addWidget(QLabel("输出目录"))
        row.addWidget(self.out_dir)
        layout.addLayout(row)
        layout.addWidget(text_group("导出记录", self.report_text))
        self.add_notice_label(layout)

        self.case_field = QLineEdit()
        self.case_field.setPlaceholderText("参数卡 JSON（data/examples/*.json）")
        self.ir_field = QLineEdit()
        self.ir_field.setPlaceholderText("IR 文件（.ir.json，由页签②解析得到）")
        layout.addWidget(self._path_row("验算书输入：参数卡", self.case_field))
        layout.addWidget(self._path_row("核查/检查单输入：IR", self.ir_field))

        buttons = QHBoxLayout()
        for label, slot in (
                ("导出验算书.docx", self.export_result),
                ("导出核查清单.docx", self.export_check),
                ("导出检查单.docx", self.export_checklist)):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.results = {}  # type: Dict[str, Any]

    def _path_row(self, label: str, field: QLineEdit) -> QWidget:
        box = QWidget()
        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(QLabel(label))
        row = QHBoxLayout()
        row.addWidget(field)
        pick = QPushButton("选择…")
        pick.clicked.connect(lambda _=None, target=field: self._pick(target))
        row.addWidget(pick)
        outer.addLayout(row)
        return box

    def _pick(self, field: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择输入文件", "",
                                              "JSON (*.json *.ir.json)")
        if path:
            field.setText(path)

    def _out_path(self, name: str) -> str:
        directory = os.path.abspath(self.out_dir.text().strip() or os.getcwd())
        if not os.path.isdir(directory):
            os.makedirs(directory)
        return os.path.join(directory, name)

    def _log(self, lines, failed: bool = False) -> None:
        """导出记录写进面板；失败必须同时进通知通道（ReportError 不许被吞掉）。"""
        self.report_text.setPlainText("\n".join(lines))
        if failed:
            self.notify("；".join(lines[:2]), "error")

    def export_result(self, out_path: Optional[str] = None) -> Tuple[Optional[str], int]:
        """验算书导出 → (写出的路径或 None, 退出码)；退出码沿用 `sdc report` 的口径。"""
        case = self.case_field.text().strip()
        if not case:
            self.notify("先选择参数卡", "warn")
            return None, 2
        result, code, error = run_case_command(self.data_dir, case, None)
        if result is None:
            self._log(["验算书未写出：参数卡通路失败（退出码 %d）" % code, error.rstrip("\n")],
                      failed=True)
            return None, code
        written, export_code, error = export_command(
            result_body(result, case), out_path or self._out_path("验算书.docx"))
        self.results["result"] = (written, export_code, result)
        self._log(self._lines("验算书", written, export_code, error, code),
                  failed=written is None)
        return written, max(code, export_code)

    def export_check(self, out_path: Optional[str] = None) -> Tuple[Optional[str], int]:
        ir = self.ir_field.text().strip()
        if not ir:
            self.notify("先选择 IR（可在页签②解析得到）", "warn")
            return None, 2
        report, code, error = check_command(self.data_dir, ir)
        if report is None:
            self._log(["核查清单未写出：%s" % error.rstrip("\n")], failed=True)
            return None, code
        written, export_code, error = export_command(
            check_body(report), out_path or self._out_path("核查清单.docx"))
        self.results["check"] = (written, export_code, report)
        self._log(self._lines("核查清单", written, export_code, error, code),
                  failed=written is None)
        return written, max(code, export_code)

    def export_checklist(self, out_path: Optional[str] = None) -> Tuple[Optional[str], int]:
        ir = self.ir_field.text().strip()
        report, code, error = checklist_command(self.data_dir, ir or None, None)
        if report is None:
            self._log(["检查单未写出：%s" % error.rstrip("\n")], failed=True)
            self.notify(error.strip(), "error")
            return None, code
        written, export_code, error = export_command(
            checklist_body(report, ir), out_path or self._out_path("检查单.docx"))
        self.results["checklist"] = (written, export_code, report)
        self._log(self._lines("检查单", written, export_code, error, code),
                  failed=written is None)
        return written, max(code, export_code)

    def _lines(self, kind: str, written: Optional[str], code: int,
               error: str, source_code: int) -> list:
        if written is None:
            return ["%s未写出（退出码 %d）：落盘前自检未通过" % (kind, code),
                    error.rstrip("\n"),
                    "说明：自检不过就不写文件，这是交付物纪律（口径 K40/K41），不是导出功能坏了。"]
        with open(written, "rb") as handle:
            payload = handle.read()
        refs = find_external_refs(payload)
        meta = metadata_values(payload)
        return [
            "%s已导出：%s" % (kind, os.path.basename(written)),
            "退出码：%d（判定通路 %d，导出 %d）" % (max(code, source_code), source_code, code),
            "文件大小：%d 字节" % len(payload),
            "0 外链自检：%d 处违规（口径 K40 的机器定义）" % len(refs),
            "docProps：creator=%s｜lastModifiedBy=%s｜Application=%s" % (
                meta.get("creator", ""), meta.get("lastModifiedBy", ""),
                meta.get("Application", "")),
            "免责声明在正文里：%s（%s）" % ("是" if DISCLAIMER in body_text(payload) else "否",
                                             DISCLAIMER),
        ]
