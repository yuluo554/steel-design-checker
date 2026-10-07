"""五页签的行为与"界面不越权"守门测试（offscreen 常驻，无模态框）。

三条硬口径在这里都有测试承接：
- 界面只消费命令面 API，不出现第二套判定/渲染/查表（D08/K41，见 `test_gui_imports_stay_inside`）；
- 拒算就是拒算，blocked 结果里一个数值都不许有（K2/K15）；
- 「不可判」「不可用」不得被涂成达标（K43），解析通路拿不到时界面直说拿不到（K39/K45）。
"""

import ast
import json
import os

from _gui import (CLEAN_DOCX, DEMO_CARD, FIXTURE_KB_DIR, INJECTED_DOCX,
                  REPO_DATA_DIR, ROOT, cli_call, item_text, make_ir, qapp,
                  window_for)

GUI_DIR = os.path.join(ROOT, "src", "sdc", "gui")

# 界面允许的依赖：命令面的公开 API + 引擎的数据结构，没有解析层
ALLOWED_SDC_IMPORTS = {
    "sdc", "sdc.cli", "sdc.engine", "sdc.engine.core", "sdc.engine.params",
    "sdc.engine.render", "sdc.engine.units", "sdc.kb", "sdc.kb.schema",
    "sdc.checklist", "sdc.rules", "sdc.report", "sdc.suite", "sdc.selfcheck",
    "sdc.paths",
}
FORBIDDEN_MODULES = {"re", "random", "socket", "urllib", "requests", "numpy",
                     "scipy", "subprocess"}


def gui_files():
    return sorted(name for name in os.listdir(GUI_DIR) if name.endswith(".py"))


