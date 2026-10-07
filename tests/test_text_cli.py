"""M3 命令面：parse / check / checklist / bench --parse --audit 的退出码与产物契约。

退出码口径 K29：`check` 0=无非 pass 项，1=有可疑或异常（等级差异看报告），2=输入/数据不可用；
`checklist` 的 1 还包含"没接 IR"或"章节没覆盖齐"；`bench --parse/--audit` 缺 IR 目录是 2
（不在评测进程里现场解析文档，见口径 K26）。
"""

import json
import os
import subprocess
import sys

from _helpers import REPO_DATA_DIR
from sdc import cli

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src")
DOCX = os.path.join(REPO_DATA_DIR, "synth", "docx")


def _ir(tmp_path, name="SYNTH-0013.docx"):
    argv = ["--data-dir", REPO_DATA_DIR, "parse", "--doc",
            os.path.join(DOCX, name), "--out", os.path.join(str(tmp_path), "a.ir.json")]
    assert cli.main(argv) == 0
    return os.path.join(str(tmp_path), "a.ir.json")


def test_parse_single_doc_writes_ir_with_no_timestamps(tmp_path, capsys):
    path = _ir(tmp_path)
    with open(path, "r", encoding="utf-8") as handle:
        ir = json.loads(handle.read())
    assert ir["doc"]["sha256"] and ir["slots"]["grade"] == "Q420D"
    assert ir["conflicts"][0]["slot"] == "grade"
    with open(path, "rb") as handle:
        assert b"\r" not in handle.read()


def test_parse_requires_exactly_one_of_doc_or_dir(tmp_path, capsys):
    assert cli.main(["--data-dir", REPO_DATA_DIR, "parse"]) == 2
    assert cli.main(["--data-dir", REPO_DATA_DIR, "parse", "--dir",
                     os.path.join(str(tmp_path), "nope")]) == 2


def test_parse_batch_then_check_exit_codes(tmp_path, capsys):
    ir_dir = os.path.join(str(tmp_path), "ir")
    assert cli.main(["--data-dir", REPO_DATA_DIR, "parse", "--dir", DOCX,
                     "--out-dir", ir_dir]) == 0
    assert len([n for n in os.listdir(ir_dir) if n.endswith(".ir.json")]) == 24

    # 牌号矛盾的那份 ⇒ 1（有非 pass 项）；干净的那份 ⇒ 0
    assert cli.main(["--data-dir", REPO_DATA_DIR, "check", "--ir",
                     os.path.join(ir_dir, "SYNTH-0013.ir.json")]) == 1
    capsys.readouterr()
    assert cli.main(["--data-dir", REPO_DATA_DIR, "check", "--ir",
                     os.path.join(ir_dir, "SYNTH-0000.ir.json")]) == 0
    text = capsys.readouterr().out
    assert "未发现非 pass 项" in text
    assert "这不等于合规" in text           # 未启用规则必须被说出来，不能给一个干净的 pass 就完事
    assert "免责声明" in text


def test_check_json_is_stable_and_carries_provenance(tmp_path, capsys):
    ir_path = _ir(tmp_path)
    capsys.readouterr()
    argv = ["--data-dir", REPO_DATA_DIR, "check", "--ir", ir_path, "--json"]
    cli.main(argv)
    first = capsys.readouterr().out
    cli.main(argv)
    assert first == capsys.readouterr().out
    report = json.loads(first)
    assert report["meta"]["data_fingerprint"]
    assert report["findings"][0]["clause_ids"]
    assert all(finding["basis"] for finding in report["findings"])


