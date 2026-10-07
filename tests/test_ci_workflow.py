"""CI workflow 与基准门禁的守门测试（M6）。

三条各管一段风险：
- workflow 必须是**可解析**的 YAML 且每个 job 有 `runs-on`/`steps`——发票台账 M6 的实录是
  step 名里「冒号+空格」没加引号，整份 workflow 非法，GitHub 一个 job 都不建，而文件的
  `state` 仍显示 active、字节也洁净，只有真解析才暴露；
- 依赖声明必须覆盖这条测试自己（`dev` 里没 pyyaml 的话它会静默跳过，"CI 绿但悄悄少跑"）；
- `scripts/ci_bench_gate.py` 的允许「不可判」名单要和 README 那张表对齐——README 由
  `test_suite.py` 与实跑逐行对账，所以这条等于把门禁名单钉在实测结果上。
"""

import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = os.path.join(REPO, ".github", "workflows")
README = os.path.join(REPO, "README.md")
PYPROJECT = os.path.join(REPO, "pyproject.toml")

yaml = pytest.importorskip("yaml", reason="CI 守门走 extras：pip install -e .[dev]")

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "ci_bench_gate", os.path.join(REPO, "scripts", "ci_bench_gate.py"))
gate_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate_mod)


def _load(name):
    with open(os.path.join(WORKFLOWS, name), "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _workflow_names():
    if not os.path.isdir(WORKFLOWS):
        return []
    return sorted(n for n in os.listdir(WORKFLOWS) if n.endswith((".yml", ".yaml")))


def test_workflows_exist_and_are_named():
    assert _workflow_names(), "缺少 .github/workflows/*.yml：D12 承诺的矩阵从未建过就是红的"


@pytest.mark.parametrize("name", _workflow_names() or ["missing"])
def test_every_workflow_parses_and_jobs_are_structured(name):
    if not os.path.isfile(os.path.join(WORKFLOWS, name)):
        pytest.skip("没有 workflow 文件")
    doc = _load(name)
    assert isinstance(doc, dict), "%s 不是映射" % name
    jobs = doc.get("jobs")
    assert isinstance(jobs, dict) and jobs, "%s 没有 jobs" % name
    for job_id, job in jobs.items():
        assert job.get("runs-on"), "job %s 缺 runs-on" % job_id
        steps = job.get("steps")
        assert isinstance(steps, list) and steps, "job %s 缺 steps" % job_id
        for step in steps:
            assert isinstance(step, dict), "job %s 的某个 step 不是映射" % job_id
            if "name" in step:
                # 名字必须是字符串：冒号+空格未加引号时 YAML 会把它解析成映射或报错
                assert isinstance(step["name"], str), "job %s 有 step 名被解析成了结构" % job_id


def test_matrix_spans_both_python_baselines_and_covers_gui():
    """D12：3.8 与 3.12 双矩阵；GUI 测试必须至少有一个矩阵真跑（否则 31 项常驻跳过）。"""
    doc = _load("ci.yml")
    matrix = doc["jobs"]["test"]["strategy"]["matrix"]["include"]
    versions = {str(entry["python-version"]) for entry in matrix}
    assert {"3.8", "3.12"} <= versions, "矩阵要覆盖 3.8 与 3.12，实得 %s" % sorted(versions)
    gui = [entry for entry in matrix if "gui" in str(entry.get("extras", "")).split(",")]
    assert gui, "没有任何矩阵安装 gui extras：GUI 测试会全平台静默跳过"
    assert {str(entry["python-version"]) for entry in gui} & {"3.8"}, "gui 矩阵要含 3.8 基线"


def test_dev_extras_declare_pyyaml():
    """这条测试自己依赖 pyyaml；漏声明只会静默少跑，所以把声明也测一遍。"""
    with open(PYPROJECT, "r", encoding="utf-8") as handle:
        text = handle.read()
    dev_line = [line for line in text.splitlines() if line.strip().startswith("dev = [")]
    assert dev_line and "pyyaml" in dev_line[0].lower(), "dev extras 必须声明 pyyaml（CI YAML 守门用）"


def _row(name, status):
    return {"name": name, "gate": "-", "measured": "x", "status": status, "source": "s"}


def test_bench_gate_reds_on_fail_unavailable_and_new_unmeasurable():
    cases = [
        ([_row("误报", "fail")], 1, "未达标"),
        ([_row("解析 F1", "unavailable")], 2, "不可用"),
        ([_row("某新指标", "unmeasurable")], 1, "未登记"),
    ]
    for rows, rc, expect in cases:
        _lines, problems = gate_mod.gate({"metrics": rows, "data_fingerprint": "f"}, rc)
        assert problems, "门禁对 %s 是空转" % expect


def test_bench_gate_green_when_only_known_unmeasurable():
    rows = [_row("解析 F1", "pass"), _row("算例通过率", "unmeasurable"),
            _row("可硬判 abnormal 的规则分母", "unmeasurable")]
    _lines, problems = gate_mod.gate({"metrics": rows, "data_fingerprint": "f"}, 1)
    assert problems == [], problems
    # 退出码与状态不一致也必须红（K43 的码表不能只对一半）
    _lines, problems = gate_mod.gate({"metrics": [_row("解析 F1", "pass")],
                                      "data_fingerprint": "f"}, 1)
    assert problems and "退出码" in problems[0]


def test_readme_test_module_count_matches_disk():
    """README 与 plan 的计数漂移是文档债第一眼（全仓同步：测试模块数一处不漏）。"""
    modules = sorted(n for n in os.listdir(os.path.join(REPO, "tests"))
                     if n.startswith("test_") and n.endswith(".py"))
    with open(README, "r", encoding="utf-8") as handle:
        readme = handle.read()
    assert "%d 个测试模块" % len(modules) in readme, (
        "README 写的测试模块数与 tests/ 实际数量不一致：%d" % len(modules))


def test_gate_whitelist_matches_readme_unmeasurable_rows():
    """README 的指标表由 test_suite.py 与实跑逐行对账 ⇒ 这里等于对账实测的不可判集合。"""
    with open(README, "r", encoding="utf-8") as handle:
        lines = [line for line in handle.read().splitlines() if line.startswith("|")]
    unmeasurable, bad = set(), set()
    for line in lines:
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 5 or cells[0] in ("指标", "") or set(cells[0]) <= {"-"}:
            continue
        if cells[3] == "不可判":
            unmeasurable.add(cells[0])
        elif cells[3] in ("未达标", "不可用"):
            bad.add(cells[0])
    assert not bad, "README 指标表出现未达标/不可用行：%s" % sorted(bad)
    assert unmeasurable == set(gate_mod.KNOWN_UNMEASURABLE), (
        "README 的不可判集合与门禁名单不一致：README=%s 门禁=%s"
        % (sorted(unmeasurable), sorted(gate_mod.KNOWN_UNMEASURABLE)))
    assert unmeasurable == set(gate_mod.KNOWN_UNMEASURABLE), (
        "README 的不可判集合与门禁名单不一致：改了数据要同时登记，不许默默放行")