def imported_names(path):
    """返回 (绝对导入的模块名集合, 相对导入的名字集合, 源码里出现过的属性名)。"""
    with open(path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    absolute = set()
    relative = set()
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            absolute.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                relative.add(node.module or "")
            else:
                absolute.add(node.module or "")
                absolute.update("%s.%s" % (node.module, alias.name) for alias in node.names)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
        elif isinstance(node, ast.Name):
            used.add(node.id)
    return absolute, relative, used


# ---------------------------------------------------------------------------
# 守门：依赖面与模态框
# ---------------------------------------------------------------------------

def test_gui_imports_stay_inside_the_command_surface():
    """GUI 不得 import `re`/`subprocess`/网络库，也不得 import 解析层。

    解析层（`sdc.parse`）出现在界面里就意味着界面自己跑正则读文档 —— 那是
    K39/K45 明令由子进程承担的一步。
    """
    offenders = []
    for name in gui_files():
        absolute, _relative, _used = imported_names(os.path.join(GUI_DIR, name))
        for module in absolute:
            root = module.split(".")[0]
            if root in FORBIDDEN_MODULES:
                offenders.append("%s imports %s" % (name, module))
            if root == "sdc" and module not in ALLOWED_SDC_IMPORTS:
                offenders.append("%s imports %s" % (name, module))
        if any(part.startswith("sdc.parse") for part in absolute):
            offenders.append("%s 直接 import 了解析层" % name)
    assert not offenders, "；".join(offenders)


def test_gui_never_builds_a_modal_dialog():
    """offscreen 测试批会被模态框挂死（plan/03 §六），界面通知只能走 NotifyMixin。"""
    for name in gui_files():
        with open(os.path.join(GUI_DIR, name), "r", encoding="utf-8") as handle:
            source = handle.read()
        assert "QMessageBox" not in source, "%s 里出现了模态框" % name


def test_gui_modules_do_not_compute_or_measure_themselves():
    """界面里不得出现查表/求值/闸门类调用——那些都在引擎与判定层。"""
    banned_calls = {"lookup", "evaluate", "build_plan", "parse_expression",
                    "module_gate", "effective_status", "level_for", "run_rules",
                    "build_ir", "read_document", "extract_slots", "generate_corpus"}
    offenders = []
    for name in gui_files():
        _absolute, _relative, used = imported_names(os.path.join(GUI_DIR, name))
        hit = sorted(banned_calls & used)
        if hit:
            offenders.append("%s 调用了 %s" % (name, ", ".join(hit)))
    assert not offenders, "；".join(offenders)


# ---------------------------------------------------------------------------
# 主窗口
# ---------------------------------------------------------------------------

def test_five_tabs_in_the_planned_order(qapp):
    window = window_for(REPO_DATA_DIR)
    titles = [window.tabs.tabText(index) for index in range(window.tabs.count())]
    assert titles == ["① 验算台", "② 设计说明核查", "③ 规范检查单", "④ 报告导出",
                      "⑤ 知识库与状态"]
    assert len(window.pages) == 5


def test_disclaimer_is_pinned_and_verbatim(qapp):
    from PySide6.QtWidgets import QLabel

    from sdc.engine.core import DISCLAIMER

    window = window_for(REPO_DATA_DIR)
    pinned = [label.text() for label in window.findChildren(QLabel)
              if DISCLAIMER in label.text()]
    assert pinned, "免责声明必须常驻窗口，而不是只在弹窗里出现一次"
    assert DISCLAIMER in window.status.currentMessage()
    # 界面不许另写一句免责话术：src/ 里这条文案只允许出现在 engine/core.py（test_report 已守）
    assert all(text.count(DISCLAIMER) == 1 for text in pinned)


# ---------------------------------------------------------------------------
# ① 验算台
# ---------------------------------------------------------------------------

def test_verify_page_blocks_real_data_and_shows_no_numbers(qapp):
    page = window_for(REPO_DATA_DIR).page(0)
    assert page._load(DEMO_CARD)
    result = page.run()
    assert result["conclusion"] == "blocked"
    assert page.exit_code == 1
    assert result["steps"] == [] and result["ratio"] is None
    assert page.steps.rowCount() == 0                      # 数值步骤一行都不该有
    assert page.blocked.rowCount() == len(result["blocked"])
    assert "不出数值（blocked）" in page.text.toPlainText()
    assert "拒算依据" in page.text.toPlainText()


def test_verify_page_produces_steps_on_the_fixture_kb(qapp):
    page = window_for(FIXTURE_KB_DIR).page(0)
    assert page._load(DEMO_CARD)
    result = page.run()
    assert result["conclusion"] != "blocked"
    assert page.steps.rowCount() == len(result["steps"]) > 0
    row = [item_text(page.steps, 0, column) for column in range(page.steps.columnCount())]
    assert result["steps"][0]["formula_id"] in row


def test_form_fields_follow_the_module_slot_table(qapp):
    from sdc.engine.params import MODULE_SLOTS
    from sdc.kb.schema import MODULES

    page = window_for(REPO_DATA_DIR).page(0)
    for index, module in enumerate(MODULES):
        page.form.module_combo.setCurrentIndex(index)
        spec = MODULE_SLOTS[module]
        assert set(page.form.fields) == set(spec["required"]) | set(spec["optional"])


def test_form_round_trips_a_card_without_inventing_values(qapp):
    page = window_for(REPO_DATA_DIR).page(0)
    assert page._load(DEMO_CARD)
    card = page.form.to_card()
    with open(DEMO_CARD, "r", encoding="utf-8") as handle:
        original = json.loads(handle.read())
    # 表单只搬运卡片里有的东西：单位声明可以补齐（引擎有默认值），其余逐字相等
    for key in sorted(original):
        if key == "units":
            assert set(original["units"]).issubset(set(card["units"]))
            for family, unit in sorted(original["units"].items()):
                assert card["units"][family] == unit
        else:
            assert card[key] == original[key], key


# ---------------------------------------------------------------------------
# ② 设计说明核查
# ---------------------------------------------------------------------------

def test_check_page_parses_in_a_subprocess_then_renders_the_terminal_report(qapp, tmp_path):
    page = window_for(REPO_DATA_DIR).page(1)
    page.doc_field.setText(INJECTED_DOCX)
    ir_path = page.parse_document()
    assert ir_path and os.path.isfile(ir_path)
    assert "IR 已写入" in page.parse_text.toPlainText()      # 子进程的原话在这里可见
    report = page.check(ir_path)
    code, out, _err = cli_call(["--data-dir", REPO_DATA_DIR, "check", "--ir", ir_path])
    assert page.exit_code == code
    assert page.check_text.toPlainText() + "\n" == out       # 同一批行（K41）
    assert page.findings.rowCount() == len(report["findings"])


def test_check_page_says_the_parse_channel_is_unavailable(qapp, monkeypatch):
    """打包版没找到 CLI exe 时，界面必须说"通路不可用"，不能自己下场跑正则。"""
    from sdc.gui import page_check

    monkeypatch.setattr(page_check, "cli_channel", lambda: (None, os.getcwd()))
    page = window_for(REPO_DATA_DIR).page(1)
    page.doc_field.setText(INJECTED_DOCX)
    assert page.parse_document() is None
    text = page.parse_text.toPlainText()
    assert "不可用" in text and "sdc-cli" in text
    assert any("不可用" in line for line in page.messages)


# ---------------------------------------------------------------------------
# ③ 规范检查单
# ---------------------------------------------------------------------------

def test_checklist_page_without_ir_is_all_need_human_and_degraded(qapp):
    page = window_for(REPO_DATA_DIR).page(2)
    report = page.build(ir_path="")
    assert page.exit_code == 1
    assert report["summary"]["total"] == 107
    assert report["summary"]["by_verdict"] == {"need_human": 107}
    code, out, _err = cli_call(["--data-dir", REPO_DATA_DIR, "checklist"])
    assert page.text.toPlainText() + "\n" == out


def test_checklist_page_human_answer_round_trip(qapp):
    page = window_for(REPO_DATA_DIR).page(2)
    page.build(ir_path="")
    entry_id = page.report["entries"][0]["id"]
    page.table.cellWidget(0, 4).setCurrentText("符合")
    assert page.collected_answers() == {entry_id: "符合"}
    rebuilt = page.build(ir_path="", answers_path=page.answers_file())
    assert rebuilt["summary"]["by_verdict"]["human_pass"] == 1
    assert rebuilt["entries"][0]["human_answer"] == "符合"
    assert "人工答复：符合" in item_text(page.table, 0, 3)


def test_checklist_page_with_ir_uses_the_auto_first_pass(qapp, tmp_path):
    ir_path = make_ir(REPO_DATA_DIR, INJECTED_DOCX, tmp_path)
    page = window_for(REPO_DATA_DIR).page(2)
    report = page.build(ir_path=ir_path)
    code, out, _err = cli_call(["--data-dir", REPO_DATA_DIR, "checklist",
                               "--ir", ir_path])
    assert page.exit_code == code
    assert page.text.toPlainText() + "\n" == out
    assert report["ir_used"] is True


# ---------------------------------------------------------------------------
# ④ 报告导出
# ---------------------------------------------------------------------------

def test_export_page_writes_all_three_and_shows_the_selfcheck_facts(qapp, tmp_path):
    page = window_for(REPO_DATA_DIR).page(3)
    out_dir = str(tmp_path / "reports")
    page.out_dir.setText(out_dir)
    page.case_field.setText(DEMO_CARD)
    page.ir_field.setText(make_ir(REPO_DATA_DIR, INJECTED_DOCX, tmp_path))

    written = [page.export_result(), page.export_check(), page.export_checklist()]
    assert all(path and os.path.isfile(path) for path, _code in written)
    text = page.report_text.toPlainText()
    assert "0 外链自检：0 处违规" in text
    assert "REPORT_PLACEHOLDER" in text
    assert "免责声明在正文里：是" in text


def test_export_page_survives_a_failed_selfcheck_with_a_reason(qapp, tmp_path, monkeypatch):
    """落盘前自检不过 ⇒ 不写文件，并把原因说清楚（不吞 ReportError）。"""
    from sdc.gui import page_export

    def poisoned(result, case_path=""):
        return ["外部渠道 https://example.invalid/gb50017 的链接"]

    monkeypatch.setattr(page_export, "result_body", poisoned)
    page = window_for(REPO_DATA_DIR).page(3)
    page.out_dir.setText(str(tmp_path / "reports"))
    page.case_field.setText(DEMO_CARD)
    written, code = page.export_result()
    assert written is None and code == 2
    assert not os.listdir(os.path.join(str(tmp_path), "reports"))
    log = page.report_text.toPlainText()
    assert "未写出" in log and "自检" in log
    assert any("error" in line for line in page.messages)


# ---------------------------------------------------------------------------
# ⑤ 知识库与状态
# ---------------------------------------------------------------------------

def test_status_page_shows_gates_progress_and_queue(qapp):
    page = window_for(REPO_DATA_DIR).page(4)
    report = page.refresh()
    assert page.gate.rowCount() == len(report["modules"]) == 5
    assert all(item_text(page.gate, row, 1) == "blocked" for row in range(page.gate.rowCount()))
    assert page.queue.rowCount() == len(report["verify_queue"])
    assert page.selfcheck_text.toPlainText() == cli_call(
        ["--data-dir", REPO_DATA_DIR, "selfcheck"])[1].rstrip("\n")


def test_status_page_keeps_unmeasurable_and_unavailable_out_of_green(qapp):
    """夹具数据目录里没有合成语料 ⇒ 确定性回归是「不可用」。

    这条同时钉住两件事：分母/前置缺失不得画成达标（K43），以及界面用的是
    `sdc.suite.STATUS_LABEL` 那一份措辞（K41，界面不另发明一套状态词）。
    """
    from sdc.suite import STATUS_LABEL

    page = window_for(FIXTURE_KB_DIR).page(4)
    report = page.run_bench()
    labels = [(item_text(page.metrics, row, 0), item_text(page.metrics, row, 3))
              for row in range(page.metrics.rowCount())]
    statuses = dict((row["name"], row["status"]) for row in report["metrics"])
    for name, label in labels:
        assert label == STATUS_LABEL[statuses[name]]
        if statuses[name] != "pass":
            assert label != "达标", "%s 被涂绿了" % name
    assert ("确定性回归", "不可用") in labels
    assert any("不可用" in line for line in page.messages)


def test_clean_document_still_gets_a_checklist_with_a_visible_caveat(qapp, tmp_path):
    """干净语料核查是 pass，但"这不等于合规"那句必须在界面原话里。"""
    page = window_for(REPO_DATA_DIR).page(1)
    ir_path = make_ir(REPO_DATA_DIR, CLEAN_DOCX, tmp_path)
    report = page.check(ir_path)
    assert page.exit_code == 0 and report["findings"] == []
    assert "未发现非 pass 项" in page.check_text.toPlainText()
    assert "这不等于合规" in page.check_text.toPlainText()
    assert page.inactive.rowCount() == len(report["not_activated"])
