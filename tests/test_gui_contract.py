"""GUI 与 CLI 的契约：同一份输入，两边的结论、正文、退出码、指纹必须逐字相同（口径 D08/K41）。

期望值全部来自命令面自己的输出（`sdc.cli.main` 现跑），这里不手写任何"界面应该显示什么"
的字符串 —— 手写的期望值会变成第三套事实源，正是本项目要避免的。
"""

import json
import os

from _gui import (CLEAN_DOCX, DEMO_CARD, FIXTURE_KB_DIR, INJECTED_DOCX,
                  REPO_DATA_DIR, cli_call, make_ir, qapp, window_for, write_card)


# ---------------------------------------------------------------------------
# ① 验算台 ↔ `sdc run`
# ---------------------------------------------------------------------------

def test_verify_text_and_rc_are_the_cli_output_verbatim(qapp):
    page = window_for(REPO_DATA_DIR).page(0)
    page._load(DEMO_CARD)
    page.run()
    code, out, err = cli_call(["--data-dir", REPO_DATA_DIR, "run", "--case", DEMO_CARD])
    assert page.exit_code == code == 1
    assert page.text.toPlainText() + "\n" == out
    assert err == ""


def test_verify_result_object_equals_the_cli_json_payload(qapp):
    """不只是文本相同：界面手里的 Result 与 `run --json` 反序列化出来的是同一个对象。"""
    page = window_for(REPO_DATA_DIR).page(0)
    page._load(DEMO_CARD)
    result = page.run()
    code, out, _err = cli_call(["--data-dir", REPO_DATA_DIR, "run",
                               "--case", DEMO_CARD, "--json"])
    assert result == json.loads(out)
    assert result["meta"]["data_fingerprint"] == json.loads(out)["meta"]["data_fingerprint"]


def test_verify_numbers_match_cli_on_the_fixture_kb(qapp):
    page = window_for(FIXTURE_KB_DIR).page(0)
    page._load(DEMO_CARD)
    result = page.run()
    code, out, _err = cli_call(["--data-dir", FIXTURE_KB_DIR, "run", "--case", DEMO_CARD])
    assert page.exit_code == code == 0
    assert result["conclusion"] != "blocked" and result["ratio"] is not None
    assert page.text.toPlainText() + "\n" == out
    assert out.rstrip("\n").endswith("辅助验算工具，不替代正式设计文件与施工图审查")
    _code, json_out, _err = cli_call(["--data-dir", FIXTURE_KB_DIR, "run",
                                     "--case", DEMO_CARD, "--json"])
    assert result == json.loads(json_out)


def test_illegal_card_value_produces_the_engine_message_not_an_invented_one(qapp, tmp_path):
    """表单填了引擎不认的值：界面显示的必须还是 `normalize_card` 的原话。"""
    card_path = write_card(tmp_path, {"h_f": "十二"})
    code, out, err = cli_call(["--data-dir", REPO_DATA_DIR, "run", "--case", card_path])
    assert code == 2

    page = window_for(REPO_DATA_DIR).page(0)
    page._load(DEMO_CARD)
    page.form.fields["h_f"].setText("十二")
    page.run()
    assert page.exit_code == 2
    assert page.text.toPlainText() == err        # 逐字节相同，连换行都不差
    assert "参数卡不可用" in err


# ---------------------------------------------------------------------------
# ② 核查 ↔ `sdc check`
# ---------------------------------------------------------------------------

def test_check_page_matches_cli_for_an_injected_document(qapp, tmp_path):
    ir_path = make_ir(REPO_DATA_DIR, INJECTED_DOCX, tmp_path)
    page = window_for(REPO_DATA_DIR).page(1)
    report = page.check(ir_path)
    code, out, _err = cli_call(["--data-dir", REPO_DATA_DIR, "check", "--ir", ir_path])
    assert page.exit_code == code == 1
    assert page.check_text.toPlainText() + "\n" == out
    _code, json_out, _err = cli_call(["--data-dir", REPO_DATA_DIR, "check",
                                     "--ir", ir_path, "--json"])
    assert report == json.loads(json_out)


def test_check_page_matches_cli_for_a_clean_document(qapp, tmp_path):
    ir_path = make_ir(REPO_DATA_DIR, CLEAN_DOCX, tmp_path)
    page = window_for(REPO_DATA_DIR).page(1)
    page.check(ir_path)
    code, out, _err = cli_call(["--data-dir", REPO_DATA_DIR, "check", "--ir", ir_path])
    assert page.exit_code == code == 0
    assert page.check_text.toPlainText() + "\n" == out


# ---------------------------------------------------------------------------
# ③ 检查单 ↔ `sdc checklist`
# ---------------------------------------------------------------------------

def test_checklist_page_matches_cli_both_with_and_without_ir(qapp, tmp_path):
    ir_path = make_ir(REPO_DATA_DIR, INJECTED_DOCX, tmp_path)
    page = window_for(REPO_DATA_DIR).page(2)

    page.build(ir_path="")
    code, out, _err = cli_call(["--data-dir", REPO_DATA_DIR, "checklist"])
    assert page.exit_code == code == 1
    assert page.text.toPlainText() + "\n" == out

    page.build(ir_path=ir_path)
    code, out, _err = cli_call(["--data-dir", REPO_DATA_DIR, "checklist", "--ir", ir_path])
    assert page.exit_code == code
    assert page.text.toPlainText() + "\n" == out


