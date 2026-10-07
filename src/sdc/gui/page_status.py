"""页签⑤知识库与状态：门控看板、推进看板、核对队列、一键基准指标表。

这一页是把纪律做成看得见的功能，不是装饰：
正文一律是 `sdc selfcheck` 与 `sdc bench --all` 的同一个渲染器输出（口径 K41），
表格只是 payload 的另一种视图。指标表的四态里「不可判」「不可用」原样显示，
**不得**渲染成达标或绿勾（口径 K43 与 HANDOFF-M5 §七）。
"""

import os
import tempfile
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QSplitter,
                               QTabWidget, QVBoxLayout, QWidget)

from ..cli import bench_suite_command
from ..selfcheck import build_report as build_selfcheck_report
from ..selfcheck import render_text as render_selfcheck
from ..suite import STATUS_LABEL, render_text as render_suite
from .widgets import BasePage, fill_table, make_table, make_text_view, text_group

HEADERS_GATE = ("模块", "门控", "原因", "未就绪依赖")
HEADERS_PROGRESS = ("kind", "总数", "verified", "located", "pending", "verified %")
HEADERS_RULES = ("规则 id", "check_type", "有效档位", "未启用原因", "还差核对")
HEADERS_QUEUE = ("条款 id", "status", "解锁项数", "规则", "条目")
HEADERS_METRICS = ("指标", "门槛", "实测", "结论", "来源命令")


class StatusPage(BasePage):
    """⑤知识库与状态。"""

    def __init__(self, data_dir: str, parent: Optional[QWidget] = None):
        BasePage.__init__(self, data_dir, parent)
        self.selfcheck: Optional[Dict[str, Any]] = None
        self.suite: Optional[Dict[str, Any]] = None
        self.exit_code: Optional[int] = None

        layout = QVBoxLayout(self)
        self.refresh_button = QPushButton("刷新 selfcheck 看板")
        self.bench_button = QPushButton("跑一键基准（sdc bench --all，需要几秒）")
        self.refresh_button.clicked.connect(self.refresh)
        self.bench_button.clicked.connect(self.run_bench)
        row = QHBoxLayout()
        row.addWidget(self.refresh_button)
        row.addWidget(self.bench_button)
        row.addStretch(1)
        layout.addLayout(row)

        self.summary = QLabel("数据目录：%s" % data_dir)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.add_notice_label(layout)

        self.gate = make_table(HEADERS_GATE)
        self.progress = make_table(HEADERS_PROGRESS)
        self.rules = make_table(HEADERS_RULES)
        self.queue = make_table(HEADERS_QUEUE)
        self.metrics = make_table(HEADERS_METRICS)
        self.selfcheck_text = make_text_view("点「刷新 selfcheck 看板」")
        self.bench_text = make_text_view("点「跑一键基准」")

        boards = QTabWidget()
        tabs = QWidget()
        tab_layout = QVBoxLayout(tabs)
        grid = QSplitter(Qt.Horizontal)
        grid.addWidget(text_group("模块门控 [3]", self.gate))
        grid.addWidget(text_group("推进看板 [6]", self.progress))
        tab_layout.addWidget(grid)
        tab_layout.addWidget(text_group("规则未启用原因", self.rules))
        tab_layout.addWidget(text_group("核对队列 [7]", self.queue))
        boards.addTab(tabs, "看板表格")
        boards.addTab(text_group("selfcheck 原文", self.selfcheck_text), "selfcheck 原文")
        boards.addTab(text_group("指标表", self.metrics), "一键基准表格")
        boards.addTab(text_group("bench --all 原文", self.bench_text), "一键基准原文")
        layout.addWidget(boards)

        self.refresh()

    # -- selfcheck ----------------------------------------------------------
    def refresh(self) -> Dict[str, Any]:
        report = build_selfcheck_report(self.data_dir)
        self.selfcheck = report
        trace = report["traceability"]
        self.summary.setText(
            "数据目录：%s｜指纹 %s｜结构与引用问题 %d 项｜可溯源 %d/%d" % (
                report["data_dir"], report["data_fingerprint"][:12],
                len(report["problems"]), trace["checked_with_channel"],
                trace["checked_total"]))
        fill_table(self.gate, HEADERS_GATE, [
            (gate["module"], gate["status"], gate["reason"],
             "; ".join("%s %s" % (item["kind"], item["id"]) for item in gate["unready"]))
            for gate in report["modules"]])
        fill_table(self.progress, HEADERS_PROGRESS, [
            (kind, row["total"], row["verified"], row["located"], row["pending"],
             "%.1f" % row["percent_verified"])
            for kind, row in sorted(report["progress"].items()) if row["total"]])
        fill_table(self.rules, HEADERS_RULES, [
            (row["id"], row["check_type"], row["effective_status"], row["reason"],
             ", ".join(row["blockers"]))
            for row in report["rules"]["rules"]])
        fill_table(self.queue, HEADERS_QUEUE, [
            (item["clause_id"], item["status"], item["unlock_count"],
             ", ".join(item["rules"]), ", ".join(item["entries"]))
            for item in report["verify_queue"]])
        self.selfcheck_text.setPlainText(render_selfcheck(report))
        self.notify("selfcheck 看板已刷新（ok=%s）" % report["ok"])
        return report

    # -- 一键基准 -----------------------------------------------------------
    def workdir(self) -> str:
        directory = os.path.join(tempfile.gettempdir(), "sdc-gui-suite")
        if not os.path.isdir(directory):
            os.makedirs(directory)
        return directory

    def run_bench(self) -> Dict[str, Any]:
        self.notify("一键基准运行中（整批语料解析两遍，走子进程）…")
        report, code, error = bench_suite_command(self.data_dir, self.workdir(), False)
        if report is None:
            self.bench_text.setPlainText(error)
            self.notify(error.strip(), "error")
            return {}
        self.suite = report
        self.exit_code = code
        counts = dict((status, 0) for status in STATUS_LABEL)
        for row in report["metrics"]:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        fill_table(self.metrics, HEADERS_METRICS, [
            (row["name"], row["gate"], row["measured"],
             STATUS_LABEL.get(row["status"], row["status"]), row["source"])
            for row in report["metrics"]])
        self.bench_text.setPlainText(render_suite(report, sweep_only=False, exit_code=code))
        self.notify("一键基准退出码 %d：达标 %d／不可判 %d／未达标 %d／不可用 %d" % (
            code, counts["pass"], counts["unmeasurable"], counts["fail"],
            counts["unavailable"]))
        return report
