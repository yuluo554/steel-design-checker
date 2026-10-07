"""一键基准（M4）：指标表、退出码、README 对账，以及"探针不是空转"的反证。

口径 K39（解析步骤走子进程）、K43（指标表退出码）。
"""

import json
import os

import pytest

from _helpers import FIXTURE_KB_DIR, REPO_DATA_DIR
from sdc import cli, suite
from sdc.kb.loader import load_kb

README = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "README.md")
WORKDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       os.pardir, ".tmp_parse", "suite-test")


@pytest.fixture(scope="module")
def kb():
    return load_kb(REPO_DATA_DIR)


@pytest.fixture(scope="module")
def report(kb):
    return suite.build_report(kb, REPO_DATA_DIR, WORKDIR)


def _row(report, name):
    for row in report["metrics"]:
        if row["name"] == name:
            return row
    raise AssertionError("指标表没有 %r 这一行" % name)


# ---------------------------------------------------------------------------
# 指标表内容
# ---------------------------------------------------------------------------

def test_all_four_benchmarks_are_reported_as_one_table(report):
    names = [row["name"] for row in report["metrics"]]
    for expected in ("算例通过率", "确定性回归", "解析 F1", "缺陷检出率", "误报",
                     "条款可溯源率", "待核对闸门", "0 外链"):
        assert expected in names, names
    assert report["exit_code"] == suite.RC_DEGRADED, "分母 0 不能被说成通过"
    assert report["ok"] is False


def test_measured_values_match_the_underlying_benchmarks(report):
    """指标表不能自说自话：数值必须与单独跑一遍的结果一致。"""
    parse = suite._slim(report["detail"]["parse"])
    assert parse["f1"] == pytest.approx(1.0)
    assert _row(report, "解析 F1")["measured"] == "1.0000"
    audit = report["detail"]["audit"]
    assert audit["detection_rate"] == pytest.approx(1.0)
    assert audit["false_positives"] == []
    assert _row(report, "误报")["measured"] == "0 处"
    assert _row(report, "算例通过率")["status"] == "unmeasurable"
    assert _row(report, "算例通过率")["measured"] == "分母 0，样本待补"
    assert load_kb(REPO_DATA_DIR).records["case"] == []


def test_determinism_row_covers_ir_reports_and_deliverables(report):
    det = report["detail"]["determinism"]
    assert det["ir"]["status"] == "pass"
    assert det["ir"]["files"] == 24, "整批语料都要进两次比对，不能只挑一份"
    assert det["ir"]["diffs"] == []
    assert [c["ok"] for c in det["reports"]["checks"]] == [True, True]
    exports = dict((item["name"], item) for item in det["exports"]["items"])
    assert set(exports) == {"验算书", "核查清单", "检查单"}
    for item in exports.values():
        assert item["stable"] and item["link_violations"] == []
    assert _row(report, "确定性回归")["status"] == "pass"
    assert _row(report, "0 外链")["measured"] == "0 处（3 份交付物）"


def test_clause_traceability_counts_findings_not_just_data(report):
    row = _row(report, "条款可溯源率")
    assert row["status"] == "pass"
    assert row["measured"].startswith("12 / 12"), row["measured"]
    assert "渠道完整率" in row["definition"]


def test_gate_probe_reports_blocked_modules(report):
    row = _row(report, "待核对闸门")
    assert row["status"] == "pass" and row["measured"] == "0 例漏出数值"
    gate = report["detail"]["gate"]
    assert gate["runs"] == 2 and gate["blocked_modules"]
    assert all(row["conclusion"] == "blocked" for row in gate["cards"])


# ---------------------------------------------------------------------------
# 反证：探针与比对都能真的抓到东西
# ---------------------------------------------------------------------------

def test_diff_digests_detects_byte_change_and_missing_file():
    a = {"X.ir.json": "aaa", "Y.ir.json": "bbb"}
    assert suite.diff_digests(a, dict(a)) == []
    diffs = suite.diff_digests(a, {"X.ir.json": "aaa", "Y.ir.json": "zzz"})
    assert diffs == ["Y.ir.json 两次字节不一致"], diffs
    only_b = suite.diff_digests(a, {"X.ir.json": "aaa"})
    assert only_b == ["Y.ir.json 只在一侧产出"], only_b


def test_count_leaks_flags_numbers_out_of_a_blocked_module(kb):
    """blocked 通路漏出数值就是事故；探针必须真的能抓到，而不是永远返回空。"""
    leaking = {"ratio": 0.8, "steps": [{"no": 1}], "limits": [], "conclusion": "satisfied"}
    honest = {"ratio": None, "steps": [], "limits": [], "conclusion": "blocked"}
    assert suite.count_leaks(kb, [("fillet_weld", honest)]) == []
    assert suite.count_leaks(kb, [("fillet_weld", leaking)]) == ["fillet_weld"]