def test_checklist_answers_go_through_the_cli_surface(qapp, tmp_path):
    """界面的人工答复先落成 JSON 再走 `--answers` 通路，与命令行完全同构。"""
    page = window_for(REPO_DATA_DIR).page(2)
    page.build(ir_path="")
    page.table.cellWidget(0, 4).setCurrentText("不符合")
    page.table.cellWidget(1, 4).setCurrentText("不适用")
    answers_path = page.answers_file()
    report = page.build(answers_path=answers_path)

    code, out, _err = cli_call(["--data-dir", REPO_DATA_DIR, "checklist",
                               "--answers", answers_path])
    assert page.exit_code == code
    assert page.text.toPlainText() + "\n" == out
    assert report["summary"]["by_verdict"]["human_fail"] == 1
    assert report["summary"]["by_verdict"]["not_applicable"] == 1


# ---------------------------------------------------------------------------
# ④ 导出 ↔ `sdc report` / `check --out` / `checklist --out`
# ---------------------------------------------------------------------------

def _read(path):
    with open(path, "rb") as handle:
        return handle.read()


def test_exported_docx_bytes_equal_the_cli_exported_docx(qapp, tmp_path):
    ir_path = make_ir(REPO_DATA_DIR, INJECTED_DOCX, tmp_path)
    out_dir = str(tmp_path / "gui")
    page = window_for(REPO_DATA_DIR).page(3)
    page.out_dir.setText(out_dir)
    page.case_field.setText(DEMO_CARD)
    page.ir_field.setText(ir_path)
    gui_paths = [page.export_result(), page.export_check(), page.export_checklist()]

    cli_dir = str(tmp_path / "cli")
    os.makedirs(cli_dir)
    for argv in (["--data-dir", REPO_DATA_DIR, "report", "--case", DEMO_CARD,
                  "--out", os.path.join(cli_dir, "验算书.docx")],
                 ["--data-dir", REPO_DATA_DIR, "check", "--ir", ir_path,
                  "--out", os.path.join(cli_dir, "核查清单.docx")],
                 ["--data-dir", REPO_DATA_DIR, "checklist", "--ir", ir_path,
                  "--out", os.path.join(cli_dir, "检查单.docx")]):
        assert cli_call(argv)[0] in (0, 1), argv

    for (written, _code), name in zip(gui_paths, ("验算书", "核查清单", "检查单")):
        assert written is not None
        assert _read(written) == _read(os.path.join(cli_dir, "%s.docx" % name)), name


def test_export_page_reports_the_same_declined_export_as_the_cli(qapp, tmp_path):
    """正文里出现外部地址 ⇒ 两边都不写文件，界面给出的原因就是 ReportError 原文。

    这是"落盘前自检 fail closed"的反证测试：把一条 URL 塞进 case_id（它会进报告首行），
    0 外链断言（口径 K40）必须拦下来，而不是写出一份带外链的交付物。
    """
    bad_card = write_card(tmp_path, {"case_id": "详见 https://www.example.invalid 的说明"})
    gui_dir = str(tmp_path / "gui")
    page = window_for(REPO_DATA_DIR).page(3)
    page.out_dir.setText(gui_dir)
    page.case_field.setText(bad_card)
    written, code = page.export_result()
    cli_target = os.path.join(str(tmp_path), "cli.docx")
    cli_code, _out, err = cli_call(["--data-dir", REPO_DATA_DIR, "report",
                                   "--case", bad_card, "--out", cli_target])
    assert written is None and not os.path.exists(cli_target)
    assert code == cli_code == 2
    # ReportError 的原文带着各自的输出路径，所以逐字相同不在契约之内；
    # 契约是"两边都拒绝写出 + 同一套违规理由"。
    report_text = page.report_text.toPlainText()
    for clause in ("交付物自检未通过", "正文出现外部地址", "出处只写标准号+条号+渠道名，不写 URL"):
        assert clause in err, clause
        assert clause in report_text, clause
    assert any("error" in line for line in page.messages)


# ---------------------------------------------------------------------------
# ⑤ 状态页 ↔ `sdc selfcheck` / `sdc bench --all`
# ---------------------------------------------------------------------------

def test_status_page_selfcheck_text_equals_cli(qapp):
    page = window_for(REPO_DATA_DIR).page(4)
    report = page.refresh()
    code, out, _err = cli_call(["--data-dir", REPO_DATA_DIR, "selfcheck"])
    assert page.selfcheck_text.toPlainText() + "\n" == out
    _code, json_out, _err = cli_call(["--data-dir", REPO_DATA_DIR, "selfcheck", "--json"])
    assert report == json.loads(json_out)


def test_bench_all_table_and_text_equal_the_cli_run(qapp, monkeypatch, tmp_path):
    """一键基准在界面上跑一遍，指标表与明细必须与 `sdc bench --all` 逐行一致。

    两边的套件工作目录取同一个：`render_text` 会打印工作目录（那是事实的一部分，
    不是噪声），所以契约测试把它固定下来，而不是从期望值里抹掉。
    """
    workdir = os.path.abspath(os.path.join(str(tmp_path), "suite"))
    code, out, _err = cli_call(["--data-dir", REPO_DATA_DIR, "bench", "--all",
                               "--workdir", workdir])
    page = window_for(REPO_DATA_DIR).page(4)
    monkeypatch.setattr(page, "workdir", lambda: workdir)
    report = page.run_bench()
    assert page.exit_code == code == 1
    assert page.bench_text.toPlainText() + "\n" == out
    assert [row["status"] for row in report["metrics"]] == \
        ["unmeasurable", "pass", "pass", "pass", "pass", "pass", "pass", "pass",
         "unmeasurable"]