def test_check_rejects_broken_input(tmp_path, capsys):
    bogus = os.path.join(str(tmp_path), "bogus.ir.json")
    with open(bogus, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("{}")
    assert cli.main(["--data-dir", REPO_DATA_DIR, "check", "--ir", bogus]) == 2
    assert cli.main(["--data-dir", REPO_DATA_DIR, "check", "--ir",
                     os.path.join(str(tmp_path), "missing.ir.json")]) == 2


def test_bench_parse_and_audit_need_ir_dir(tmp_path, capsys):
    assert cli.main(["--data-dir", REPO_DATA_DIR, "bench", "--parse"]) == 2
    assert cli.main(["--data-dir", REPO_DATA_DIR, "bench", "--audit"]) == 2
    assert cli.main(["--data-dir", REPO_DATA_DIR, "bench", "--cases", "--audit"]) == 2


def test_judgment_commands_never_read_or_parse_a_document(monkeypatch, tmp_path, capsys):
    """口径 K26 的**可测形态**：判定进程不读文档、不跑槽位抽取。

    注意别把这句话说过头：`.tmp_verify/m4/k26-import-graph/result.tsv` 实测
    `sdc.bench`/`sdc.rules.engine`/`sdc.selfcheck` 在 import 阶段就把 9 条抽取式编译了
    （它们复用 `parse.slots` 的 `canonical_value`/`SLOT_NAMES`），所以"不 import `re`"
    不成立；真正被隔离的是**对文档执行正则**这件事，以及解析与判定分进程（口径 K39）。
    """
    ir_dir = os.path.join(str(tmp_path), "ir")
    assert cli.main(["--data-dir", REPO_DATA_DIR, "parse", "--dir", DOCX,
                     "--out-dir", ir_dir]) == 0
    capsys.readouterr()

    def boom(*args, **kwargs):
        raise AssertionError("判定层读了文档或现场解析（口径 K26）")

    monkeypatch.setattr("sdc.parse.ir.read_document", boom)
    monkeypatch.setattr("sdc.cli.build_ir", boom)

    one = os.path.join(ir_dir, "SYNTH-0013.ir.json")
    assert cli.main(["--data-dir", REPO_DATA_DIR, "check", "--ir", one]) == 1
    assert cli.main(["--data-dir", REPO_DATA_DIR, "checklist", "--ir", one]) == 0
    assert cli.main(["--data-dir", REPO_DATA_DIR, "bench", "--parse",
                     "--ir-dir", ir_dir]) == 0
    assert cli.main(["--data-dir", REPO_DATA_DIR, "bench", "--audit",
                     "--ir-dir", ir_dir]) == 0
    assert cli.main(["--data-dir", REPO_DATA_DIR, "selfcheck"]) == 0


def test_bench_parse_meets_gate_and_audit_has_no_false_positive(tmp_path, capsys):
    ir_dir = os.path.join(str(tmp_path), "ir")
    assert cli.main(["--data-dir", REPO_DATA_DIR, "parse", "--dir", DOCX,
                     "--out-dir", ir_dir]) == 0
    capsys.readouterr()
    assert cli.main(["--data-dir", REPO_DATA_DIR, "bench", "--parse",
                     "--ir-dir", ir_dir]) == 0
    parse_text = capsys.readouterr().out
    assert "F1" in parse_text and "达标" in parse_text

    assert cli.main(["--data-dir", REPO_DATA_DIR, "bench", "--audit",
                     "--ir-dir", ir_dir]) == 0
    audit_text = capsys.readouterr().out
    assert "误报（非注入项被判非 pass）：0 处" in audit_text
    assert "检出率 1.0000" in audit_text
    assert "分母 0" in audit_text            # 可硬判 abnormal 的规则分母必须显式说明


def test_bench_parse_reports_missing_ir_instead_of_passing(tmp_path, capsys):
    ir_dir = os.path.join(str(tmp_path), "partial")
    os.makedirs(ir_dir)
    cli.main(["--data-dir", REPO_DATA_DIR, "parse", "--doc",
              os.path.join(DOCX, "SYNTH-0000.docx"), "--out",
              os.path.join(ir_dir, "SYNTH-0000.ir.json")])
    capsys.readouterr()
    assert cli.main(["--data-dir", REPO_DATA_DIR, "bench", "--parse",
                     "--ir-dir", ir_dir]) == 1
    assert "缺少 IR" in capsys.readouterr().out


def test_checklist_covers_all_eight_chapters_and_degrades_without_ir(tmp_path, capsys):
    assert cli.main(["--data-dir", REPO_DATA_DIR, "checklist"]) == 1
    out = capsys.readouterr().out
    assert "未接入 —— 全部条目只能标为待人工确认" in out

    capsys.readouterr()
    assert cli.main(["--data-dir", REPO_DATA_DIR, "checklist",
                     "--ir", _ir(tmp_path)]) == 0
    text = capsys.readouterr().out
    assert "尚未覆盖的章" not in text
    assert "条目 107 条，覆盖 8 章" in text


def test_checklist_answers_are_recorded_separately_from_auto_verdict(tmp_path, capsys):
    answers = os.path.join(str(tmp_path), "answers.json")
    with open(answers, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"GB55006-2021:5.1.3": "符合",
                                 "GB55006-2021:3.0.2": "不适用"}, ensure_ascii=False))
    capsys.readouterr()
    assert cli.main(["--data-dir", REPO_DATA_DIR, "checklist", "--ir", _ir(tmp_path),
                     "--answers", answers]) == 0
    out = capsys.readouterr().out
    assert "符合(人工)" in out and "不适用(人工)" in out
    assert "自动初判" in out                      # 人工答复与自动初判分列留痕


def test_checklist_json_has_no_forbidden_verdict_while_basis_is_located(tmp_path, capsys):
    ir_path = _ir(tmp_path)
    capsys.readouterr()
    assert cli.main(["--data-dir", REPO_DATA_DIR, "checklist",
                     "--ir", ir_path, "--json"]) == 0
    payload = capsys.readouterr().out
    report = json.loads(payload)
    # 依据全 located ⇒ 自动初判只能"可疑"，不能出现"不符合"
    assert not [row for row in report["entries"]
                if row["verdict"] == "auto_flag" and row["auto"]["level"] == "abnormal"
                and row["status"] == "located"]


def test_cli_runs_as_module_with_pythonpath(tmp_path):
    """`py -3 -X utf8 -m sdc` 的可演示入口（HANDOFF 的演示命令都走这条路）。"""
    env = dict(os.environ, PYTHONPATH=os.path.abspath(SRC))
    result = subprocess.run([sys.executable, "-X", "utf8", "-m", "sdc", "selfcheck", "--json"],
                            cwd=os.path.abspath(os.path.join(SRC, os.pardir)),
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert result.returncode == 0, result.stdout.decode("utf-8", "replace")[:400]
    assert json.loads(result.stdout.decode("utf-8"))["ok"] is True