def test_exit_code_separates_unmeasurable_from_pass():
    row = suite._row("x", "gate", "m", "pass", "src")
    assert suite._exit_code([row]) == suite.RC_OK
    assert suite._exit_code([row, suite._row("y", "g", "m", "unmeasurable", "s")]) \
        == suite.RC_DEGRADED
    assert suite._exit_code([row, suite._row("y", "g", "m", "fail", "s")]) \
        == suite.RC_DEGRADED
    assert suite._exit_code([row, suite._row("y", "g", "m", "unavailable", "s")]) \
        == suite.RC_BAD_INPUT


# ---------------------------------------------------------------------------
# 数据目录不含语料时的诚实降级（夹具 KB 只有数值通路）
# ---------------------------------------------------------------------------

def test_fixture_kb_keeps_case_pass_rate_and_degrades_text_rows():
    kb = load_kb(FIXTURE_KB_DIR)
    report = suite.build_report(kb, FIXTURE_KB_DIR,
                                os.path.join(WORKDIR, "fixtures"))
    assert _row(report, "算例通过率")["measured"] == "7 / 7"
    assert _row(report, "算例通过率")["status"] == "pass"
    assert _row(report, "解析 F1")["status"] == "unavailable"
    assert _row(report, "待核对闸门")["status"] == "unavailable", "没有 examples/ 就无从探针"
    assert report["exit_code"] == suite.RC_BAD_INPUT


# ---------------------------------------------------------------------------
# 渲染与 README 对账
# ---------------------------------------------------------------------------

def test_metric_table_and_markdown_agree(report):
    text = suite.render_text(report)
    markdown = suite.metrics_markdown(report)
    for row in report["metrics"]:
        assert row["measured"] in text
        assert "| %s |" % row["name"] in markdown
    assert "免责声明：辅助验算工具" in text
    assert "退出码：%d" % report["exit_code"] in text


def test_readme_metrics_table_matches_a_live_run(report):
    """README 里的指标表是从这次实测来的；改了数据不重跑 README，这条就红。"""
    with open(README, "r", encoding="utf-8") as handle:
        readme = handle.read()
    for row in report["metrics"]:
        line = "| %s | %s | %s |" % (row["name"], row["gate"], row["measured"])
        assert line in readme, "README 的指标表与实测不一致：%s" % line
    assert "sdc bench --all --markdown" in readme, "README 要写清这张表怎么重生成"


def test_sweep_mode_prints_only_determinism(capsys):
    workdir = os.path.join(WORKDIR, "sweep")
    capsys.readouterr()
    code = cli.main(["--data-dir", REPO_DATA_DIR, "bench", "--sweep", "--workdir", workdir])
    text = capsys.readouterr().out
    assert code == suite.RC_OK, "确定性回归是全绿的一行：不一致时这里必须变成非 0 并写明差异"
    assert "sdc bench --sweep（确定性回归）" in text
    assert "[1] 指标表" not in text
    assert "整批 IR 两次字节一致" in text


# ---------------------------------------------------------------------------
# 命令面
# ---------------------------------------------------------------------------

def test_bench_mode_flags_are_exclusive_and_explicit(capsys):
    capsys.readouterr()
    assert cli.main(["--data-dir", REPO_DATA_DIR, "bench", "--cases", "--all"]) == 2
    assert "一次只能选一种基准" in capsys.readouterr().err
    assert cli.main(["--data-dir", REPO_DATA_DIR, "bench", "--all",
                     "--ir-dir", ".tmp_parse/ir"]) == 2
    assert "不接受 --ir-dir" in capsys.readouterr().err
    assert cli.main(["--data-dir", REPO_DATA_DIR, "bench", "--sweep", "--markdown"]) == 2
    assert "--markdown 只对 --all 有意义" in capsys.readouterr().err


def test_bench_all_json_is_machine_readable_and_stable(tmp_path, capsys):
    argv = ["--data-dir", REPO_DATA_DIR, "bench", "--all", "--json",
            "--workdir", os.path.join(str(tmp_path), "suite")]
    capsys.readouterr()
    assert cli.main(argv) == suite.RC_DEGRADED
    first = capsys.readouterr().out
    assert cli.main(argv) == suite.RC_DEGRADED
    second = capsys.readouterr().out
    assert first == second, "两次 --all 的 JSON 必须逐字节一致（口径 K8）"
    payload = json.loads(first)
    assert payload["metrics"] and payload["detail"]["determinism"]["ir"]["files"] == 24
    assert "\r" not in first


def test_bench_all_markdown_is_the_readme_source(tmp_path, capsys):
    capsys.readouterr()
    code = cli.main(["--data-dir", REPO_DATA_DIR, "bench", "--all", "--markdown",
                     "--workdir", os.path.join(str(tmp_path), "md")])
    text = capsys.readouterr().out
    assert code == suite.RC_DEGRADED
    assert text.startswith("| 指标 | 门槛 | 实测 | 结论 | 来源命令 |")
